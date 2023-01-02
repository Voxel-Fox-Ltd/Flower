import discord
from discord.ext import vbu, commands

from cogs import utils


class TradeCommands(vbu.Cog[utils.types.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user who you want to give items to.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=True,
                ),
            ],
        ),
    )
    @vbu.i18n("flower")
    async def giveitem(
            self,
            ctx: commands.SlashContext,
            user: discord.User):
        """
        Give one of your items to another user.
        """

        # Make sure they arne't giving it to themselves
        if user == ctx.author:
            return await ctx.interaction.response.send_message(
                _("You can't give items to yourself!"),
                ephemeral=True,
            )

        # Get the user's inventory
        async with vbu.Database() as db:
            user_inventory = await utils.UserInventory.fetch_by_id(
                db,
                ctx.interaction.user.id,
            )

        # Make sure they have items to give
        if sum(i.amount for i in user_inventory.items.values()) <= 0:
            return await ctx.interaction.response.send_message(
                _("You don't have any items to give!"),
                ephemeral=True,
            )

        # Give them a dropdown of items to give
        await ctx.interaction.response.send_message(
            _("What item would you like to give?"),
            components=discord.ui.MessageComponents(
                discord.ui.ActionRow(
                    discord.ui.SelectMenu(
                        custom_id=f"GIVEITEM {user.id}",
                        options=[
                            discord.ui.SelectOption(
                                label=item.display_name.capitalize(),
                                value=key,
                            )
                            for key, item in user_inventory.items.items()
                            if item.amount > 0
                        ],
                    ),
                ),
            ),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("flower")
    async def give_item_dropdown_select(
            self,
            interaction: discord.ComponentInteraction):
        """
        Give an item to a user.
        """

        # Make sure it's the right dropdown
        if not interaction.custom_id.startswith("GIVEITEM "):
            return

        # Get the user to give it to
        user_id = int(interaction.custom_id.split(" ")[1])

        # Get the user's inventory
        async with vbu.Database() as db:
            user_inventory = await utils.UserInventory.fetch_by_id(
                db,
                interaction.user.id,
            )
            given_inventory = await utils.UserInventory.fetch_by_id(
                db,
                user_id,
            )

            # Get the item they selected
            item_key = interaction.values[0]
            item = user_inventory.get(item_key)
            if item.amount <= 0:
                return await interaction.response.send_message(
                    _("You don't have enough of that item to give."),
                    ephemeral=True,
                )

            # Give them the item
            async with db.transaction() as trans:
                await user_inventory.update(trans, **{item_key: -1})
                await given_inventory.update(trans, **{item_key: 1})
            await utils.update_achievement_count(
                db,
                interaction.user.id,
                utils.Achievement.gives,
            )

        # Send a message
        await interaction.response.defer_update()
        message: str = _("You gave {user} 1x {item}!").format(
            user=f"<@{user_id}>",
            item=item.name,
        )
        try:
            await interaction.channel.send(message)  # pyright: ignore
        except discord.HTTPException:
            await interaction.followup.send(message)


def setup(bot: utils.types.Bot):
    x = TradeCommands(bot)
    bot.add_cog(x)
