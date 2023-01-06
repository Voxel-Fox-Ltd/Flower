from typing import Optional, cast

import discord
from discord.ext import commands, vbu

from cogs import utils


if __debug__:
    _poedit = lambda x: x

    # TRANSLATORS: Name of a command. Must be lowercase.
    _poedit("experience")
    # TRANSLATORS: Description for a command.
    _poedit("Get the amount of experience you have.")
    # TRANSLATORS: Name of a command option. Must be lowercase.
    _poedit("user")
    # TRANSLATORS: Description for a command option.
    _poedit("The user to get info about.")

    # TRANSLATORS: Name of a command. Must be lowercase.
    _poedit("inventory")
    # TRANSLATORS: Description for a command.
    _poedit("Get the inventory of a user.")
    # TRANSLATORS: Name of a command option. Must be lowercase.
    _poedit("user")
    # TRANSLATORS: Description for a command option.
    _poedit("The user to get inventory of.")


_t = lambda i, x: vbu.translation(i, "flower").gettext(x)


class UserInfoCommands(vbu.Cog[utils.types.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "experience")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Get the amount of experience you have.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user to get info about.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=False,
                    name_localizations={
                        i: _t(i, "user")
                        for i in discord.Locale
                    },
                    description_localizations={
                        i: _t(i, "The user to get info about.")
                        for i in discord.Locale
                    },
                ),
            ],
        ),
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def experience(
            self,
            ctx: vbu.SlashContext,
            user: Optional[discord.Member] = None):
        """
        Get the amount of experience you have.
        """

        # Get the user
        user = user or ctx.author  # pyright: ignore - recast
        user = cast(discord.Member, user)

        # Get the experience
        async with vbu.Database() as db:
            user_object = await utils.UserInfo.fetch_by_id(db, user.id)

        # Send the experience
        if user.id == ctx.author.id:
            message = _("You have {experience} experience.").format(
                experience=user_object.experience,
            )
        else:
            message = _("{user} has {experience} experience.").format(
                user=user.mention,
                experience=user_object.experience,
            )
        await ctx.interaction.response.send_message(message)

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "inventory")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Get the inventory of a user.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user to get inventory of.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=False,
                    name_localizations={
                        i: _t(i, "user")
                        for i in discord.Locale
                    },
                    description_localizations={
                        i: _t(i, "The user to get inventory of.")
                        for i in discord.Locale
                    },
                ),
            ],
        ),
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def inventory(
            self,
            ctx: vbu.SlashContext,
            user: Optional[discord.Member] = None):
        """
        Get the inventory of a user.
        """

        # Get the user
        user = user or ctx.author  # pyright: ignore - recast
        user = cast(discord.Member, user)

        # Get the inventory and plants
        async with vbu.Database() as db:
            user_info = await utils.UserInfo.fetch_by_id(db, user.id)
            inv_object = await utils.UserInventory.fetch_by_id(db, user.id)
            user_plants = await utils.UserPlant.fetch_all_by_user_id(db, user.id)

        # Build an embed
        embed = vbu.Embed(
            use_random_colour=True,
        )
        embed.set_author_to_user(user)  # pyright: ignore

        # Get the user's plants
        plant_list: list[str] = []
        for plant in user_plants:
            name_row = f"\N{BULLET} **{plant.name}**"
            if plant.is_dead:
                name_row += " :("
            plant_list.append(name_row)
            plant_list.append(f"\u2003\N{BULLET} {plant.plant.display_name}")
            if not plant.is_dead:
                formatted_adoption = discord.utils.format_dt(plant.adoption_time, "R")
                plant_list.append(f"\u2003\N{BULLET} adopted {formatted_adoption}")
                formatted_watered = discord.utils.format_dt(plant.last_water_time, "R")
                plant_list.append(f"\u2003\N{BULLET} last watered {formatted_watered}")

        plant_string = "\n".join(plant_list)
        if plant_string:
            embed.add_field(
                name=_("Plants"),
                value=plant_string,
                inline=False,
            )

        # Get the user's items
        item_list: list[str] = [
            f"\N{BULLET} **Experience**: ${user_info.experience:,}"
        ]
        for item in inv_object.items.values():
            if item.amount <= 0:
                continue
            item_list.append(
                f"\N{BULLET} **{item.display_name.capitalize()}**: {item.amount:,}"
            )
        item_string = "\n".join(sorted(item_list))
        if item_string:
            embed.add_field(
                name=_("Items"),
                value=item_string,
                inline=False,
            )

        # Send the embed
        await ctx.interaction.response.send_message(embeds=[embed])

    @commands.context_command(
        name="Get user inventory",
        description="Get the inventory of a user.",
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "Get user inventory")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Get the inventory of a user.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user to get inventory of.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=True,
                    name_localizations={
                        i: _t(i, "user")
                        for i in discord.Locale
                    },
                    description_localizations={
                        i: _t(i, "The user to get the inventory of.")
                        for i in discord.Locale
                    },
                ),
            ],
        ),
    )
    async def inventory_context_command(
            self,
            ctx: vbu.SlashContext,
            user: discord.User):
        return await self.inventory(ctx, user=user)


def setup(bot: utils.types.Bot):
    x = UserInfoCommands(bot)
    bot.add_cog(x)
