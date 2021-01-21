import asyncio
from datetime import datetime as dt, timedelta
import os
import glob
import json
import collections
import random

import discord
from discord.ext import commands
import voxelbotutils as utils

from cogs import localutils


def strikethrough(text:str) -> str:
    """
    Returns a string wrapped in a strikethrough
    """

    return f"~~{text}~~"


class PlantShopCommands(utils.Cog):

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)

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
        try:
            self.bot.plants.clear()
        except AttributeError:
            pass
        self.bot.plants = {i['name']: localutils.PlantType(**i) for i in available_plants}

        # Add the items
        self.bot.items = {
            'revival_token': localutils.ItemType(
                item_name='revival_token',
                item_price=self.bot.config.get('plants', {}).get('revival_token_price', 300)
            ),
        }

        # Reset the artist dict
        self.bot.get_cog("InformationCommands")._artist_info = None

    def get_points_for_plant_pot(self, current_limit:str):
        """
        Get the amount of points needed to get the next level of pot.
        """

        pot_base_price = self.bot.config.get('plants', {}).get('plant_pot_base_price', 50)
        return int(pot_base_price * (3 ** (current_limit - 1)))

    async def get_available_plants(self, user_id:int) -> dict:
        """
        Get the available plants for a given user at each given level.
        """

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
                await db(
                    """INSERT INTO user_available_plants
                    (user_id, last_shop_timestamp, plant_level_0, plant_level_1, plant_level_2, plant_level_3, plant_level_4, plant_level_5, plant_level_6)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (user_id) DO UPDATE SET
                    last_shop_timestamp=excluded.last_shop_timestamp, plant_level_0=excluded.plant_level_0, plant_level_1=excluded.plant_level_1,
                    plant_level_2=excluded.plant_level_2, plant_level_3=excluded.plant_level_3, plant_level_4=excluded.plant_level_4,
                    plant_level_5=excluded.plant_level_5, plant_level_6=excluded.plant_level_6""",
                    user_id, dt.utcnow(), available_plants[0].name, available_plants[1].name, available_plants[2].name, available_plants[3].name,
                    available_plants[4].name, available_plants[5].name, available_plants[6].name,
                )

            # They have available plants, format into new dictionary
            else:
                available_plants = {
                    0: self.bot.plants[plant_shop_rows[0]['plant_level_0']],
                    1: self.bot.plants[plant_shop_rows[0]['plant_level_1']],
                    2: self.bot.plants[plant_shop_rows[0]['plant_level_2']],
                    3: self.bot.plants[plant_shop_rows[0]['plant_level_3']],
                    4: self.bot.plants[plant_shop_rows[0]['plant_level_4']],
                    5: self.bot.plants[plant_shop_rows[0]['plant_level_5']],
                    6: self.bot.plants[plant_shop_rows[0]['plant_level_6']],
                }
        return available_plants

    @utils.command()
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def reloadplants(self, ctx:utils.Context):
        """
        Shows you the available plants.
        """

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
        self.bot.plants = {i['name']: localutils.PlantType(**i) for i in available_plants}

        # Reset the artist dict
        self.bot.get_cog("InformationCommands")._artist_info = None

        # And done
        return await ctx.send("Reloaded.")

    @utils.command(aliases=['getplant', 'getpot', 'newpot', 'newplant'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def shop(self, ctx:utils.Context):
        """
        Shows you the available plants.
        """

        # Get data from the user
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", ctx.author.id)
            plant_level_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", ctx.author.id)
        if user_rows:
            user_experience = user_rows[0]['user_experience']
            plant_limit = user_rows[0]['plant_limit']
            last_plant_shop_time = user_rows[0]['last_plant_shop_time'] or dt(2000, 1, 1)
        else:
            user_experience = 0
            plant_limit = 1
            last_plant_shop_time = dt(2000, 1, 1)
        can_purchase_new_plants = dt.utcnow() > last_plant_shop_time + timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15}))
        buy_plant_cooldown_delta = None
        if can_purchase_new_plants is False:
            buy_plant_cooldown_delta = utils.TimeValue(
                ((last_plant_shop_time + timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15}))) - dt.utcnow()).total_seconds()
            )

        # Set up our initial items
        available_item_count = 0  # Used to make sure we can continue the command
        embed = utils.Embed(use_random_colour=True, description="")
        ctx._set_footer(embed)

        # See what we wanna get to doing
        embed.description += (
            f"What would you like to spend your experience to buy, {ctx.author.mention}? "
            f"You currently have **{user_experience:,} exp**, and you're using {len(plant_level_rows):,} of your {plant_limit:,} available plant pots.\n"
        )
        available_plants = await self.get_available_plants(ctx.author.id)

        # Add "can't purchase new plant" to the embed
        if can_purchase_new_plants is False:
            embed.description += f"\nYou can't purchase new plants for another **{buy_plant_cooldown_delta.clean}**.\n"

        # Add plants to the embed
        plant_text = []
        for plant in sorted(available_plants.values()):
            modifier = lambda x: x
            text = f"{plant.display_name.capitalize()} - `{plant.required_experience:,} exp`"
            if can_purchase_new_plants and plant.required_experience <= user_experience and len(plant_level_rows) < plant_limit:
                available_item_count += 1
            else:
                modifier = strikethrough
            plant_text.append(modifier(text))

        # Say when the plants will change
        now = dt.utcnow()
        remaining_time = utils.TimeValue((dt(now.year if now.month < 12 else now.year + 1, now.month + 1 if now.month < 12 else 1, 1) - now).total_seconds())
        plant_text.append(f"These plants will change in {remaining_time.clean_spaced}.")
        embed.add_field("Available Plants", '\n'.join(plant_text), inline=True)

        # Set up items to be added to the embed
        item_text = []

        # Add pots
        modifier = lambda x: x
        text = f"Pot - `{self.get_points_for_plant_pot(plant_limit):,} exp`"
        if user_experience >= self.get_points_for_plant_pot(plant_limit) and plant_limit < self.bot.config.get('plants', {}).get('hard_plant_cap', 10):
            available_item_count += 1
        else:
            modifier = strikethrough
        item_text.append(modifier(text))

        # Add variable items
        for item in self.bot.items.values():
            modifier = lambda x: x
            text = f"{item.display_name.capitalize()} - `{item.price:,} exp`"
            if user_experience >= item.price:
                available_item_count += 1
            else:
                modifier = strikethrough
            item_text.append(modifier(text))

        # Add all our items to the embed
        embed.add_field("Available Items", '\n'.join(item_text), inline=True)

        # Cancel if they don't have anything available
        if available_item_count == 0:
            embed.description += "\n**There is currently nothing available which you can purchase.**\n"
            return await ctx.send(embed=embed)
        else:
            embed.description += "\n**Say the name of the item you want to purchase, or type `cancel` to exit the shop with nothing.**\n"

        # Wait for them to respond
        shop_menu_message = await ctx.send(embed=embed)
        try:
            done, pending = asyncio.wait([
                self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel == ctx.channel and m.content),
                self.bot.wait_for("raw_message_delete", check=lambda m: m.id == shop_menu_message.id),
            ], timeout=120, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out asking for plant type {ctx.author.mention}.")

        # See how they responded
        for future in pending:
            future.cancel()
        done = done.pop().result()
        if isinstance(done, discord.RawMessageDeleteEvent):
            return
        plant_type_message = done
        given_response = plant_type_message.content.lower().replace(' ', '_')

        # See if they want to cancel
        if given_response == "cancel":
            try:
                await plant_type_message.add_reaction("\N{OK HAND SIGN}")
            except discord.HTTPException:
                pass
            return

        # See if they want a plant pot
        if given_response == "pot":
            if plant_limit >= self.bot.config.get('plants', {}).get('hard_plant_cap', 10):
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
        if can_purchase_new_plants is False:
            return await ctx.send(f"You can't purchase new plants for another **{buy_plant_cooldown_delta.clean}**.")
        if plant_type not in available_plants.values():
            return await ctx.send(f"**{plant_type.display_name.capitalize()}** isn't available in your shop this month, {ctx.author.mention} :c")
        if plant_type.required_experience > user_experience:
            return await ctx.send(f"You don't have the required experience to get a **{plant_type.display_name}**, {ctx.author.mention} (it requires {plant_type.required_experience}, you have {user_experience}) :c")
        if len(plant_level_rows) >= plant_limit:
            return await ctx.send(f"You don't have enough plant pots to be able to get a **{plant_type.display_name}**, {ctx.author.mention} :c")

        # Get a name for the plant
        await ctx.send("What name do you want to give your plant?")
        while True:
            try:
                plant_name_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel == ctx.channel and m.content, timeout=120)
            except asyncio.TimeoutError:
                return await ctx.send(f"Timed out asking for plant name {ctx.author.mention}.")
            plant_name = self.bot.get_cog("PlantCareCommands").validate_name(plant_name_message.content)
            if len(plant_name) > 50 or len(plant_name) == 0:
                await ctx.send("That name is too long! Please give another one instead!")
            else:
                break

        # Save the enw plant to database
        async with self.bot.database() as db:
            plant_name_exists = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                ctx.author.id, plant_name
            )
            if plant_name_exists:
                return await ctx.send(f"You've already used the name `{plant_name}` for one of your other plants - please run this command again to give a new one!", allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))
            await db(
                """INSERT INTO plant_levels (user_id, plant_name, plant_type, plant_nourishment, last_water_time, original_owner_id, plant_adoption_time, plant_pot_hue)
                VALUES ($1, $2, $3, 0, $4, $1, TIMEZONE('UTC', NOW()), $1 % 360) ON CONFLICT (user_id, plant_name) DO UPDATE
                SET plant_nourishment=0, last_water_time=$4""",
                ctx.author.id, plant_name, plant_type.name, dt(2000, 1, 1),
            )
            await db(
                "UPDATE user_settings SET user_experience=user_settings.user_experience-$2, last_plant_shop_time=TIMEZONE('UTC', NOW()) WHERE user_id=$1",
                ctx.author.id, plant_type.required_experience,
            )
        await ctx.send(f"Planted your **{plant_type.display_name}** seeds!")

    @utils.command(aliases=['trade'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True, add_reactions=True)
    @commands.guild_only()
    async def tradeplant(self, ctx, user:discord.Member):
        """
        Trade a plant with a given user.
        """

        # Make sure they're not trading with the bot
        if user.id == self.bot.user.id:
            return await ctx.invoke(self.bot.get_command("shop"))
        elif user.bot:
            return await ctx.send("Bots don't have any plants, actually.")
        elif ctx.author.id == user.id:
            return await ctx.send(":/")

        # Get their alive plants _now_, even if we have to do it later again
        async with self.bot.database() as db:
            rows = await db("SELECT * FROM plant_levels WHERE user_id=ANY($1::BIGINT[]) AND plant_nourishment > 0 ORDER BY plant_name ASC", [ctx.author.id, user.id])
        alive_plants = collections.defaultdict(list)
        for row in rows:
            alive_plants[row['user_id']].append(row)

        # Make sure they both have some plants before we ask them about trades
        if not alive_plants[ctx.author.id]:
            return await ctx.send(f"You don't have any alive plants to trade, {ctx.author.mention}!")
        elif not alive_plants[user.id]:
            return await ctx.send(f"{user.mention} doesn't have any alive plants to trade, {ctx.author.mention}!", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))

        # See if they want to trade
        m = await ctx.send(f"{user.mention}, do you want to trade a plant with {ctx.author.mention}?")
        await m.add_reaction("\N{THUMBS UP SIGN}")
        await m.add_reaction("\N{THUMBS DOWN SIGN}")
        try:
            check = lambda r, u: r.message.id == m.id and u.id == user.id and str(r.emoji) in ["\N{THUMBS UP SIGN}", "\N{THUMBS DOWN SIGN}"]
            r, _ = await self.bot.wait_for("reaction_add", check=check, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send(f"{user.mention} didn't respond to your trade request in time, {ctx.author.mention}", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))
        if str(r.emoji) == "\N{THUMBS DOWN SIGN}":
            return await ctx.send(f"{user.mention} doesn't want to trade anything, {ctx.author.mention}! :c", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))

        # Get their alive plants _again_
        async with self.bot.database() as db:
            rows = await db("SELECT * FROM plant_levels WHERE user_id=ANY($1::BIGINT[]) AND plant_nourishment > 0 ORDER BY plant_name ASC", [ctx.author.id, user.id])
        alive_plants = collections.defaultdict(list)
        for row in rows:
            alive_plants[row['user_id']].append(row)

        # Make sure they both still have plants that are alive
        if not alive_plants[ctx.author.id]:
            return await ctx.send(f"You don't have any alive plants to trade, {ctx.author.mention}!")
        elif not alive_plants[user.id]:
            return await ctx.send(f"You don't have any alive plants to trade, {user.mention}!")

        # Format an embed
        embed = utils.Embed(use_random_colour=True)
        embed.add_field(
            f"{ctx.author.name}",
            "\n".join([f"**{row['plant_name']}** ({row['plant_type'].replace('_', ' ')}, {row['plant_nourishment']})" for row in alive_plants[ctx.author.id]]),
            inline=True,
        )
        embed.add_field(
            f"{user.name}",
            "\n".join([f"**{row['plant_name']}** ({row['plant_type'].replace('_', ' ')}, {row['plant_nourishment']})" for row in alive_plants[user.id]]),
            inline=True,
        )

        # Ask what they want to trade
        await ctx.send(f"What's the name of the plant that you'd like to trade, {ctx.author.mention} {user.mention}?", embed=embed)
        trade_plant_index = {ctx.author.id: None, user.id: None}
        while True:
            def check(m):
                allowed_ids = set()
                for uid, ind in trade_plant_index.items():
                    if ind is None:
                        allowed_ids.add(uid)
                return m.author.id in allowed_ids and m.content  # and m.content.isdigit()
            try:
                index_message = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send(f"Your trade request timed out, {ctx.author.mention} {user.mention}.")

            # Make sure their given index was invalid
            try:
                valid_row = [i for i in alive_plants[index_message.author.id] if i['plant_name'].lower() == index_message.content.lower()][0]
            except IndexError:
                continue
            trade_plant_index[index_message.author.id] = alive_plants[index_message.author.id].index(valid_row)
            await index_message.add_reaction("\N{THUMBS UP SIGN}")

            # See if we can exit now
            if None not in trade_plant_index.values():
                break

        # Get their plant images
        display_utils = self.bot.get_cog("PlantDisplayUtils")
        image_data = []
        plants_being_traded = [
            alive_plants[ctx.author.id][trade_plant_index[ctx.author.id]],
            alive_plants[user.id][trade_plant_index[user.id]]
        ]
        for plant_row in plants_being_traded:
            display_data = display_utils.get_display_data(plant_row)
            image_data.append(display_utils.get_plant_image(**display_data))
        compiled_image = display_utils.compile_plant_images(*image_data)
        handle = display_utils.image_to_bytes(compiled_image)
        file = discord.File(handle, filename="plant_trade.png")

        # Ask if they wanna go ahead with it
        embed = utils.Embed(use_random_colour=True).set_image("attachment://plant_trade.png")
        m = await ctx.send("Do you both want to go ahead with this trade?", embed=embed, file=file)
        await m.add_reaction("\N{THUMBS UP SIGN}")
        await m.add_reaction("\N{THUMBS DOWN SIGN}")
        said_yes = set()
        while True:
            try:
                check = lambda r, u: r.message.id == m.id and u.id in [ctx.author.id, user.id] and str(r.emoji) in ["\N{THUMBS UP SIGN}", "\N{THUMBS DOWN SIGN}"]
                r, u = await self.bot.wait_for("reaction_add", check=check, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send(f"Your trade request timed out, {ctx.author.mention} {user.mention}.")
            if str(r.emoji) == "\N{THUMBS DOWN SIGN}":
                return await ctx.send(f"{u.mention} doesn't want to go ahead with the trade :<")
            said_yes.add(u.id)
            if len(said_yes) == 2:
                break

        # Alright sick let's trade
        try:
            async with self.bot.database() as db:
                await db.start_transaction()
                for row in plants_being_traded:
                    v = await db("DELETE FROM plant_levels WHERE user_id=$1 AND plant_name=$2 RETURNING *", row['user_id'], row['plant_name'])
                    assert v is not None
                for row in plants_being_traded:
                    is_watered = row['last_water_time'] + timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15})) > dt.utcnow()
                    await db(
                        """INSERT INTO plant_levels (user_id, plant_name, plant_type, plant_nourishment,
                        last_water_time, original_owner_id, plant_adoption_time, plant_pot_hue) VALUES ($1, $2, $3, $4, $5, $6, TIMEZONE('UTC', NOW()), $7)""",
                        ctx.author.id if row['user_id'] == user.id else user.id, row['plant_name'], row['plant_type'], row['plant_nourishment'],
                        row['last_water_time'] if is_watered else dt.utcnow() - timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15})),
                        row['original_owner_id'] or row['user_id'], row['plant_pot_hue'],
                    )
                await db.commit_transaction()
        except Exception:
            return await ctx.send("I couldn't trade your plants! That probably means that one of you already _has_ a plant with the given name in your plant list.")
        await ctx.send("Traded your plants!")


def setup(bot):
    x = PlantShopCommands(bot)
    bot.add_cog(x)
