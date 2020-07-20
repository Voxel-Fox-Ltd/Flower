from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands, tasks

from cogs import utils


class PlantCareCommands(utils.Cog):

    PLANT_DEATH_TIMEOUT = {
        'days': 2,
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

    @commands.command(cls=utils.Command, aliases=['water'], cooldown_after_parsing=True)
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
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)
                RETURNING plant_name, plant_nourishment""",
                ctx.author.id, plant_name, dt.utcnow(),
            )

        # Increase the nourishment otherwise
        else:
            plant_level_row = await db(
                """UPDATE plant_levels
                SET plant_nourishment=LEAST(plant_levels.plant_nourishment+1, $4), last_water_time=$3
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)
                RETURNING plant_name, plant_nourishment""",
                ctx.author.id, plant_name, dt.utcnow(), plant_data.max_nourishment_level,
            )

        # Add to the user exp
        plant_nourishment = plant_level_row[0]['plant_nourishment']
        if plant_nourishment > 0:
            gained_experience = plant_data.get_experience()
            await db(
                """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                DO UPDATE SET user_experience=user_settings.user_experience+$2""",
                ctx.author.id, gained_experience,
            )
        else:
            gained_experience = 0
        await db.disconnect()

        # Send an output
        if plant_nourishment < 0:
            await ctx.send("You sadly pour water into the dry soil of your silently wilting plant :c")
        elif plant_data.get_nourishment_display_level(plant_nourishment) > plant_data.get_nourishment_display_level(plant_nourishment - 1):
            await ctx.send(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_experience} experience, watching your plant grow!~")
        else:
            await ctx.send(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_experience} experience~")

    @commands.command(cls=utils.Command, aliases=['delete'])
    async def deleteplant(self, ctx:utils.Context, *, plant_name:str):
        """Deletes your plant from the database"""

        async with self.bot.database() as db:
            await db("DELETE FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, plant_name)
        await ctx.send("Done.")

    @commands.command(cls=utils.Command, aliases=['rename'])
    async def renameplant(self, ctx:utils.Context, before:str, *, after:str):
        """Deletes your plant from the database"""
                           
        if '"' in words:
            await ctx.send("No, you fucking idiot!")
        else:    
                         
                          
            async with self.bot.database() as db:
                plant_has_before_name = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before)
                if not plant_has_before_name:
                    return await ctx.send(f"You have no plants with the name `{before}`.", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
                await db("UPDATE plant_levels SET plant_name=$3 WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before, after)
            await ctx.send("Done!~")

    @commands.command(cls=utils.Command, aliases=['exp', 'points'])
    async def experience(self, ctx:utils.Context, user:utils.converters.UserID=None):
        """Shows you how much experience a user has"""

        user = discord.Object(user) if user else ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", user.id)
        if user_rows:
            exp_value = user_rows[0]['user_experience']
        else:
            exp_value = 0
        return await ctx.send(f"<@{user.id}> has **{exp_value:,}** experience.", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))

    @commands.command(cls=utils.Command, aliases=['giveexp', 'givepoints'])
    async def giveexperience(self, ctx:utils.Context, user:discord.Member, amount:int):
        """Transfers some of your experience to another user"""

        if amount <= 0:
            return await ctx.send("You need to give an amount above zero.")
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", ctx.author.id)
            if not user_rows:
                return await ctx.send("You don't have enough experience to make that transfer! :c")
            if user_rows[0]['user_experience'] < amount:
                return await ctx.send("You don't have enough experience to make that transfer! :c")
            await db.start_transaction()
            await db("UPDATE user_settings SET user_experience=user_settings.user_experience-$2 WHERE user_id=$1", ctx.author.id, amount)
            await db(
                """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                DO UPDATE SET user_experience=user_settings.user_experience+excluded.user_experience""",
                user.id, amount
            )
            await db.commit_transaction()
        return await ctx.send(f"Transferred **{amount:,}** exp from {ctx.author.mention} to <@{user.id}>!", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))

    @commands.command(cls=utils.Command, aliases=['list'])
    async def plants(self, ctx:utils.Context, user:utils.converters.UserID=None):
        """Shows you all the plants that a given user has"""

        user = discord.Object(user) if user else ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", user.id)
        plant_names = sorted([(i['plant_name'], i['plant_type'], i['plant_nourishment']) for i in user_rows])
        if not plant_names:
            return await ctx.send(f"<@{user.id}> has no plants :c", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))
        plant_output_string = []
        for i in plant_names:
            if i[2] >= 0:
                plant_output_string.append(f"**{i[0]}** ({i[1].replace('_', ' ')}, nourishment level {i[2]}/{self.bot.plants[i[1]].max_nourishment_level})")
            else:
                plant_output_string.append(f"**{i[0]}** ({i[1].replace('_', ' ')}, dead)")
        return await ctx.send(
            f"<@{user.id}> has the following:\n" + '\n'.join(plant_output_string),
            allowed_mentions=discord.AllowedMentions(users=[ctx.author], everyone=False, roles=False)
        )


def setup(bot:utils.Bot):
    x = PlantCareCommands(bot)
    bot.add_cog(x)
