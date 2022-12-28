from typing import TYPE_CHECKING, Optional, cast

import discord
from discord.ext import commands, vbu

from cogs import utils

if TYPE_CHECKING:
    from .utils.types import (
        Bot,
    )


class UserInfoCommands(vbu.Cog[Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user to get info about.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=False,
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
                experience=user_object.user_experience,
            )
        else:
            message = _("{user} has {experience} experience.").format(
                user=user.mention,
                experience=user_object.user_experience,
            )
        await ctx.interaction.response.send_message(message)

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user to get inventory of.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=False,
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
        await ctx.interaction.response.send_message(
            embeds=[
                embed,
            ],
        )


def setup(bot: Bot):
    x = UserInfoCommands(bot)
    bot.add_cog(x)
