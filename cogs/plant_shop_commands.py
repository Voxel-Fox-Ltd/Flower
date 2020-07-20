import asyncio
from datetime import datetime as dt
import os
import glob
import json

import discord
from discord.ext import commands

from cogs import utils


class PlantShopCommands(utils.Cog):

    HARD_PLANT_CAP = 10
    PLANT_POT_PRICE = 50

    @classmethod
    def get_points_for_plant_pot(cls, current_limit:str):
        """Get the amount of points needed to get the next level of pot"""

        return int(cls.PLANT_POT_PRICE * (3 ** (current_limit - 1)))

    @commands.command(cls=utils.Command)
    @commands.is_owner()
    async def reloadplants(self, ctx:utils.Context):
        """Shows you the available plants"""

        # Load up all the plants
        plant_directories = glob.glob("images/plants/[!_]*/")
        plant_names = [i.strip(os.sep).split(os.sep)[-1] for i in plant_directories]
        available_plants = []

        # Check the plant JSON file
        for name in plant_names:
            with open(f"images/plants/{name}/pack.json") as a:
                data = json.load(a)
            data.update({"name": name})
            available_plants.append(data)

        # Dictionary it up
        self.bot.plants.clear()
        self.bot.plants = {i['name']: utils.PlantType(**i) for i in available_plants}
        return await ctx.send("Reloaded.")

    @commands.command(cls=utils.Command, aliases=['getplant', 'shop', 'getpot', 'newpot'])
    async def newplant(self, ctx:utils.Context):
        """Shows you the available plants"""

        # Get the experience
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", ctx.author.id)
            plant_level_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", ctx.author.id)
        if user_rows:
            user_experience = user_rows[0]['user_experience']
            plant_limit = user_rows[0]['plant_limit']
        else:
            user_experience = 0
            plant_limit = 1
        # if len(plant_level_rows) >= plant_limit and user_experience < self.get_points_for_plant_pot(plant_limit):
        #     return await ctx.send(f"You can only have {plant_limit} plant{'s' if plant_limit > 1 else ''}, and you need {self.get_points_for_plant_pot(plant_limit)} exp to get a new pot (you currently have {user_experience} exp)! :c")

        # See what plants are available
        text_rows = [f"What seeds would you like to spend your experience to buy, {ctx.author.mention}? You currently have **{user_experience} exp**."]
        for plant in sorted(list(self.bot.plants.values())):
            if plant.visible is False or plant.available is False:
                continue
            if plant.required_experience <= user_experience and len(plant_level_rows) < plant_limit:
                text_rows.append(f"**{plant.name.capitalize().replace('_', ' ')}** - {plant.required_experience} exp")
            else:
                text_rows.append(f"~~**{plant.name.capitalize().replace('_', ' ')}** - {plant.required_experience} exp~~")

        # See what other stuff is available
        text_rows.append("")
        text_rows.append("Would you like to buy a new item?")
        if user_experience >= self.get_points_for_plant_pot(plant_limit) and plant_limit < self.HARD_PLANT_CAP:
            text_rows.append(f"**Pot** - {self.get_points_for_plant_pot(plant_limit)} exp")
        else:
            text_rows.append(f"~~**Pot** - {self.get_points_for_plant_pot(plant_limit)} exp~~")
        await ctx.send('\n'.join(text_rows))

        # Wait for them to respond
        try:
            plant_type_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel == ctx.channel and m.content, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out asking for plant type {ctx.author.mention}.")

        # See if they want a plant pot
        given_response = plant_type_message.content.lower().replace(' ', '_')
        if given_response == "pot":
            if plant_limit >= self.HARD_PLANT_CAP:
                return await ctx.send(f"You're already at the maximum amount of pots, {ctx.author.mention}! :c")
            if user_experience >= self.get_points_for_plant_pot(plant_limit):
                async with self.bot.database() as db:
                    await db(
                        """INSERT INTO user_settings (user_id, plant_limit, user_experience) VALUES ($1, 2, $2) ON CONFLICT (user_id) DO UPDATE
                        SET plant_limit=user_settings.plant_limit+1, user_experience=user_settings.user_experience-excluded.user_experience""",
                        ctx.author.id, self.get_points_for_plant_pot(plant_limit)
                    )
                return await ctx.send(f"Given you another plant pot, {ctx.author.mention}!")
            else:
                return await ctx.send(f"You don't have the required experience to get a new plant pot, {ctx.author.mention} :c")

        # See if they want a plant
        try:
            plant_type = self.bot.plants[given_response]
        except KeyError:
            return await ctx.send(f"`{plant_type_message.content}` isn't an available plant name, {ctx.author.mention}!", allowed_mentions=discord.AllowedMentions(users=[ctx.author], roles=False, everyone=False))
        if plant_type.available is False:
            return await ctx.send(f"**{plant_type.name.replace('_', ' ').capitalize()}** plants are unavailable right now, {ctx.author.mention} :c")
        if plant_type.required_experience > user_experience:
            return await ctx.send(f"You don't have the required experience to get a **{plant_type.name.replace('_', ' ')}**, {ctx.author.mention} :c")
        if len(plant_level_rows) >= plant_limit:
            return await ctx.send(f"You don't have enough plant pots to be able to get a **{plant_type.name.replace('_', ' ')}**, {ctx.author.mention} :c")

        # Get a name for the plant
        await ctx.send("What name do you want to give your plant?")
        try:
            plant_name_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel == ctx.channel and m.content, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out asking for plant name {ctx.author.mention}.")

        # Save that to database
        async with self.bot.database() as db:
            plant_name_exists = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                ctx.author.id, plant_name_message.content
            )
            if plant_name_exists:
                return await ctx.send(f"You've already used the name `{plant_name_message.content}` for one of your other plants - please run this command again to give a new one!", allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))
            await db(
                """INSERT INTO plant_levels (user_id, plant_name, plant_type, plant_nourishment, last_water_time)
                VALUES ($1, $2, $3, 0, $4) ON CONFLICT (user_id, plant_name) DO UPDATE
                SET plant_nourishment=0, last_water_time=$4""",
                ctx.author.id, plant_name_message.content, plant_type.name, dt(2000, 1, 1),
            )
            await db(
                "UPDATE user_settings SET user_experience=user_settings.user_experience-$2 WHERE user_id=$1",
                ctx.author.id, plant_type.required_experience,
            )
        # self.bot.get_command("water").reset_cooldown(ctx)
        await ctx.send(f"Planted your **{plant_type.name.replace('_', ' ')}** seeds!")


def setup(bot):
    x = PlantShopCommands(bot)
    bot.add_cog(x)
