from typing import Literal
import discord
from discord.ext import commands, vbu

from cogs import utils


class PlantManagement(vbu.Cog[utils.types.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="plant",
                    description="The plant that you want to rename.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                    autocomplete=True,
                ),
                discord.ApplicationCommandOption(
                    name="new_name",
                    description="The new name for the plant.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                ),
            ]
        )
    )
    async def rename(
            self,
            ctx: vbu.SlashContext,
            plant: str,
            new_name: str):
        """
        Rename one of your plants.
        """

        new_name = new_name.strip()
        async with vbu.Database() as db:

            # Get the plant
            plant_object = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                plant,
            )
            if not plant_object:
                return await ctx.send(
                    _("You don't have a plant named **{plant}**.")
                        .format(plant=plant),
                    ephemeral=True,
                )

            # See if that name is already in use
            plant_with_name = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                new_name,
            )
            if plant_with_name:
                return await ctx.interaction.response.send_message(
                    _("You already have a plant named **{name}**.")
                        .format(name=new_name),
                    ephemeral=True,
                )

            # And rename if not
            await plant_object.update(
                db,
                name=new_name,
            )
        await ctx.interaction.response.send_message(
            _("Successfully renamed your plant to {name}.")
                .format(name=new_name),
            ephemeral=True,
        )

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="plant",
                    description="The plant that you want to delete.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                    autocomplete=True,
                ),
            ],
        ),
    )
    async def delete(
            self,
            ctx: vbu.SlashContext,
            plant: str):
        """
        Delete a one of your plants.
        """

        async with vbu.Database() as db:

            # Get the plant
            plant_object = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                plant,
            )
        if not plant_object:
            return await ctx.interaction.response.send_message(
                _("You don't have a plant named **{plant}**.")
                    .format(plant=plant),
                ephemeral=True,
            )

        # Ask if they're sure they want to delete it
        return await ctx.interaction.response.send_message(
            _("Are you sure you want to delete your plant **{name}**?")
                .format(name=plant),
            components=discord.ui.MessageComponents(
                discord.ui.ActionRow(
                    discord.ui.Button(
                        label=_("Yes"),
                        style=discord.ButtonStyle.green,
                        custom_id=f"DELETEPLANT {plant} 1",
                    ),
                    discord.ui.Button(
                        label=_("No"),
                        style=discord.ButtonStyle.red,
                        custom_id=f"DELETEPLANT {plant} 0",
                    ),
                ),
            ),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.checks.interaction_filter(start="DELETEPLANT")
    async def on_delete_button_pressed(
            self,
            interaction: discord.ComponentInteraction,
            plant_name: str,
            delete: Literal["1", "0"]):
        """
        Delete a plant if the delete plant button is pressed.
        """

        # See if we want to delete the plant
        if delete == "0":
            await interaction.response.edit_message(
                content=_("Not deleting your plant **{name}**.")
                    .format(name=plant_name),
                components=None,
            )
            return

        # Get the plant from the database
        async with vbu.Database() as db:
            plant_object = await utils.UserPlant.fetch_by_name(
                db,
                interaction.user.id,
                plant_name,
            )
            if not plant_object:
                return await interaction.response.edit_message(
                    content=_("You don't have a plant named **{plant}**.")
                        .format(plant=plant_name),
                    components=None,
                )

            # Delete the plant
            await plant_object.delete(db)

        # And tell the user
        await interaction.response.edit_message(
            content=_("Successfully deleted your plant."),
            components=None,
        )

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="plant",
                    description="The plant that you want to immortalize.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                    autocomplete=True,
                ),
            ],
        ),
    )
    async def immortalize(
            self,
            ctx: vbu.SlashContext,
            plant: str):
        """
        Immortalize one of your plants.
        """

        async with vbu.Database() as db:

            # Get the plant
            plant_object = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                plant,
            )
            if not plant_object:
                return await ctx.interaction.response.send_message(
                    _("You don't have a plant named **{plant}**.")
                        .format(plant=plant),
                    ephemeral=True,
                )

            # See if it's already immortalized
            if plant_object.immortal:
                return await ctx.interaction.response.send_message(
                    _("Your plant **{name}** is already immortal.")
                        .format(name=plant),
                    ephemeral=True,
                )

            # See if they have any immortal plant juice
            user_inventory = await utils.UserInventory.fetch_by_id(
                db,
                ctx.author.id,
            )
            if user_inventory.get("immortal_plant_juice").amount < 1:
                shop_command_mention: str = self.bot.get_command("shop").mention  # pyright: ignore
                return await ctx.interaction.response.send_message(
                    _(
                        "You don't have any immortal plant juice. You can get "
                        "some from the {shop_command_mention}."
                    ).format(shop_command_mention=shop_command_mention),
                    ephemeral=True,
                )

        # Ask if they're sure they want to immortalize it
        return await ctx.interaction.response.send_message(
            _(
                "Are you sure you want to immortalize your plant **{name}**? "
                "Doing so will mean that you only get half the amount of "
                "experience from it, but it will never die."
            ).format(name=plant),
            components=discord.ui.MessageComponents(
                discord.ui.ActionRow(
                    discord.ui.Button(
                        label=_("Yes"),
                        style=discord.ButtonStyle.green,
                        custom_id=f"IMMORTALIZEPLANT {plant} 1",
                    ),
                    discord.ui.Button(
                        label=_("No"),
                        style=discord.ButtonStyle.red,
                        custom_id=f"IMMORTALIZEPLANT {plant} 0",
                    ),
                ),
            ),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.checks.interaction_filter(start="IMMORTALIZEPLANT")
    async def on_immortalize_button_pressed(
            self,
            interaction: discord.ComponentInteraction,
            plant_name: str,
            immortalize: Literal["1", "0"]):
        """
        Immortalize a plant if the immortalize plant button is pressed.
        """

        # See if we want to immortalize the plant
        if immortalize == "0":
            await interaction.response.edit_message(
                content=_("Not immortalizing your plant **{name}**.")
                    .format(name=plant_name),
                components=None,
            )
            return

        # Get the plant from the database
        async with vbu.Database() as db:
            plant_object = await utils.UserPlant.fetch_by_name(
                db,
                interaction.user.id,
                plant_name,
            )
            if not plant_object:
                return await interaction.response.edit_message(
                    content=_("You don't have a plant named **{plant}**.")
                        .format(plant=plant_name),
                    components=None,
                )

            # Immortalize the plant
            await plant_object.update(
                db,
                immortal=True,
            )

        # And tell the user
        await interaction.response.edit_message(
            content=_("Successfully immortalized your plant."),
            components=None,
        )


def setup(bot: utils.types.Bot):
    x = PlantManagement(bot)
    bot.add_cog(x)
