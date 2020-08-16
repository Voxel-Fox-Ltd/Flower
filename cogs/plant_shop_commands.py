import asyncio
from datetime import datetime as dt
import os
import glob
import json
import collections
import random

import discord
from discord.ext import commands

from cogs import utils


class PlantShopCommands(utils.Cog):

    HARD_PLANT_CAP = 10
    PLANT_POT_PRICE = 50
    REVIVAL_TOKEN_PRICE = 300
    LEVEL_ZERO_PLANT_NAME = "blue_daisy"

    @classmethod
    def get_points_for_plant_pot(cls, current_limit:str):
        """Get the amount of points needed to get the next level of pot"""

        return int(cls.PLANT_POT_PRICE * (3 ** (current_limit - 1)))

    async def get_available_plants(self, user_id:int) -> dict:
        """Get the available plants for a given user at each given level"""

        async with self.bot.database() as db:

            # Check what plants they have available
            plant_shop_rows = await db("SELECT * FROM user_available_plants WHERE user_id=$1", user_id)

            # If they don't have any available plants, generate new ones for the shop
            if not plant_shop_rows or plant_shop_rows[0]['last_shop_timestamp'].month != dt.utcnow().month:
                possible_available_plants = collections.defaultdict(list)
                for item in self.bot.plants.values():
                    if item.available is False:
                        continue
                    possible_available_plants[item.plant_level].append(item)
                available_plants = {}
                for level, plants in possible_available_plants.items():
                    available_plants[level] = random.choice(plants)
                available_plants[0] = self.bot.plants['blue_daisy']
                await db(
                    """INSERT INTO user_available_plants VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (user_id) DO UPDATE SET
                    last_shop_timestamp=excluded.last_shop_timestamp, plant_level_1=excluded.plant_level_1, plant_level_2=excluded.plant_level_2,
                    plant_level_3=excluded.plant_level_3, plant_level_4=excluded.plant_level_4, plant_level_5=excluded.plant_level_5,
                    plant_level_6=excluded.plant_level_6""",
                    user_id, dt.utcnow(), available_plants[1].name, available_plants[2].name, available_plants[3].name, available_plants[4].name,
                    available_plants[5].name, available_plants[6].name,
                )

            # They have available plants, format into new dictionary
            else:
                available_plants = {
                    0: self.bot.plants['blue_daisy'],
                    1: self.bot.plants[plant_shop_rows[0]['plant_level_1']],
                    2: self.bot.plants[plant_shop_rows[0]['plant_level_2']],
                    3: self.bot.plants[plant_shop_rows[0]['plant_level_3']],
                    4: self.bot.plants[plant_shop_rows[0]['plant_level_4']],
                    5: self.bot.plants[plant_shop_rows[0]['plant_level_5']],
                    6: self.bot.plants[plant_shop_rows[0]['plant_level_6']],
                }
        return available_plants

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

    @commands.command(cls=utils.Command, aliases=['getplant', 'getpot', 'newpot', 'newplant'])
    async def shop(self, ctx:utils.Context):
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
        available_item_count = 0  # Used to make sure we can continue the command

        # See what plants are available
        if len(plant_level_rows) >= plant_limit:
            text_rows = [f"You currently have no available plant pots, {ctx.author.mention}. You currently have **{user_experience} exp.**"]
        else:
            text_rows = [f"What seeds would you like to spend your experience to buy, {ctx.author.mention}? You currently have **{user_experience} exp**."]
        for plant in sorted((await self.get_available_plants(ctx.author.id)).values()):
            if plant.required_experience <= user_experience and len(plant_level_rows) < plant_limit:
                text_rows.append(f"**{plant.display_name.capitalize()}** - {plant.required_experience} exp")
                available_item_count += 1
            else:
                text_rows.append(f"~~**{plant.display_name.capitalize()}** - {plant.required_experience} exp~~")

        # Add the "welcome to items" rows
        text_rows.append("")
        text_rows.append("Would you like to buy a new item?")

        # Plant pots
        if user_experience >= self.get_points_for_plant_pot(plant_limit) and plant_limit < self.HARD_PLANT_CAP:
            text_rows.append(f"**Pot** - {self.get_points_for_plant_pot(plant_limit)} exp")
            available_item_count += 1
        else:
            text_rows.append(f"~~**Pot** - {self.get_points_for_plant_pot(plant_limit)} exp~~")

        # Add items
        for item in self.bot.items.values():
            if user_experience >= item.price:
                text_rows.append(f"**{item.display_name.capitalize()}** - {item.price} exp")
                available_item_count += 1
            else:
                text_rows.append(f"~~**{item.display_name.capitalize()}** - {item.price} exp~~")

        # See if we should cancel
        if available_item_count == 0:
            text_rows.append("")
            text_rows.append("**There is currently nothing available which you can purchase.**")
            return await ctx.send('\n'.join(text_rows))

        # Wait for them to respond
        await ctx.send('\n'.join(text_rows))
        try:
            plant_type_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel == ctx.channel and m.content, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out asking for plant type {ctx.author.mention}.")
        given_response = plant_type_message.content.lower().replace(' ', '_')

        # See if they want a plant pot
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

        # See if they want a revival token
        item_type = self.bot.items.get(given_response)
        if item_type is not None:
            if user_experience >= item_type.price:
                async with self.bot.database() as db:
                    await db.start_transaction()
                    await db(
                        """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE
                        SET user_experience=user_settings.user_experience-excluded.user_experience""",
                        ctx.author.id, item_type.price
                    )
                    await db(
                        """INSERT INTO user_inventory (user_id, item_name, amount) VALUES ($1, $2, 1)
                        ON CONFLICT (user_id, item_name) DO UPDATE SET amount=user_inventory.amount+excluded.amount""",
                        ctx.author.id, item_type.name
                    )
                    await db.commit_transaction()
                return await ctx.send(f"Given you a **{item_type.display_name}**, {ctx.author.mention}!")
            else:
                return await ctx.send(f"You don't have the required experience to get a **{item_type.display_name}**, {ctx.author.mention} :c")

        # See if they want a plant
        try:
            plant_type = self.bot.plants[given_response]
        except KeyError:
            return await ctx.send(f"`{plant_type_message.content}` isn't an available plant name, {ctx.author.mention}!", allowed_mentions=discord.AllowedMentions(users=[ctx.author], roles=False, everyone=False))
        # if plant_type.available is False:
        #     return await ctx.send(f"**{plant_type.display_name.capitalize()}** plants are unavailable right now, {ctx.author.mention} :c")
        if plant_type.required_experience > user_experience:
            return await ctx.send(f"You don't have the required experience to get a **{plant_type.display_name}**, {ctx.author.mention} (it requires {plant_type.required_experience}, you have {user_experience}) :c")
        if len(plant_level_rows) >= plant_limit:
            return await ctx.send(f"You don't have enough plant pots to be able to get a **{plant_type.display_name}**, {ctx.author.mention} :c")

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
        await ctx.send(f"Planted your **{plant_type.display_name}** seeds!")


def setup(bot):
    x = PlantShopCommands(bot)
    bot.add_cog(x)
