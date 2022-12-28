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
        Rename a plant.
        """

        async with vbu.Database() as db:

            # Get the plant
            plant_object = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                plant,
            )
            if not plant_object:
                return await ctx.send(f"You don't have a plant named {plant}.")

            # See if that name is already in use
            plant_with_name = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                new_name,
            )
            if plant_with_name:
                return await ctx.interaction.response.send_message(
                    _("You already have a plant named {name}.")
                    .format(name=new_name)
                )

            # And rename if not
            await plant_object.update(
                db,
                name=new_name,
            )
        await ctx.interaction.response.send_message(
            _("Successfully renamed your plant to {name}.")
            .format(name=new_name)
        )


