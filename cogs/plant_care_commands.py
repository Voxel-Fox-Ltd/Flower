from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands, tasks

from cogs import utils


class PlantCareCommands(utils.Cog):

    PLANT_DEATH_TIMEOUT = {
        'days': 3,
    }
    PLANT_WATER_COOLDOWN = {
        'minutes': 15,
    }

    def __init__(self, bot):
        super().__init__(bot)
        self.plant_death_timeout_loop.start()

    def cog_unload(self):
        self.plant_death_timeout_loop.cancel()

    @tasks.loop(minutes=1)
    async def plant_death_timeout_loop(self):
        """Loop to see if we should kill off any plants that may have been timed out"""

        async with self.bot.database() as db:
            await db(
                """UPDATE plant_levels SET plant_nourishment=-plant_levels.plant_nourishment WHERE
                plant_nourishment > 0 AND last_water_time + $2 < $1""",
                dt.utcnow(), timedelta(**self.PLANT_DEATH_TIMEOUT),
            )

    @staticmethod
    def validate_name(name:str):
        """Validates the name of a plant
        Input is the name, output is a (bool, Optional[str]) tuple - the boolean is whether their given name is valid, and the
        string is their plant's name. More often than not that'll be the same as the input, but quote marks are stripped from the
        name before being given as an output
        """

        name_is_valid = True
        name = name.strip('"“”\'')
        if '\n' in name:
            name_is_valid = False
        elif len(name) <= 0:
            name_is_valid = False
        elif len(name) > 50:
            name_is_valid = False
        return name_is_valid, name

    @commands.command(cls=utils.Command, aliases=['water'], cooldown_after_parsing=True)
    @commands.bot_has_permissions(send_messages=True)
    async def waterplant(self, ctx:utils.Context, *, plant_name:str):
        """Increase the growth level of your plant"""

        # Decide on our plant type - will be ignored if there's already a plant
        db = await self.bot.database.get_connection()

        # See if they have a plant available
        plant_level_row = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, plant_name)
        if not plant_level_row:
            await db.disconnect()
            return await ctx.send(f"You don't have a plant with the name **{plant_name}**! Run `{ctx.prefix}getplant` to plant some new seeds, or `{ctx.prefix}plants` to see the list of plants you have already!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        plant_data = self.bot.plants[plant_level_row[0]['plant_type']]

        # See if they're allowed to water things
        if plant_level_row[0]['last_water_time'] + timedelta(**self.PLANT_WATER_COOLDOWN) > dt.utcnow() and ctx.author.id not in self.bot.owner_ids:
            await db.disconnect()
            timeout = utils.TimeValue(((plant_level_row[0]['last_water_time'] + timedelta(**self.PLANT_WATER_COOLDOWN)) - dt.utcnow()).total_seconds())
            return await ctx.send(f"You need to wait another {timeout.clean_spaced} to be able water your {plant_level_row[0]['plant_type'].replace('_', ' ')}.")

        # See if the plant should be dead
        if plant_level_row[0]['plant_nourishment'] < 0:
            plant_level_row = await db(
                """UPDATE plant_levels SET
                plant_nourishment=LEAST(-plant_levels.plant_nourishment, plant_levels.plant_nourishment), last_water_time=$3
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *""",
                ctx.author.id, plant_name, dt.utcnow(),
            )

        # Increase the nourishment otherwise
        else:
            plant_level_row = await db(
                """UPDATE plant_levels
                SET plant_nourishment=LEAST(plant_levels.plant_nourishment+1, $4), last_water_time=$3
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *""",
                ctx.author.id, plant_name, dt.utcnow(), plant_data.max_nourishment_level,
            )

        # Add to the user exp if the plant is alive
        plant_nourishment = plant_level_row[0]['plant_nourishment']
        gained_experience = 0
        if plant_nourishment > 0:

            # Get the experience that they should have gained
            gained_experience = plant_data.get_experience()

            # See if we want to give them a 30 second water-time bonus
            if plant_level_row[0]['last_water_time'] + timedelta(seconds=30) <= dt.utcnow():
                gained_experience = int(gained_experience * 1.5)

            # Update db
            await db(
                """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                DO UPDATE SET user_experience=user_settings.user_experience+$2""",
                ctx.author.id, gained_experience,
            )

        # Send an output
        await db.disconnect()
        if plant_nourishment < 0:
            return await ctx.send("You sadly pour water into the dry soil of your silently wilting plant :c")
        elif plant_data.get_nourishment_display_level(plant_nourishment) > plant_data.get_nourishment_display_level(plant_nourishment - 1):
            return await ctx.send(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_experience} experience, watching your plant grow!~")
        else:
            return await ctx.send(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_experience} experience~")

    @commands.command(cls=utils.Command, aliases=['delete'])
    @commands.bot_has_permissions(send_messages=True)
    async def deleteplant(self, ctx:utils.Context, *, plant_name:str):
        """Deletes your plant from the database"""

        async with self.bot.database() as db:
            data = await db("DELETE FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *", ctx.author.id, plant_name)
        if not data:
            return await ctx.send(f"You have no plant names **{plant_name}**!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        return await ctx.send(f"Done - you've deleted your {data[0]['plant_type'].replace('_', ' ')}.")

    @commands.command(cls=utils.Command, aliases=['rename'])
    @commands.bot_has_permissions(send_messages=True)
    async def renameplant(self, ctx:utils.Context, before:str, *, after:str):
        """Gives a new name to your plant. Use "quotes" if your plant has a space in its name."""

        # Make sure some names were provided
        _, name = self.validate_name(after)
        if not after:
            raise utils.MissingRequiredArgumentString("after")
        if len(before) > 50 or len(before) == 0:
            return await ctx.send(f"You have no plants with the name **{before}**.", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        if len(after) > 50 or len(after) == 0:
            await ctx.send("That name is too long! Please give another one instead!")
            return
        if '\n' in after:
            await ctx.send("You can't have names with multiple lines in them! Please give another one instead!")

        # See about changing the name
        async with self.bot.database() as db:

            # Make sure the given name exists
            plant_has_before_name = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before)
            if not plant_has_before_name:
                return await ctx.send(f"You have no plants with the name **{before}**.", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

            # Make sure they aren't trying to rename to a currently existing name
            plant_name_exists = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, after)
            if plant_name_exists:
                return await ctx.send(f"You already have a plant with the name **{after}**!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

            # Update plant name
            await db("UPDATE plant_levels SET plant_name=$3 WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before, after)
        await ctx.send("Done!~")

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    async def revive(self, ctx:utils.Context, *, plant_name:str):
        """Use one of your revival tokens to be able to revive your plant"""

        async with self.bot.database() as db:

            # See if they have enough revival tokens
            inventory_rows = await db("SELECT * FROM user_inventory WHERE user_id=$1 AND item_name='revival_token'", ctx.author.id)
            if not inventory_rows or inventory_rows[0]['amount'] < 1:
                return await ctx.send(f"You don't have any revival tokens, {ctx.author.mention}! :c")

            # See if the plant they specified exists
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, plant_name)
            if not plant_rows:
                return await ctx.send(f"You have no plants named **{plant_name}**.", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

            # See if the plant they specified is dead
            if plant_rows[0]['plant_nourishment'] >= 0:
                return await ctx.send(f"Your **{plant_rows[0]['plant_name']}** plant isn't dead!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

            # Revive the plant and remove a token
            await db.start_transaction()
            await db("UPDATE user_inventory SET amount=user_inventory.amount-1 WHERE user_id=$1 AND item_name='revival_token'", ctx.author.id)
            await db(
                """UPDATE plant_levels SET plant_nourishment=1, last_water_time=TIMEZONE('UTC', NOW()) - INTERVAL '15 MINUTES'
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)""",
                ctx.author.id, plant_name
            )
            await db.commit_transaction()

        # And now we done
        return await ctx.send(f"Revived **{plant_rows[0]['plant_name']}**, your {plant_rows[0]['plant_type'].replace('_', ' ')}! :D")


def setup(bot:utils.Bot):
    x = PlantCareCommands(bot)
    bot.add_cog(x)
