from __future__ import annotations
import asyncio

from typing import Optional, TypedDict
from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands, vbu

from cogs import utils


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
            options=[
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
    @vbu.i18n("flower")
    async def water(
            self,
            ctx: vbu.SlashContext,
            plant: str):
        """
        Water one of your plants.
        """

        # Get a plant object associated with the plant name they gave
        async with vbu.Database() as db:
            user_plant = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                plant,
            )
            if user_plant is None:
                return await ctx.interaction.response.send_message(
                    _("You don't have a plant with that name!")
                )
            user_info = await utils.UserInfo.fetch_by_id(db, ctx.author.id)

        # Make sure the plant isn't dead
        if user_plant.is_dead:
            return await ctx.interaction.response.send_message(
                _("You sadly pour water into the soil of your deat plant.")
            )

        # See if the timeout for watering has passed
        if user_plant.last_water_time is not None:
            timeout_time = (
                user_plant.last_water_time
                + utils.constants.WATER_COOLDOWN
            )
            if timeout_time > dt.utcnow():
                wait_time = discord.utils.format_dt(timeout_time, "R")
                return await ctx.interaction.response.send_message(
                    _(
                        "You can't water that plant yet! Please wait "
                        "{wait_time} before trying again."
                    ).format(wait_time=wait_time),
                    ephemeral=True,
                )

        # Defer so we can do some more intensive stuff now
        await ctx.interaction.response.defer()

        # Set up original original data before we morph it with calculations
        original_gained_experience: int = user_plant.plant.get_experience()
        gained_experience: int = original_gained_experience
        multipliers: list[WaterPlantMultiplier] = []

        # Plant multiplier - premium subscriber
        if user_info.has_premium:
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
            - utils.constants.WATER_COOLDOWN
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
        if user_plant.original_owner_id != ctx.author.id:
            multipliers.append(
                {
                    "multiplier": 1.1,
                    "text": _("You got this plant from a trade!"),
                },
            )

        # Plant multiplier - voted on Topgg
        user_voted_api_request: bool = False
        try:
            user_voted_api_request = await asyncio.wait_for(
                self.get_user_voted(ctx.author.id),
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
            await user_info.update(
                db,
                experience=user_info.experience + gained_experience,
            )

        # Send the response
        embed = vbu.Embed(use_random_colour=True)
        embed.title=_("Watered {plant_name}!").format(
            plant_name=user_plant.name,
        )
        description_lines: list[str] = []
        if original_gained_experience == gained_experience:
            description_lines.append(
                _(
                    "You pour water into your plant's soil, gaining you "
                    "{experience} experience."
                ).format(experience=gained_experience)
            )
        else:
            description_lines.append(
                _(
                    "You pour water into your plant's soil, gaining you "
                    "~~{original_experience}~~ {experience} experience."
                ).format(
                    original_experience=original_gained_experience,
                    experience=gained_experience,
                )
            )
        if multipliers:
            description_lines.append("")
        for multiplier in multipliers:
            description_lines.append(multiplier["text"])
        embed.description = "\n".join(description_lines)
        self.bot.set_footer_from_config(embed)
        await ctx.interaction.followup.send(
            embeds=[embed],
        )


def setup(bot: utils.types.Bot):
    x = WaterCommands(bot)
    bot.add_cog(x)
