from __future__ import annotations

import asyncio
from datetime import datetime as dt, timedelta
from typing import TYPE_CHECKING, Optional, List, Tuple
import uuid

import discord
from discord.ext import commands, tasks, vbu

from cogs import utils

if TYPE_CHECKING:
    from cogs.utils.types import (
        WaterPlantPayload,
        PlantLevelsRow,
        PlantLevelsRows,
        WaterPlantMultiplier,
        UserSettingsRows,
        UserSettingsRow,
    )


class PlantCareCommands(vbu.Cog[utils.types.Bot]):

    TOPGG_GET_VOTES_ENDPOINT = "https://top.gg/api/bots/{bot_client_id}/check"

    def __init__(self, bot):
        super().__init__(bot)
        self.plant_death_timeout_loop.start()

    def cog_unload(self):
        self.plant_death_timeout_loop.cancel()

    async def get_user_voted(
            self,
            user_id: int) -> bool:
        """
        Returns whether or not the user with the given ID has voted for the bot on Top.gg.

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
        topgg_token = self.bot.config.get('bot_listing_api_keys', {}).get('topgg_token')
        if not topgg_token:
            return False

        # Build our request
        params = {"userId": user_id}
        headers = {"Authorization": topgg_token}
        url = self.TOPGG_GET_VOTES_ENDPOINT.format(bot_client_id=self.bot.config['oauth']['client_id'])

        # Make request
        async with self.bot.session.get(url, params=params, headers=headers) as r:
            try:
                r.raise_for_status()
                data = await r.json()
            except Exception:
                return False

        # And return
        return bool(data['voted'])

    @tasks.loop(minutes=1)
    async def plant_death_timeout_loop(self):
        """
        Loop to see if we should kill off any plants that may have been timed out.
        """

        async with vbu.Database() as db:

            # Kill any dead plants
            updated_plant_rows = await db(
                """UPDATE plant_levels SET plant_nourishment=-plant_levels.plant_nourishment WHERE
                plant_nourishment > 0 AND last_water_time + $2 < $1 AND immortal=FALSE RETURNING *""",
                dt.utcnow(), timedelta(**self.bot.config['plants']['death_timeout']),
            )

            # Add counter for plant dying
            for row in updated_plant_rows:
                await db(
                    """INSERT INTO plant_achievement_counts (user_id, plant_type, plant_death_count) VALUES ($1, $2, 1)
                    ON CONFLICT (user_id, plant_type) DO UPDATE SET
                    plant_death_count=plant_achievement_counts.max_plant_nourishment+1""",
                    row['user_id'], row['plant_type'],
                )

            # Add a maximum plant lifetime
            await db(
                """INSERT INTO user_achievement_counts (user_id, max_plant_lifetime)
                (SELECT user_id, MAX(TIMEZONE('UTC', NOW()) - plant_adoption_time) FROM plant_levels WHERE
                plant_levels.plant_nourishment > 0 AND immortal=FALSE GROUP BY user_id) ON CONFLICT
                (user_id) DO UPDATE SET max_plant_lifetime=GREATEST(user_achievement_counts.max_plant_lifetime,
                excluded.max_plant_lifetime) WHERE user_achievement_counts.user_id=excluded.user_id""",
            )
    @plant_death_timeout_loop.before_loop
    async def before_plant_death_timeout_loop(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def get_water_plant_dict(
            text: str,
            success: bool = False,
            gained_experience: int = 0,
            new_nourishment_level: int = 0,
            new_user_experience: int = 0,
            voted_on_topgg: bool = False,
            multipliers: Optional[List[WaterPlantMultiplier]] = None) -> WaterPlantPayload:
        """
        Return a JSON-friendly dict of a relevant information for having watered a plant.

        Parameters
        -----------
        text: str
            The text to be returned.
        success: bool
            Whether or not the water was a success.
        gained_experience: int
            The amount of experience gained.
        new_nourishment_level: int
            The new nourishment level of the plant.
        new_user_experience: int
            The new total experience of the user.
        voted_on_topgg: bool
            Whether or not the user voted on Top.gg.
        multipliers: Optional[List[dict]]
            A list of multiplier values that were used.
        """

        return {
            "text": text,
            "success": success,
            "gained_experience": gained_experience,
            "new_nourishment_level": new_nourishment_level,
            "new_user_experience": new_user_experience,
            "voted_on_topgg": voted_on_topgg,
            "multipliers": multipliers or list(),
        }

    async def water_plant_backend(
            self,
            user_id: int,
            plant_name: str,
            waterer_id: Optional[int] = None) -> WaterPlantPayload:
        """
        Run the backend for the plant watering
        """

        # Decide on our plant type - will be ignored if there's already a plant
        db = await vbu.Database.get_connection()

        # Get friend watering status
        waterer_id = waterer_id or user_id
        waterer_is_owner = user_id == waterer_id

        # See if they can water this person's plant
        if not waterer_is_owner:
            given_key = await db(
                """SELECT * FROM user_garden_access WHERE garden_owner=$1 AND garden_access=$2""",
                user_id, waterer_id,
            )
            if not given_key:
                await db.disconnect()
                return self.get_water_plant_dict(f"You don't have access to <@{user_id}>'s garden!")

        # See if they have a plant available
        plant_level_row: PlantLevelsRows = await db(
            """SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)""",
            user_id, plant_name,
        )

        # They don't
        if not plant_level_row:
            await db.disconnect()
            text = vbu.format(
                f"{{0:pronoun,You,They}} {{0:pronoun,don't,doesn't}} have a plant with the name **{plant_name}**",
                waterer_is_owner
            )
            return self.get_water_plant_dict(text)

        # Get the plant type
        plant_data = self.bot.plants[plant_level_row[0]['plant_type']]

        # See if the user running the command is the owner of the plant and give a cooldown period properly
        if waterer_is_owner:
            key = "water_cooldown"
        else:
            key = "guest_water_cooldown"
        water_cooldown_period = timedelta(**self.bot.config['plants'][key])

        # See if they're within their water time period
        last_water_time = plant_level_row[0]['last_water_time']
        if (last_water_time + water_cooldown_period) > dt.utcnow() and user_id not in self.bot.owner_ids:
            await db.disconnect()
            timeout = vbu.TimeValue((
                (plant_level_row[0]['last_water_time'] + water_cooldown_period) - dt.utcnow()
            ).total_seconds())
            return self.get_water_plant_dict(vbu.format(
                (
                    f"You need to wait another {timeout.clean_spaced} to be able to water "
                    f"{{0:pronoun,their,your}} {plant_level_row[0]['plant_type'].replace('_', ' ')}."
                ),
                waterer_is_owner,
            ))

        # See if the plant should be dead
        if plant_level_row[0]['plant_nourishment'] < 0:
            plant_level_row = await db(
                """UPDATE plant_levels SET
                plant_nourishment=LEAST(-plant_levels.plant_nourishment, plant_levels.plant_nourishment),
                last_water_time=$3 WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)
                RETURNING *""",
                user_id, plant_name, dt.utcnow(),
            )

        # Increase the nourishment otherwise
        else:
            plant_level_row = await db(
                """UPDATE plant_levels
                SET plant_nourishment=LEAST(plant_levels.plant_nourishment+1, $4),
                last_water_time=$3, notification_sent=FALSE
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *""",
                user_id, plant_name, dt.utcnow(), plant_data.max_nourishment_level,
            )

        # Add to the user exp if the plant is alive
        user_plant_data: PlantLevelsRow = plant_level_row[0]
        gained_experience: int = 0
        original_gained_experience: int = 0
        multipliers: List[WaterPlantMultiplier] = []
        additional_text: List[str] = []
        voted_on_topgg: bool = False
        user_is_premium: bool = False

        # See if the user is premium
        try:
            await utils.checks.has_premium().predicate(vbu.web.WebContext(self.bot, waterer_id))
            user_is_premium = True
        except commands.CheckFailure:
            pass

        # Disconnect from the database so we don't have hanging connections open while
        # making our Top.gg web request
        await db.disconnect()

        # And now let's water the damn thing
        if user_plant_data['plant_nourishment'] > 0:

            # Get the experience that they should have gained
            total_gained_experience = plant_data.get_experience()
            original_gained_experience = total_gained_experience

            # See if we want to give them a premium bonus
            if user_is_premium:
                multipliers.append({
                    "multiplier": 2.0,
                    "text": "You're subscribed to Flower Premium! :D",
                })

            # See if we want to give them a 30 second water-time bonus
            if dt.utcnow() - last_water_time - water_cooldown_period <= timedelta(seconds=30):
                multipliers.append({
                    "multiplier": 1.5,
                    "text": vbu.format(
                        f"You watered within 30 seconds of {{0:pronoun,your,their}} plant's cooldown resetting.",
                        waterer_is_owner,
                    ),
                })

            # See if we want to give the new owner bonus
            if plant_level_row[0]['user_id'] != plant_level_row[0]['original_owner_id']:
                multipliers.append({
                    "multiplier": 1.05,
                    "text": vbu.format(
                        f"You watered a plant that {{0:pronoun,you,they}} got from a trade.",
                        waterer_is_owner,
                    ),
                })

            # See if we want to give them the voter bonus
            user_voted_api_request: bool = False
            try:
                user_voted_api_request = await asyncio.wait_for(self.get_user_voted(waterer_id), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            if user_voted_api_request:
                bot_client_id = self.bot.config['oauth']['client_id']
                multipliers.append({
                    "multiplier": 1.1,
                    "text": f"You [voted for the bot](https://top.gg/bot/{bot_client_id}/vote) on Top.gg.",
                })
                voted_on_topgg = True

            # See if we want to give them the plant longevity bonus
            if user_plant_data['plant_adoption_time'] < dt.utcnow() - timedelta(days=7):
                multipliers.append({
                    "multiplier": 1.2,
                    "text": vbu.format(
                        f"{{0:pronoun,Your,Their}} plant has been alive for longer than a week.",
                        waterer_is_owner,
                    ),
                })

            # See if we want to give them the plant longevity bonus
            if user_plant_data['immortal']:
                multipliers.append({
                    "multiplier": 0.5,
                    "text": vbu.format(
                        f"{{0:pronoun,Your,Their}} plant is immortal.",
                        waterer_is_owner,
                    ),
                })

            # Add the actual multiplier values
            for m in multipliers:
                total_gained_experience *= m['multiplier']

            # Update db
            total_gained_experience = int(total_gained_experience)
            async with vbu.Database() as db:

                # Give exp to everyone we care about
                if waterer_is_owner:
                    gained_experience = total_gained_experience
                    user_experience_row: UserSettingsRows = await db(
                        """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                        DO UPDATE SET user_experience=user_settings.user_experience+$2 RETURNING *""",
                        user_id, gained_experience,
                    )
                else:
                    gained_experience = int(total_gained_experience * 0.8)
                    owner_gained_experience = int(total_gained_experience - gained_experience)
                    async with db.transaction() as trans:
                        user_experience_row: UserSettingsRows = await trans(
                            """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                            DO UPDATE SET user_experience=user_settings.user_experience+$2 RETURNING *""",
                            waterer_id, gained_experience,
                        )
                        await trans(
                            """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                            DO UPDATE SET user_experience=user_settings.user_experience+$2""",
                            user_id, owner_gained_experience,
                        )

                # Update the user achievements
                await db(
                    """INSERT INTO plant_achievement_counts (user_id, plant_type, max_plant_nourishment) VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, plant_type) DO UPDATE SET
                    max_plant_nourishment=GREATEST(plant_achievement_counts.max_plant_nourishment,
                    excluded.max_plant_nourishment)""",
                    user_id, user_plant_data['plant_type'], user_plant_data['plant_nourishment']
                )

        # Send an output
        else:
            return self.get_water_plant_dict(vbu.format(
                "You sadly pour water into the dry soil of {0:pronoun,your,their} wilting plant :c",
                waterer_is_owner,
            ))

        # Set up our output text
        gained_exp_string: str
        if gained_experience == original_gained_experience:
            gained_exp_string = f"**{gained_experience}**"
        else:
            gained_exp_string = f"~~{original_gained_experience}~~ **{gained_experience}**"
        output_lines: List[str] = []
        if plant_data.get_nourishment_display_level(user_plant_data['plant_nourishment']) > plant_data.get_nourishment_display_level(user_plant_data['plant_nourishment'] - 1):
            output_lines.append(vbu.format(
                (
                    f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, "
                    f"gaining you {gained_exp_string} experience, watching {{0:pronoun,your,their}} plant grow!~"
                ),
                waterer_is_owner,
            ))
        else:
            output_lines.append((
                    f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, "
                    f"gaining you {gained_exp_string} experience~"
            ))
        for obj in multipliers:
            output_lines.append(f"**{obj['multiplier']}x**: {obj['text']}")
        for t in additional_text:
            output_lines.append(t)

        # And now we output all the information that we need for this to be an API route
        return self.get_water_plant_dict(
            text="\n".join(output_lines),
            success=True,
            gained_experience=gained_experience,
            new_nourishment_level=plant_level_row[0]['plant_nourishment'],
            new_user_experience=user_experience_row[0]['user_experience'],
            voted_on_topgg=voted_on_topgg,
            multipliers=multipliers,
        )

    @commands.command(
        aliases=['waterplant', 'w'],
        cooldown_after_parsing=True,
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    type=discord.ApplicationCommandOptionType.user,
                    required=False,
                    description="The user whose plant you want to water.",
                ),
                discord.ApplicationCommandOption(
                    name="plant_name",
                    type=discord.ApplicationCommandOptionType.string,
                    required=False,
                    description="The plant that you want to water.",
                ),
            ],
        ),
    )
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.defer()
    async def water(self, ctx: vbu.Context, user: Optional[discord.User] = None, *, plant_name: Optional[str] = None):
        """
        Increase the growth level of your plant.
        """

        user: discord.User = user or ctx.author  # type: ignore

        # Make sure there's a plant name
        if plant_name is None:
            return await ctx.send("You need to specify a plant to water.")

        # Let's run all the bullshit
        item = await self.water_plant_backend(user.id, plant_name, ctx.author.id)
        if item['success'] is False:
            return await ctx.send(item['text'])
        output_lines = item['text'].split("\n")

        # Make initial embed
        embed = vbu.Embed(use_random_colour=True, description=output_lines[0])

        # Add multipliers
        if len(output_lines) > 1:
            embed.add_field(
                "Multipliers",
                "\n".join([i.strip('') for i in output_lines[1:]]),
                inline=False,
            )

        # Add "please vote for Flower" footer
        counter = 0
        ctx.bot.set_footer_from_config(embed)

        def check(footer_text) -> bool:
            if item['voted_on_topgg']:
                return 'vote' in footer_text
            return 'vote' not in footer_text
        while counter < 100 and check(embed.footer.text.lower()):  # type: ignore - ignore MaybeEmpty[str]
            ctx.bot.set_footer_from_config(embed)
            counter += 1

        # Send message
        return await ctx.send(embeds=[embed])

    async def delete_plant_backend(
            self,
            user_id: int,
            plant_name: str) -> Optional[PlantLevelsRow]:
        """
        The backend function for deleting a plant from the database. Either returns the deleted
        plant's data, or None.

        Parameters
        -----------
        user_id: int
            The ID of the user to affect.
        plant_name: str
            The name of the user's plant.

        Returns
        --------
        Optional[dict]
            Either the deleted plant row, or ``None`` if the plant didn't exist.
        """

        async with vbu.Database() as db:
            data = await db(
                "DELETE FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *",
                user_id, plant_name,
            )
        if not data:
            return None
        return data[0]

    @commands.command(
        aliases=['deleteplant', 'deleteflower'],
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="plant_name",
                    type=discord.ApplicationCommandOptionType.string,
                    description="The plant that you want to delete.",
                ),
            ],
        ),
    )
    @commands.bot_has_permissions(send_messages=True)
    async def delete(self, ctx: vbu.Context, *, plant_name: str):
        """
        Deletes your plant from the database.
        """

        # Make sure they want to
        interaction_id = str(uuid.uuid4())
        await ctx.send(
            f"Are you sure you want to delete **{plant_name}** from your inventory?",
            components=(buttons := discord.ui.MessageComponents.boolean_buttons(
                yes_id=f"{interaction_id} YES",
                no_id=f"{interaction_id} NO",
            )),
        )
        try:
            check = lambda p: p.user.id == ctx.author.id and p.custom_id.startswith(interaction_id)
            interaction = await self.bot.wait_for("component_interaction", check=check, timeout=60 * 2)
            await interaction.response.edit_message(
                components=buttons.disable_components(),
            )
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out waiting for you to confirm plant deletion, {ctx.author.mention}.")

        # See if they said no
        if interaction.custom_id.split(" ")[-1] == "NO":
            return await interaction.followup.send("Alright, cancelled deletion")

        # Attempt to delete the plant
        data = await self.delete_plant_backend(ctx.author.id, plant_name)
        if not data:
            return await interaction.followup.send(
                f"You have no plant names **{plant_name}**!",
                allowed_mentions=discord.AllowedMentions.none(),
            )

        # And respond
        return await interaction.followup.send(f"Done - you've deleted your {data['plant_type'].replace('_', ' ')}.")

    @vbu.command(
        aliases=['renameplant'],
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="before",
                    type=discord.ApplicationCommandOptionType.string,
                    description="The name of the plant that you want to rename.",
                ),
                discord.ApplicationCommandOption(
                    name="after",
                    type=discord.ApplicationCommandOptionType.string,
                    description="The name that you want to set the plant to.",
                ),
            ],
        ),
    )
    @commands.is_slash_command()
    async def rename(self, ctx: vbu.Context, before: str, after: str):
        """
        Gives a new name to your plant. Use "quotes" if your plant has a space in its name.
        """

        # Make sure some names were provided
        after = utils.PlantType.validate_name(after)
        if not after:
            raise vbu.errors.MissingRequiredArgumentString("after")
        if len(after) > 50 or len(after) == 0:
            return await ctx.send("That name is too long! Please give another one instead!")

        # See about changing the name
        async with vbu.Database() as db:

            # Make sure the given name exists
            plant_has_before_name: PlantLevelsRows = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                ctx.author.id, before,
            )
            if not plant_has_before_name:
                return await ctx.send(
                    f"You have no plants with the name **{before}**.",
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            # Make sure they own the plant
            if plant_has_before_name[0]['original_owner_id'] != ctx.author.id:
                return await ctx.send("You can't rename plants that you didn't own originally.")

            # Make sure they aren't trying to rename to a currently existing name
            plant_name_exists = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                ctx.author.id, after,
            )
            if plant_name_exists:
                return await ctx.send(
                    f"You already have a plant with the name **{after}**!",
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            # Update plant name
            await db(
                "UPDATE plant_levels SET plant_name=$3 WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                ctx.author.id, before, after,
            )

        # And done
        await ctx.send("Done!~")

    async def revive_plant_backend(
            self,
            user_id: int,
            plant_name: str) -> Tuple[str, bool]:
        """
        The backend for reviving a plant.
        Returns a response string and whether or not the revive succeeded, as a tuple.
        """

        async with vbu.Database() as db:

            # See if they have enough revival tokens
            inventory_rows = await db(
                "SELECT * FROM user_inventory WHERE user_id=$1 AND item_name='revival_token'",
                user_id,
            )
            if not inventory_rows or inventory_rows[0]['amount'] < 1:
                return f"You don't have any revival tokens, <@{user_id}>! :c", False

            # See if the plant they specified exists
            plant_rows = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                user_id, plant_name,
            )
            if not plant_rows:
                return f"You have no plants named **{plant_name}**.", False

            # See if the plant they specified is dead
            if plant_rows[0]['plant_nourishment'] >= 0:
                return f"Your **{plant_rows[0]['plant_name']}** plant isn't dead!", False

            # Revive the plant and remove a token
            async with db.transaction() as trans:
                await trans.call(
                    """UPDATE user_inventory SET amount=user_inventory.amount-1 WHERE user_id=$1
                    AND item_name='revival_token'""",
                    user_id,
                )
                await trans.call(
                    """UPDATE plant_levels SET plant_nourishment=1, last_water_time=$3,
                    plant_adoption_time=TIMEZONE('UTC', NOW()) WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)""",
                    user_id, plant_name, dt.utcnow() - timedelta(**self.bot.config['plants']['water_cooldown'])
                )
                await trans.call(
                    """INSERT INTO user_achievement_counts (user_id, revive_count) VALUES ($1, 1)
                    ON CONFLICT (user_id) DO UPDATE SET
                    revive_count=user_achievement_counts.revive_count+excluded.revive_count""",
                    user_id,
                )

        # And now we done
        p = plant_rows[0]
        return f"Revived **{p['plant_name']}**, your {p['plant_type'].replace('_', ' ')}! :D", True

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="plant_name",
                    description="The name of the plant that you want to revive.",
                    type=discord.ApplicationCommandOptionType.string,
                ),
            ],
        ),
    )
    @commands.bot_has_permissions(send_messages=True)
    async def revive(self, ctx: vbu.Context, *, plant_name: str):
        """
        Use one of your revival tokens to be able to revive your plant.
        """

        response, _ = await self.revive_plant_backend(ctx.author.id, plant_name)
        return await ctx.send(response, allowed_mentions=discord.AllowedMentions.none())

    @vbu.command(
        aliases=['immortalise'],
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                "en-GB": "immortalise",
            },
            options=[
                discord.ApplicationCommandOption(
                    name="plant_name",
                    description="The name of the plant that you want to immortalize.",
                    type=discord.ApplicationCommandOptionType.string,
                ),
            ],
        ),
    )
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    async def immortalize(self, ctx: vbu.Context, *, plant_name: str):
        """
        Makes one of your plants immortal.
        """

        user_id = ctx.author.id
        async with vbu.Database() as db:

            # See if they have enough revival tokens
            inventory_rows = await db(
                "SELECT * FROM user_inventory WHERE user_id=$1 AND item_name='immortal_plant_juice'",
                user_id,
            )
            if not inventory_rows or inventory_rows[0]['amount'] < 1:
                return await ctx.send(f"You don't have any immortal plant juice, <@{user_id}>! :c")

            # See if the plant they specified exists
            plant_rows = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                user_id, plant_name,
            )
            if not plant_rows:
                return await ctx.send(f"You have no plants named **{plant_name}**.")

            # See if the plant they specified is dead
            if plant_rows[0]['plant_nourishment'] <= 0:
                return await ctx.send("You can't immortalize a dead plant!")

        # Make sure they want to
        component_id = str(uuid.uuid4())
        await ctx.send(
            (
                "By making a plant immortal, you halve the amount of exp you get from it. "
                "Are you sure this is something you want to do?"
            ),
            components=discord.ui.MessageComponents.boolean_buttons(
                yes_id=f"{component_id} YES",
                no_id=f"{component_id} NO",
            ),
        )
        try:
            check = lambda p: p.user.id == ctx.author.id and p.custom_id.startswith(component_id)
            payload = await self.bot.wait_for("component_interaction", check=check, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out waiting for you to confirm plant immortality, {ctx.author.mention}.")

        # Check their reaction
        if payload.custom_id == "NO":
            return await payload.response.edit_message(
                content="Alright, cancelled making your plant immortal :<",
                components=None,
            )
        await payload.response.defer_update()

        # Okay they're sure
        async with vbu.Database() as db:

            # Revive the plant and remove a token
            async with db.transaction() as trans:
                await trans(
                    """UPDATE user_inventory SET amount=user_inventory.amount-1
                    WHERE user_id=$1 AND item_name='immortal_plant_juice'""",
                    user_id,
                )
                await trans(
                    """UPDATE plant_levels SET immortal=true,
                    plant_adoption_time=TIMEZONE('UTC', NOW()) WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)""",
                    user_id, plant_name
                )
                await trans(
                    """INSERT INTO user_achievement_counts (user_id, immortalize_count) VALUES ($1, 1)
                    ON CONFLICT (user_id) DO UPDATE SET
                    immortalize_count=user_achievement_counts.immortalize_count+excluded.immortalize_count""",
                    user_id,
                )

        # And now we done
        return await payload.followup.send(
            f"Immortalized **{plant_rows[0]['plant_name']}**, your {plant_rows[0]['plant_type'].replace('_', ' ')}! :D",
        )

def setup(bot: vbu.Bot):
    x = PlantCareCommands(bot)
    bot.add_cog(x)
