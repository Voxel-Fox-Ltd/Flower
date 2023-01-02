from __future__ import annotations

import asyncio

from typing import Optional, TypedDict
from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands, vbu

from cogs import utils


if __debug__:
    _poedit = lambda x: x

    # TRANSLATORS: Name of a command. Must be lowercase.
    _poedit("water")
    # TRANSLATORS: Description of a command.
    _poedit("Water one of your plants.")
    # TRANSLATORS: Name of a command option. Must be lowercase.
    _poedit("plant")
    # TRANSLATORS: Description of a command option.
    _poedit("The plant to water.")

    # TRANSLATORS: Name of a command. Must be lowercase.
    _poedit("waterall")
    # TRANSLATORS: Description of a command.
    _poedit("Water all of your plants.")


_t = lambda i, x: vbu.translation(i, "flower").gettext(x)


class WaterPlantMultiplier(TypedDict):
    multiplier: float
    text: str


class WaterCommands(vbu.Cog[utils.types.Bot]):

    @property
    def topgg_url(self) -> Optional[str]:
        """
        Get the Topgg vote API URL.
        """

        if not self.bot.user:
            return None
        return "https://top.gg/bot/{0}/vote".format(self.bot.user.id)

    async def get_user_voted(
            self,
            user_id: int) -> bool:
        """
        Returns whether or not the user with the given ID has
        voted for the bot on Top.gg.

        Parameters
        -----------
        user_id: int
            The ID of the user we want to check.

        Returns
        --------
        bool
            Whether or not the user voted for the bot.
        """

        # Get the token
        api_keys = self.bot.config.get('bot_listing_api_keys', {})
        topgg_token: Optional[str] = api_keys.get('topgg_token')
        if not topgg_token:
            return False

        # Build our request
        if not self.topgg_url:
            return False
        params = {
            "userId": user_id,
        }
        headers = {
            "Authorization": topgg_token,
        }

        # Make request
        get = {
            "url": self.topgg_url,
            "params": params,
            "headers": headers,
        }
        async with self.bot.session.get(**get) as r:
            try:
                r.raise_for_status()
                data = await r.json()
            except Exception:
                return False

        # And return
        return bool(data['voted'])

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "waterall")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Water all of your plants.")
                for i in discord.Locale
            },
        ),
    )
    @vbu.i18n("flower")
    async def waterall(
            self,
            ctx: vbu.SlashContext):
        """
        Water all of your plants.
        """

        # Open db so we can get information
        async with vbu.Database() as db:

            # Make sure the user is a premium subscriber
            user_info = await utils.UserInfo.fetch_by_id(db, ctx.author.id)
            if not user_info.has_premium:
                return await ctx.send(
                    _(
                        "You need to be a premium subscriber to use this "
                        "command. "
                    ),
                    ephemeral=True,
                )

            # Get all of the user's plants
            all_plants = await utils.UserPlant.fetch_all_by_user_id(
                db,
                ctx.author.id,
            )

        # See which ones we can water
        waterable: list[utils.UserPlant] = []
        for plant in all_plants:
            if plant.is_waterable:
                waterable.append(plant)

        # If there aren't any waterable ones, then just tell them we're
        # continuing on
        if not waterable:
            return await ctx.interaction.response.send_message(
                _(
                    "You don't have any plants that need watering right now!"
                ),
                ephemeral=True,
            )

        # Otherwise loop through and run the water command for each of the
        # plants
        embeds: list[discord.Embed] = []
        for plant in waterable:
            if (e := await self.water_plant(ctx.interaction, plant)):
                embeds.append(e)
        while embeds:
            await ctx.interaction.followup.send(
                embeds=embeds[:10],
            )
            embeds = embeds[10:]

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user whose plants you want to water.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=True,
                ),
                discord.ApplicationCommandOption(
                    name="plant",
                    description="The plant to water.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                    autocomplete=True,
                ),
            ],
        ),
    )
    async def waterother(
            self,
            ctx: vbu.SlashContext,
            user: discord.User,
            plant: str):
        """
        Water someone else's plant.
        """

        # Make sure they have key access to the pinged user's garden
        async with vbu.Database() as db:
            rows = await db.call(
                """
                SELECT
                    *
                FROM
                    user_garden_access
                WHERE
                    garden_access = $1
                AND
                    garden_owner = $2
                """,
                ctx.interaction.user.id,
                user.id,
            )
        if not rows:
            return await ctx.interaction.response.send_message(
                (
                    _("You don't have access to {user}'s garden!")
                    .format(user=user.mention)
                ),
                ephemeral=True,
            )

        # Try and water the given plant :)
        if (embed := await self.water_plant(ctx.interaction, plant, user=user)):
            return await ctx.interaction.followup.send(embed=embed)

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "water")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Water one of your plants.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="plant",
                    description="The plant to water.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                    autocomplete=True,
                    name_localizations={
                        i: _t(i, "plant")
                        for i in discord.Locale
                    },
                    description_localizations={
                        i: _t(i, "The plant to water.")
                        for i in discord.Locale
                    },
                ),
            ],
        ),
    )
    @vbu.i18n("flower")
    async def water(
            self,
            ctx: vbu.SlashContext,
            plant: str | utils.UserPlant):
        """
        Water one of your plants.
        """

        if (embed := await self.water_plant(ctx.interaction, plant)):
            return await ctx.interaction.followup.send(embed=embed)

    async def water_plant(
            self,
            interaction: discord.Interaction,
            plant: str | utils.UserPlant,
            *,
            user: discord.User | None = None) -> discord.Embed | None:
        """
        Water a plant.

        This method takes an interaction object (which will be responded to
        within the method), the plant to water (as either a string of the
        plant's name, or a plant object), and optionally a user whose plant
        you want to water (used for when the person watering the plant is not
        the owner of the plant).
        """

        # Assign a user var
        waterer: discord.User = interaction.user  # pyright: ignore
        target: discord.User = user or waterer

        # Open db to get some user information
        async with vbu.Database() as db:

            # Get a plant object associated with the plant name they gave
            user_plant: utils.UserPlant | None = None
            if isinstance(plant, str):
                user_plant = await utils.UserPlant.fetch_by_name(
                    db,
                    target.id,
                    plant,
                )
            else:
                user_plant = plant

            # Get the user info associated with both the waterer and the
            # target user so that we can update them later
            waterer_info: utils.UserInfo | None = None
            target_info: utils.UserInfo | None = None
            if user_plant is not None:
                waterer_info = await utils.UserInfo.fetch_by_id(db, waterer.id)
                target_info = waterer_info
                if waterer != target:
                    target_info = await utils.UserInfo.fetch_by_id(db, target.id)

        # Make sure we have a plant that exists
        if user_plant is None:
            if waterer == target:
                await interaction.response.send_message(
                    _("You don't have a plant with that name!"),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    (
                        _("{user} doesn't have a plant with that name!")
                        .format(user=target.mention)
                    ),
                    ephemeral=True,
                )
            return None

        # Past this point we have certain guarentees; these are all here for
        # the type checker
        assert user_plant is not None
        assert waterer_info is not None
        assert target_info is not None

        # Meanwhile, this guarentee I actually want to be sure of
        # This will make sure we can't pass in _someone else's_ plant to
        # be watered
        if user_plant.user_id != target.id:
            raise AssertionError

        # Make sure the plant isn't dead
        if user_plant.is_dead:
            if waterer == target:
                await interaction.response.send_message(
                    _("You sadly pour water into the soil of your dead plant."),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    (
                        _(
                            "You sadly pour water into the soil of {user}'s "
                            "dead plant."
                        )
                        .format(user=target.mention)
                    ),
                    ephemeral=True,
                )
            return None

        # See if the timeout for watering has passed
        cooldown = (
            utils.constants.WATER_COOLDOWN
            if waterer == target
            else utils.constants.KEYHOLDER_WATER_COOLDOWN
        )
        if user_plant.last_water_time is not None:
            timeout_time = (
                user_plant.last_water_time
                + cooldown
            )
            if timeout_time > dt.utcnow():
                wait_time = discord.utils.format_dt(timeout_time, "R")
                await interaction.response.send_message(
                    _(
                        "You can't water that plant yet! Please try again "
                        "{wait_time}."
                    ).format(wait_time=wait_time),
                    ephemeral=True,
                )
                return None

        # Defer so we can do some more intensive stuff now
        if not interaction.response.is_done():
            await interaction.response.defer()

        # Set up original original data before we morph it with calculations
        original_gained_experience: int = user_plant.plant.get_experience()
        gained_experience: int = original_gained_experience
        multipliers: list[WaterPlantMultiplier] = []

        # Plant multiplier - premium subscriber
        if waterer_info.has_premium:
            multipliers.append(
                {
                    "multiplier": 2.0,
                    "text": _("You're subscribed to Flower Premium! :D"),
                }
            )

        # Plant multiplier - 30 second cooldown
        last_water_delta = (
            dt.utcnow()
            - user_plant.last_water_time
            - cooldown
        )
        if last_water_delta <= timedelta(seconds=30):
            multipliers.append(
                {
                    "multiplier": 1.5,
                    "text": _(
                        "You watered within 30 seconds of "
                        "the plant's cooldown resetting."
                    ),
                },
            )

        # Plant multiplier - got from a trade
        if user_plant.original_owner_id != user_plant.user_id:
            multipliers.append(
                {
                    "multiplier": 1.1,
                    "text": _(
                        "This plant has been traded away from its original "
                        "owner!"
                    ),
                },
            )

        # Plant multiplier - voted on Topgg
        user_voted_api_request: bool = False
        try:
            user_voted_api_request = await asyncio.wait_for(
                self.get_user_voted(interaction.user.id),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            pass
        if user_voted_api_request:
            multipliers.append(
                {
                    "multiplier": 1.1,
                    "text": _(
                        "You [voted for the bot]({topgg_url}) "
                        "on Top.gg."
                    ).format(topgg_url=self.topgg_url),
                },
            )

        # Plant multiplier - plant has been alive longer than 7 days
        if user_plant.adoption_time < dt.utcnow() - timedelta(days=7):
            multipliers.append(
                {
                    "multiplier": 1.2,
                    "text": _("This plant has been alive for over 7 days!"),
                },
            )

        # Plant multiplier - plant is immortal
        if user_plant.immortal:
            multipliers.append(
                {
                    "multiplier": 0.5,
                    "text": _("This plant is immortal."),
                },
            )

        # Apply multipliers
        gained_experience_float: float = gained_experience
        for multiplier in multipliers:
            gained_experience_float *= multiplier["multiplier"]
        gained_experience = int(gained_experience_float)

        # Update the database
        async with vbu.Database() as db:
            await user_plant.update(
                db,
                nourishment=min(
                    user_plant.nourishment + 1,
                    user_plant.plant.max_nourishment_level,
                ),
                last_water_time=dt.utcnow(),
            )
            await waterer_info.update(
                db,
                experience=waterer_info.experience + gained_experience,
            )
            await utils.update_achievement_count(
                db,
                waterer.id,
                utils.Achievement.waters,
            )

        # Send the response
        embed = vbu.Embed(use_random_colour=True)
        embed.title=_("Watered {plant_name}!").format(
            plant_name=user_plant.name,
        )
        description_lines: list[str] = []
        if not multipliers:
            description_lines.append(
                _(
                    "You pour water into your plant's soil, gaining you "
                    "**{experience}** experience."
                ).format(experience=gained_experience)
            )
        else:
            description_lines.append(
                _(
                    "You pour water into your plant's soil, gaining you "
                    "~~{original_experience}~~ **{experience}** experience."
                ).format(
                    original_experience=original_gained_experience,
                    experience=gained_experience,
                )
            )
        for multiplier in multipliers:
            description_lines.append(
                f"**{multiplier['multiplier']}** - {multiplier['text']}"
            )
        embed.description = "\n".join(description_lines)
        self.bot.set_footer_from_config(embed)
        return embed

    water.autocomplete(
        utils
        .autocomplete
        .get_plant_name_autocomplete(is_waterable=True))  # pyright: ignore


def setup(bot: utils.types.Bot):
    x = WaterCommands(bot)
    bot.add_cog(x)
