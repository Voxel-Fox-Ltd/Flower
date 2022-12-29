from typing import Optional, cast

import discord
from discord.ext import commands, vbu

from cogs import utils


_t = lambda i, x: vbu.translation(i, "flower").gettext(x)


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

        # Get the inventory
        async with vbu.Database() as db:
            inv_object = await utils.UserInventory.fetch_by_id(db, user.id)

        # Build an embed
        embed = vbu.Embed(
            title=_("Inventory"),
        )
        description_list: list[str] = []
        for item in inv_object.items.values():
            if item.amount <= 0:
                continue
            description_list.append(f"{item.name.title()}: {item.amount}\n")
        embed.description = "\n".join(sorted(description_list))

        # And send
        if not description_list:
            await ctx.interaction.response.send_message(
                _("This inventory is empty :("),
            )
        else:
            await ctx.interaction.response.send_message(
                embeds=[
                    embed,
                ],
            )


def setup(bot: utils.types.Bot):
    x = UserInfoCommands(bot)
    bot.add_cog(x)
