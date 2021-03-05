import typing
from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands
import voxelbotutils as utils


class UserCommands(utils.Cog):

    @utils.command(aliases=['experience', 'exp', 'points', 'inv'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def inventory(self, ctx:utils.Context, user:typing.Optional[discord.User]):
        """
        Show you the inventory of a user.
        """

        # Get user info
        user = user or ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", user.id)
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", user.id)
            user_inventory_rows = await db("SELECT * FROM user_inventory WHERE user_id=$1 AND amount > 0", user.id)

        # Start our embed
        embed = utils.Embed(use_random_colour=True, description="")
        ctx._set_footer(embed)

        # Format exp into a string
        if user_rows:
            exp_value = user_rows[0]['user_experience']
        else:
            exp_value = 0
        embed.description += f"<@{user.id}> has **{exp_value:,}** experience.\n"

        # Format plant limit into a string
        if user_rows:
            plant_limit = user_rows[0]['plant_limit']
        else:
            plant_limit = 1
        they_you = {True: "you", False: "they"}.get(user.id == ctx.author.id)
        their_your = {True: "your", False: "their"}.get(user.id == ctx.author.id)
        if plant_limit == len(plant_rows):
            embed.description += f"{they_you.capitalize()} are currently using all of {their_your} available {plant_limit} plant pots.\n"
        else:
            embed.description += f"{they_you.capitalize()} are currently using {len(plant_rows)} of {their_your} available {plant_limit} plant pots.\n"

        # Format inventory into a string
        if user_inventory_rows:
            inventory_string = "\n".join([f"{row['item_name'].replace('_', ' ').capitalize()} x{row['amount']:,}" for row in user_inventory_rows])
            embed.add_field("Inventory", inventory_string)

        # Return to user
        return await ctx.send(embed=embed)

    @utils.command(aliases=['list'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def plants(self, ctx:utils.Context, user:typing.Optional[discord.User]):
        """
        Shows you all the plants that a given user has.
        """

        # Grab the plant data
        user = user or ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 ORDER BY plant_name DESC", user.id)

        # See if they have anything available
        plant_data = sorted([(i['plant_name'], i['plant_type'], i['plant_nourishment'], i['last_water_time'], i['plant_adoption_time']) for i in user_rows])
        if not plant_data:
            embed = utils.Embed(use_random_colour=True, description=f"<@{user.id}> has no plants :c")
            return await ctx.send(embed=embed)

        # Add the plant information
        embed = utils.Embed(use_random_colour=True, description=f"<@{user.id}>'s plants")
        ctx._set_footer(embed)
        for plant_name, plant_type, plant_nourishment, last_water_time, plant_adoption_time in plant_data:
            plant_type_display = plant_type.replace('_', ' ').capitalize()
            plant_death_time = last_water_time + timedelta(**self.bot.config.get('plants', {}).get('death_timeout', {'days': 3}))
            plant_death_humanize_time = utils.TimeValue((plant_death_time - dt.utcnow()).total_seconds()).clean_full
            plant_life_humanize_time = utils.TimeValue((dt.utcnow() - plant_adoption_time).total_seconds()).clean_full
            if plant_nourishment == 0:
                text = f"{plant_type_display}, nourishment level {plant_nourishment}/{self.bot.plants[plant_type].max_nourishment_level}."
            elif plant_nourishment > 0:
                text = (
                    f"**{plant_type_display}**, nourishment level {plant_nourishment}/{self.bot.plants[plant_type].max_nourishment_level}.\n"
                    f"If not watered, this plant will die in **{plant_death_humanize_time}**.\n"
                    f"This plant has been alive for **{plant_life_humanize_time}**.\n"
                )
            else:
                text = f"{plant_type_display}, dead :c"
            embed.add_field(plant_name, text, inline=False)

        # Return to user
        v = await ctx.send(embed=embed)
        try:
            await self.bot.add_delete_button(v, (ctx.author, user,), wait=False)
        except discord.HTTPException:
            pass

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    async def giveitem(self, ctx:utils.Context, user:discord.Member, *, item_type:str):
        """
        Send an item to another member.
        """

        async with self.bot.database() as db:

            # See if they have the item they're trying to give
            inventory_rows = await db("SELECT * FROM user_inventory WHERE user_id=$1 AND LOWER(item_name)=LOWER($2)", ctx.author.id, item_type.replace(' ', '_'))
            if not inventory_rows or inventory_rows[0]['amount'] < 1:
                return await ctx.send(f"You don't have any of that item, {ctx.author.mention}! :c")

            # Move it from one user to the other
            await db.start_transaction()
            await db("UPDATE user_inventory SET amount=user_inventory.amount-1 WHERE user_id=$1 AND LOWER(item_name)=LOWER($2)", ctx.author.id, item_type.replace(' ', '_'))
            await db(
                """INSERT INTO user_inventory VALUES ($1, $2, 1) ON CONFLICT (user_id, item_name) DO UPDATE SET
                amount=user_inventory.amount+excluded.amount""",
                user.id, item_type.replace(' ', '_').lower()
            )
            await db.commit_transaction()

        # And now we done
        return await ctx.send(f"{ctx.author.mention}, sent 1x **{self.bot.items[item_type.replace(' ', '_').lower()].display_name}** to {user.mention}!")
    
    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    async def keys(self, ctx:utils.Context):
        """
        Check all users who have a key
        """
        # How do we want to deal with users who aren't on this server?
        # Could create a cached 'accessor_name' that's available based on accessor's Discord tag.

        await ctx.send("Not implemented")


    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    async def givekey(self, ctx:utils.Context, user:discord.Member):
        """
        Give a key to your garden to another member.
        """

        if user.bot:
            return await ctx.send("Bots can't help you maintain your garden.")
        if user.id == ctx.author.id:
            return await ctx.send("You already have a key.")

        async with self.bot.database() as db:
            given_key = await db("SELECT * FROM user_garden_access WHERE garden_owner=$1 AND garden_access=$2", ctx.author.id, user.id)
            if given_key:
                return await ctx.send(f"They already have a key!")
            
            await db(
                "INSERT INTO user_garden_access (garden_owner, garden_access, last_here) VALUES ($1, $2, $3)",
                ctx.author.id, user.id, dt(2000, 1, 1)
            )
            return await ctx.send(f"Gave {user.mention} a key!")

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    async def revokekey(self, ctx:utils.Context, user:discord.Member):
        """
        Revoke a member's access to your garden
        """

        if user.id == ctx.author.id:
            await ctx.send("You can't revoke your own key.")

        async with self.bot.database() as db:
            data = await db("DELETE FROM user_garden_access WHERE garden_owner=$1 AND garden_access=$2 RETURNING *", ctx.author.id, user.id)
        if not data:
            return await ctx.send(f"They don't have a key!")
        return await ctx.send(f"That's how the coo-key crumbles. {user.mention} no longer has a key to your garden.")


def setup(bot:utils.Bot):
    x = UserCommands(bot)
    bot.add_cog(x)
