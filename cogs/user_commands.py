import discord
from discord.ext import commands

from cogs import utils


class UserCommands(utils.Cog):

    @commands.command(cls=utils.Command, aliases=['experience', 'exp', 'points', 'inv'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def inventory(self, ctx:utils.Context, user:utils.converters.UserID=None):
        """Show you the inventory of a user"""

        # Get user info
        user = discord.Object(user) if user else ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", user.id)
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", user.id)
            user_inventory_rows = await db("SELECT * FROM user_inventory WHERE user_id=$1 AND amount > 0", user.id)

        # Start our embed
        embed = utils.Embed(use_random_colour=True, description="")

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

    @commands.command(cls=utils.Command, aliases=['list'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def plants(self, ctx:utils.Context, user:utils.converters.UserID=None):
        """Shows you all the plants that a given user has"""

        # Grab the plant data
        user = discord.Object(user) if user else ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", user.id)

        # See if they have anything available
        plant_names = sorted([(i['plant_name'], i['plant_type'], i['plant_nourishment']) for i in user_rows])
        if not plant_names:
            embed = utils.Embed(use_random_colour=True, description=f"<@{user.id}> has no plants :c")
            return await ctx.send(embed=embed)

        # Add the plant information
        embed = utils.Embed(use_random_colour=True, description=f"<@{user.id}>'s plants")
        for i in plant_names:
            if i[2] >= 0:
                embed.add_field(i[0], f"{i[1].replace('_', ' ')}, nourishment level {i[2]}/{self.bot.plants[i[1]].max_nourishment_level}")
            else:
                embed.add_field(i[0], f"{i[1].replace('_', ' ')}, dead :c")

        # Return to user
        return await ctx.send(embed=embed)

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    async def giveitem(self, ctx:utils.Context, user:discord.Member, *, item_type:str):
        """Send an item to another member"""

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
                user.id, item_type.replace(' ', '_')
            )
            await db.commit_transaction()

        # And now we done
        return await ctx.send(f"{ctx.author.mention}, sent 1x **{self.bot.items[item_type.replace(' ', '_').lower()].display_name}** to {user.mention}!")


def setup(bot:utils.Bot):
    x = UserCommands(bot)
    bot.add_cog(x)
