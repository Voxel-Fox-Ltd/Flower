from __future__ import annotations

import typing
from datetime import timedelta

import discord
from discord.ext import commands, vbu
from asyncpg.exceptions import UniqueViolationError

from cogs.utils.types.bot import Bot

if typing.TYPE_CHECKING:
    from cogs.utils.types.rows import (
        UserSettingsRows,
        PlantLevelsRows,
        UserInventoryRows,
    )


class UserCommands(vbu.Cog[Bot]):

    @commands.command(
        aliases=["experience", "exp", "points", "inv", "bal", "balance"],
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user who you want to check the inventory of.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=False,
                ),
            ],
        ),
    )
    @commands.defer()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def inventory(
            self,
            ctx: vbu.Context,
            user: typing.Union[discord.Member, discord.User] = None,
            ):
        """
        Show you the inventory of a user.
        """

        # Get user info
        user = user or ctx.author
        async with vbu.Database() as db:
            user_rows: UserSettingsRows = await db(
                "SELECT * FROM user_settings WHERE user_id=$1",
                user.id,
            )
            plant_rows: PlantLevelsRows = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1",
                user.id,
            )
            user_inventory_rows: UserInventoryRows = await db(
                "SELECT * FROM user_inventory WHERE user_id=$1 AND amount > 0",
                user.id,
            )

        # Start our embed
        embed = vbu.Embed(use_random_colour=True, description="")
        ctx.bot.set_footer_from_config(embed)

        # Format exp into a string
        if user_rows:
            exp_value = user_rows[0]['user_experience']
        else:
            exp_value = 0
        embed.description += vbu.format(
            "{0:pronoun,You have,{1.mention} has} **{2:,}** experience.\n",
            ctx.author == user,
            user,
            exp_value,
        )

        # Format plant limit into a string
        if user_rows:
            plant_limit = user_rows[0]['plant_limit']
        else:
            plant_limit = 1
        if plant_limit == len(plant_rows):
            embed.description += vbu.format(
                (
                    "{0:pronoun,You are,{1.mention} is} currently using "
                    "all of {0:pronoun,your,their} **{2}** available plant pots.\n"
                ),
                ctx.author == user,
                user,
                plant_limit,
            )
        else:
            embed.description += vbu.format(
                (
                    "{0:pronoun,You are,{1.mention} is} are currently using **{2}** of "
                    "{0:pronoun,your,their} **{3}** available plant pots.\n"
                ),
                ctx.author == user,
                user,
                len(plant_rows),
                plant_limit,
            )

        # Format inventory into a string
        if user_inventory_rows:
            inventory_string = "\n".join([
                f"{row['item_name'].replace('_', ' ').capitalize()} x{row['amount']:,}"
                for row in user_inventory_rows
            ])
            embed.add_field("Inventory", inventory_string)

        # Return to user
        return await ctx.send(embed=embed)

    @commands.command(
        aliases=["list"],
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user who you want to see the plants of.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=False,
                ),
            ],
        ),
    )
    @commands.defer()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def plants(
            self,
            ctx: vbu.Context,
            user: typing.Union[discord.Member, discord.User] = None,
            ):
        """
        Shows you all the plants that a given user has.
        """

        # Grab the plant data
        user = user or ctx.author
        async with vbu.Database() as db:
            plant_data: PlantLevelsRows = await db(
                """SELECT * FROM plant_levels WHERE user_id=$1 ORDER BY plant_name DESC,
                plant_type DESC, plant_nourishment DESC, last_water_time DESC,
                plant_adoption_time DESC""",
                user.id,
            )

        # See if they have anything available
        if not plant_data:
            embed = vbu.Embed(
                use_random_colour=True,
                description=vbu.format(
                    "{0:pronoun,You have,{1.mention} has} no plants :c",
                    ctx.author == user, user,
                ),
            )
            return await ctx.send(embed=embed)

        # Add the plant information
        embed = vbu.Embed(use_random_colour=True, description=f"<@{user.id}>'s plants")
        ctx.bot.set_footer_from_config(embed)
        for plant in plant_data:
            plant_type_display = plant['plant_type'].replace('_', ' ').capitalize()

            # Get the time when the plant will die
            if plant['immortal']:
                plant_death_humanize_time = None
            else:
                death_timeout = timedelta(**self.bot.config['plants']['death_timeout'])
                plant_death_time = plant['last_water_time'] + death_timeout
                plant_death_humanize_time = discord.utils.format_dt(plant_death_time, "R")

            # See how long the plant has been alive
            plant_life_humanize_time = discord.utils.format_dt(plant['plant_adoption_time'], "R")

            # Make the text to put in the embed
            max_nourishment = self.bot.plants[plant['plant_type']].max_nourishment_level
            text = f"**{plant_type_display}**, nourishment level {plant['plant_nourishment']}/{max_nourishment}."
            if plant['plant_nourishment'] > 0 and not plant['immortal']:
                text += f"If not watered, this plant will die in **{plant_death_humanize_time}**.\n"
            text += f"You adopted this plant {plant_life_humanize_time}.\n"
            if plant['plant_nourishment'] < 0:
                text = f"{plant_type_display}, dead :c"

            # And add the field
            embed.add_field(plant['plant_name'], text, inline=False)

        # Return to user
        return await ctx.send(embed=embed)

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user who you want to give the item to.",
                    type=discord.ApplicationCommandOptionType.user,
                ),
                discord.ApplicationCommandOption(
                    name="item_type",
                    description="The item you want to give away.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),
            ],
        ),
    )
    @commands.bot_has_permissions(send_messages=True)
    async def giveitem(
            self,
            ctx: vbu.Context,
            user: discord.Member,
            *,
            item_type: str,
            ):
        """
        Send an item to another member.
        """

        if user.bot:
            return await ctx.send("That's a bot. You can't give items to bots.")

        if item_type.lower().strip() == "pot":
            return await ctx.send("You can't give pots to other users.")
        if item_type.lower().strip() in {"exp", "experience"}:
            return await ctx.send("You can't give exp to other users.")

        async with vbu.Database() as db:

            # See if they have the item they're trying to give
            inventory_rows: UserInventoryRows = await db(
                "SELECT * FROM user_inventory WHERE user_id=$1 AND LOWER(item_name)=LOWER($2)",
                ctx.author.id, item_type.replace(' ', '_'),
            )
            if not inventory_rows or inventory_rows[0]['amount'] < 1:
                return await ctx.send(f"You don't have any of that item, {ctx.author.mention}! :c")

            # Move it from one user to the other
            async with db.transaction() as trans:
                await trans(
                    "UPDATE user_inventory SET amount=user_inventory.amount-1 WHERE user_id=$1 AND LOWER(item_name)=LOWER($2)",
                    ctx.author.id, item_type.replace(' ', '_'),
                )
                await trans(
                    """INSERT INTO user_inventory VALUES ($1, $2, 1) ON CONFLICT (user_id, item_name) DO UPDATE SET
                    amount=user_inventory.amount+excluded.amount""",
                    user.id, item_type.replace(' ', '_').lower()
                )

        # And now we done
        item_name = self.bot.items[item_type.replace(' ', '_').lower()].display_name
        return await ctx.send(f"{ctx.author.mention}, sent 1x **{item_name}** to {user.mention}!")

    @commands.group(
        aliases=["key", "access"],
        invoke_without_command=True,
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    async def keys(
            self,
            ctx: vbu.Context,
            ):
        """
        The parent command for keys - allowing other users to access your garden.
        """

        if ctx.invoked_subcommand is None:
            return await ctx.send_help(ctx.command)

    @keys.command(
        name="list",
        aliases=["show", "holders"],
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def key_list(
            self,
            ctx: vbu.Context,
            ):
        """
        Shows all users who have a key to your garden.
        """

        async with vbu.Database() as db:
            key_owners = await db("SELECT * FROM user_garden_access WHERE garden_owner=$1", ctx.author.id)
        if not key_owners:
            return await ctx.send("No one else has a key to your garden.")
        embed = vbu.Embed(use_random_colour=True, description=f"<@{ctx.author.id}>'s allowed users ({len(key_owners)})")
        embed_fields = []
        for key_owner in key_owners:
            embed_fields.append(f"<@{key_owner['garden_access']}>")
        embed.add_field("Key Holders", '\n'.join(sorted(embed_fields)), inline=False)
        return await ctx.send(embed=embed)

    @keys.command(
        name="give",
        aliases=["add"],
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user who you want to give a key to.",
                    type=discord.ApplicationCommandOptionType.user,
                ),
            ],
        ),
    )
    @commands.bot_has_permissions(send_messages=True)
    async def key_give(
            self,
            ctx: vbu.Context,
            user: discord.Member,
            ):
        """
        Give a key to your garden to another member.
        """

        if user.bot:
            return await ctx.send("Bots can't help you maintain your garden.")
        if user.id == ctx.author.id:
            return await ctx.send("You already have a key.")

        async with vbu.Database() as db:
            try:
                await db(
                    "INSERT INTO user_garden_access (garden_owner, garden_access) VALUES ($1, $2)",
                    ctx.author.id, user.id,
                )
            except UniqueViolationError:
                return await ctx.send("They already have a key.")
        return await ctx.send(f"Gave {user.mention} a key to your garden! They can now water your plants for you!")

    @keys.command(
        name="revoke",
        aliases=["remove", "take", "delete"],
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user who you want to remove a key from.",
                    type=discord.ApplicationCommandOptionType.user,
                ),
            ],
        ),
    )
    @commands.bot_has_permissions(send_messages=True)
    async def key_revoke(
            self,
            ctx: vbu.Context,
            user: vbu.converters.UserID,
            ):
        """
        Revoke a member's access to your garden
        """

        if user == ctx.author.id:
            return await ctx.send("You can't revoke your own key :/")
        async with vbu.Database() as db:
            data = await db(
                "DELETE FROM user_garden_access WHERE garden_owner=$1 AND garden_access=$2 RETURNING *",
                ctx.author.id, user,
            )
        if not data:
            return await ctx.send("They don't have a key!")
        return await ctx.send(
            f"Their key crumbles. <@{user}> no longer has a key to your garden.",
            allowed_mentions=discord.AllowedMentions.none(),
        )


def setup(bot: vbu.Bot):
    x = UserCommands(bot)
    bot.add_cog(x)
