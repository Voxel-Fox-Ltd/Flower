import asyncio
import collections
from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands, tasks
import voxelbotutils as utils


class PlantCareCommands(utils.Cog):

    PLANT_DEATH_TIMEOUT = {
        'days': 3,
    }
    PLANT_WATER_COOLDOWN = {
        'minutes': 15,
    }
    TOPGG_GET_VOTES_ENDPOINT = "https://top.gg/api/bots/{bot.user.id}/check"

    def __init__(self, bot):
        super().__init__(bot)
        self.plant_death_timeout_loop.start()

    def cog_unload(self):
        self.plant_death_timeout_loop.cancel()

    async def get_user_voted(self, user_id:int) -> bool:
        """
        Returns whether or not the user with the given ID has voted for the bot on Top.gg.

        Args:
            user_id (int): The ID of the user we want to check

        Returns:
            bool: Whether or not the user voted for the bot
        """

        topgg_token = self.bot.config.get('bot_listing_api_keys', {}).get('topgg_token')
        if not topgg_token:
            return False
        params = {"userId": user_id}
        headers = {"Authorization": topgg_token}
        async with self.bot.session.get(self.TOPGG_GET_VOTES_ENDPOINT.format(bot=self.bot), params=params, headers=headers) as r:
            try:
                data = await r.json()
            except Exception:
                return False
            if r.status != 200:
                return False
        return bool(data['voted'])

    @tasks.loop(minutes=1)
    async def plant_death_timeout_loop(self):
        """
        Loop to see if we should kill off any plants that may have been timed out
        """

        async with self.bot.database() as db:
            await db(
                """UPDATE plant_levels SET plant_nourishment=-plant_levels.plant_nourishment WHERE
                plant_nourishment > 0 AND last_water_time + $2 < $1""",
                dt.utcnow(), timedelta(**self.PLANT_DEATH_TIMEOUT),
            )

    @staticmethod
    def validate_name(name:str):
        """
        Validates the name of a plant
        Input is the name, output is a (bool, Optional[str]) tuple - the boolean is whether their given name is valid, and the
        string is their plant's name. More often than not that'll be the same as the input, but quote marks are stripped from the
        name before being given as an output.
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

    @utils.command(aliases=['water'], cooldown_after_parsing=True)
    @commands.bot_has_permissions(send_messages=True)
    async def waterplant(self, ctx:utils.Context, *, plant_name:str):
        """
        Increase the growth level of your plant.
        """

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
        last_water_time = plant_level_row[0]['last_water_time']

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
        user_plant_data = plant_level_row[0]
        gained_experience = 0
        original_gained_experience = 0
        multipliers = []  # List[Tuple[float, "reason"]]
        additional_text = []  # List[str]

        # And now let's water the damn thing
        if user_plant_data['plant_nourishment'] > 0:

            # Get the experience that they should have gained
            gained_experience = plant_data.get_experience()
            original_gained_experience = gained_experience

            # See if we want to give them a 30 second water-time bonus
            if dt.utcnow() - last_water_time - timedelta(**self.PLANT_WATER_COOLDOWN) <= timedelta(seconds=30):
                multipliers.append((1.5, "You watered within 30 seconds of your plant's cooldown resetting."))

            # See if we want to give the new owner bonus
            if plant_level_row[0]['user_id'] != plant_level_row[0]['original_owner_id']:
                multipliers.append((1.05, "You watered a plant that you got from a trade."))

            # See if we want to give them the voter bonus
            if self.bot.config.get('bot_listing_api_keys', {}).get('topgg_token') and await self.get_user_voted(ctx.author.id):
                multipliers.append((1.1, f"You [voted for the bot](https://top.gg/bot/{self.bot.user.id}/vote) on Top.gg."))

            # See if we want to give them the plant longevity bonus
            if user_plant_data['plant_adoption_time'] < dt.utcnow() - timedelta(days=7):
                multipliers.append((1.1, "Your plant has been alive for longer than a week;"))

            # Add the actual multiplier values
            for multiplier, _ in multipliers:
                gained_experience *= multiplier

            # Update db
            gained_experience = int(gained_experience)
            await db(
                """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                DO UPDATE SET user_experience=user_settings.user_experience+$2""",
                ctx.author.id, gained_experience,
            )

        # Send an output
        await db.disconnect()
        if user_plant_data['plant_nourishment'] < 0:
            return await ctx.send("You sadly pour water into the dry soil of your silently wilting plant :c")

        # Set up our output text
        gained_exp_string = f"**{gained_experience}**" if gained_experience == original_gained_experience else f"~~{original_gained_experience}~~ **{gained_experience}**"
        output_lines = []
        if plant_data.get_nourishment_display_level(user_plant_data['plant_nourishment']) > plant_data.get_nourishment_display_level(user_plant_data['plant_nourishment'] - 1):
            output_lines.append(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_exp_string} experience, watching your plant grow!~")
        else:
            output_lines.append(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_exp_string} experience~")
        for m, t in multipliers:
            output_lines.append(f"**{m}x**: {t}")
        for t in additional_text:
            output_lines.append(t)

        # Try and embed the message
        embed = None
        if ctx.guild is None or ctx.channel.permissions_for(ctx.guild.me).embed_links:

            # Make initial embed
            embed = utils.Embed(use_random_colour=True, description=output_lines[0])

            # Add multipliers
            if len(output_lines) > 1:
                embed.add_field(
                    "Multipliers", "\n".join([i.strip('') for i in output_lines[1:]]), inline=False
                )

            # Add "please vote for Flower" footer
            counter = 0
            embed.set_footer("")
            while counter < 100 and 'vote' not in embed.footer.text.lower():
                ctx._set_footer(embed)
                counter += 1

            # Clear the text we would otherwise output
            output_lines.clear()

        # Send message
        return await ctx.send("\n".join(output_lines), embed=embed)

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
        plant_display_utils = self.bot.get_cog("PlantDisplayCommands")
        image_data = []
        plants_being_traded = [alive_plants[ctx.author.id][trade_plant_index[ctx.author.id]], alive_plants[user.id][trade_plant_index[user.id]]]
        for plant_row in plants_being_traded:
            display_data = plant_display_utils.get_display_data(plant_row)
            image_data.append(plant_display_utils.get_plant_image(**display_data))
        compiled_image = plant_display_utils.compile_plant_images(*image_data)
        handle = plant_display_utils.image_to_bytes(compiled_image)
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
                    await db(
                        """INSERT INTO plant_levels (user_id, plant_name, plant_type, plant_variant, plant_nourishment,
                        last_water_time, original_owner_id, plant_adoption_time) VALUES ($1, $2, $3, $4, $5, $6, $7, TIMEZONE('UTC', NOW()))""",
                        ctx.author.id if row['user_id'] == user.id else user.id, row['plant_name'], row['plant_type'], row['plant_variant'],
                        row['plant_nourishment'], dt.utcnow() - timedelta(**self.PLANT_WATER_COOLDOWN), row['original_owner_id'] or row['user_id']
                    )
                await db.commit_transaction()
        except Exception:
            return await ctx.send("I couldn't trade your plants! That probably means that one of you already _has_ a plant with the given name in your plant list.")
        await ctx.send("Traded your plants!")

    @utils.command(aliases=['delete'])
    @commands.bot_has_permissions(send_messages=True)
    async def deleteplant(self, ctx:utils.Context, *, plant_name:str):
        """Deletes your plant from the database"""

        async with self.bot.database() as db:
            data = await db("DELETE FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *", ctx.author.id, plant_name)
        if not data:
            return await ctx.send(f"You have no plant names **{plant_name}**!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        return await ctx.send(f"Done - you've deleted your {data[0]['plant_type'].replace('_', ' ')}.")

    @utils.command(aliases=['rename'])
    @commands.bot_has_permissions(send_messages=True)
    async def renameplant(self, ctx:utils.Context, before:str, *, after:str):
        """
        Gives a new name to your plant. Use "quotes" if your plant has a space in its name.
        """

        # Make sure some names were provided
        _, after = self.validate_name(after)
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

            # Make sure they own the plant
            if plant_has_before_name[0]['original_owner_id'] != ctx.author.id:
                return await ctx.send("You can't rename plants that you didn't own originally.")

            # Make sure they aren't trying to rename to a currently existing name
            plant_name_exists = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, after)
            if plant_name_exists:
                return await ctx.send(f"You already have a plant with the name **{after}**!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

            # Update plant name
            await db("UPDATE plant_levels SET plant_name=$3 WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before, after)
        await ctx.send("Done!~")

    @utils.command()
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
