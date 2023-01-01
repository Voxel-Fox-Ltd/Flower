import discord
from discord.ext import vbu, commands

from cogs import utils


if __debug__:
    _poedit = lambda x: x

    # TRANSLATORS: This is the name of a category of commands
    "key"
    # TRANSLATORS: Command description.
    "A parent group for the key commands."

    # TRANSLATORS: Command name.
    "give"
    # TRANSLATORS: Command description.
    "Give a user access to your garden."
    # TRANSLATORS: Command option name.
    "user"
    # TRANSLATORS: Command option description.
    "The user who you want to give a key to."

    # TRANSLATORS: Command name.
    "remove"
    # TRANSLATORS: Command description.
    "Remove a user's access to your garden."


_t = lambda i, x: vbu.translation(i, "flower").gettext(x)


class KeyCommands(vbu.Cog[utils.types.Bot]):

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "key")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "A parent group for the key commands.")
                for i in discord.Locale
            },
        ),
    )
    async def key(self, _: vbu.SlashContext):
        """
        A parent group for the key commands.
        """

        pass

    @key.command(
        name="give",
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "give")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Give a user access to your garden.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user who you want to give a key to.",
                    type=discord.ApplicationCommandOptionType.user,
                    name_localizations={
                        i: _t(i, "user")
                        for i in discord.Locale
                    },
                    description_localizations={
                        i: _t(i, "The user who you want to give a key to.")
                        for i in discord.Locale
                    },
                ),
            ],
        ),
    )
    @vbu.i18n("flower")
    async def key_give(
            self,
            ctx: vbu.SlashContext,
            user: discord.User):
        """
        Give a user access to your garden.
        """

        async with vbu.Database() as db:
            await db.call(
                """
                INSERT INTO
                    user_garden_access
                    (
                        garden_access,
                        garden_owner
                    )
                VALUES
                    (
                        $1,
                        $2
                    )
                ON CONFLICT
                    (garden_access, garden_owner)
                DO NOTHING
                """,
                user.id, ctx.interaction.user.id
            )
        command_mention = "/waterother"
        if (comm := self.bot.get_command("waterother")):
            command_mention = comm.mention
        return await ctx.interaction.response.send_message(
            (
                _(
                    "You have given {user} access to your garden. They can now "
                    "water your plants with the {waterother} command."
                )
                .format(
                    user=user.mention,
                    waterother=command_mention,
                )
            ),
        )

    @key.command(
        name="remove",
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "remove")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Remove a user's access to your garden.")
                for i in discord.Locale
            },
        ),
    )
    @vbu.i18n("flower")
    async def key_remove(
            self,
            ctx: vbu.SlashContext):
        """
        Remove a user's access to your garden.
        """

        # Get a list of all the users who currently have garden access
        async with vbu.Database() as db:
            rows = await db.call(
                """
                SELECT
                    garden_access
                FROM
                    user_garden_access
                WHERE
                    garden_owner = $1
                """,
                ctx.interaction.user.id
            )

        # If there are no users with access, return
        if not rows:
            return await ctx.interaction.response.send_message(
                _("There are currently no users with access to your garden."),
                ephemeral=True
            )

        # Otherwise we cna send them a dropdown
        await ctx.interaction.response.send_message(
            _("Who do you want to remove access to your garden from?"),
            components=discord.ui.MessageComponents(
                discord.ui.ActionRow(
                    discord.ui.UserSelectMenu(
                        custom_id="KEY REMOVE",
                    ),
                ),
            ),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    async def key_remove_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for the key remove component.
        """

        # If it's not the key remove component, return
        if interaction.custom_id != "KEY REMOVE":
            return

        # Otherwise, remove the user from the database
        async with vbu.Database() as db:
            rows = await db.call(
                """
                DELETE FROM
                    user_garden_access
                WHERE
                    garden_owner = $1
                AND
                    garden_access = $2
                RETURNING
                    *
                """,
                interaction.user.id, int(interaction.values[0])
            )
        if rows:
            return await interaction.response.edit_message(
                content=(
                    _("You have removed access to your garden from {user}.")
                    .format(user=f"<@{interaction.values[0]}>")
                ),
                components=None,
            )
        return await interaction.response.send_message(
            content=(
                _("{user} doesn't have a key to your garden!")
                .format(user=f"<@{interaction.values[0]}>")
            ),
            ephemeral=True,
        )


def setup(bot: utils.types.Bot):
    x = KeyCommands(bot)
    bot.add_cog(x)
