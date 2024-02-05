from typing import TYPE_CHECKING

import discord
from discord.ext import vbu, commands

from cogs import utils

if TYPE_CHECKING:
    from PIL import Image


if __debug__:
    _poedit = lambda x: x

    # Name of a command. Must be lowercase.
    _poedit("show")
    # Command description.
    _poedit("Take a look at one of your plants.")
    # Name of a command option. Must be lowercase.
    _poedit("plant")
    # Description of a command option.
    _poedit("The plant that you want to see.")

    # Name of a command. Must be lowercase.
    _poedit("showother")
    # Command description.
    _poedit("Take a look at one of someone else's plants.")
    # Name of a command option. Must be lowercase.
    _poedit("user")
    # Description of a command option.
    _poedit("The user whose plants you want to see.")
    # Name of a command option. Must be lowercase.
    _poedit("plant")
    # Description of a command option.
    _poedit("The plant that you want to see.")

    # Name of a command. Must be lowercase.
    _poedit("showall")
    # Command description.
    _poedit("Show all of your plants at once.")


_t = lambda i, x: vbu.translation(i, "flower").gettext(x)


class PlantShowCommands(vbu.Cog[utils.types.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "show")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Take a look at one of your plants.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="plant",
                    description="The plant that you want to see.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),
            ],
        ),
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def show(
            self,
            ctx: vbu.SlashContext,
            plant: str):
        """
        Take a look at one of your plants.
        """

        await self.show_plant(
            ctx.interaction,  # pyright: ignore
            ctx.interaction.user,  # pyright: ignore
            plant,
        )

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "showother")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Take a look at one of someone else's plants.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="user",
                    description="The user whose plants you want to see.",
                    type=discord.ApplicationCommandOptionType.user,
                    required=True,
                ),
                discord.ApplicationCommandOption(
                    name="plant",
                    description="The plant that you want to see.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                    required=True,
                ),
            ],
        ),
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def showother(
            self,
            ctx: vbu.SlashContext,
            user: discord.User,
            plant: str):
        """
        Take a look at one of someone else's plants.
        """

        await self.show_plant(
            ctx.interaction,  # pyright: ignore
            user,
            plant,
        )

    async def show_plant(
            self,
            interaction: discord.CommandInteraction,
            user: discord.User,
            plant_name: str):
        """
        Show a plant via the given interaction.
        """

        # Get the plant that they want to look at
        async with vbu.Database() as db:
            user_plant = await utils.UserPlant.fetch_by_name(
                db,
                user.id,
                plant_name,
            )
            if user_plant is None:
                if user.id == interaction.user.id:
                    message = (
                        _("You have no plant named **{plant}**.")
                        .format(plant=plant_name)
                    )
                else:
                    message = (
                        _("{user} has no plant named **{plant}**.")
                        .format(user=user.mention, plant=plant_name)
                    )
                return await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )

        # Defer so we can perform our intensive display operation
        await interaction.response.defer()

        # Get our image
        image = utils.PlantDisplayUtils.get_plant_image(
            user_plant.plant,
            user_plant.nourishment,
            "clay",
            user_plant.pot_hue,
        )
        image_bytes = utils.PlantDisplayUtils.image_to_bytes(image)
        image_file = discord.File(image_bytes, filename="plant.png")

        # Send them their plant in an embed
        embed = vbu.Embed(
            title=user_plant.name,
            use_random_colour=True,
        )
        embed.set_image(url="attachment://plant.png")
        self.bot.set_footer_from_config(embed)
        await interaction.followup.send(
            embeds=[embed],
            files=[image_file],
        )

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "showall")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Show all of your plants at once.")
                for i in discord.Locale
            },
        )
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def showall(self, ctx: vbu.SlashContext):
        """
        Show all of your plants at once.
        """

        # See if the user has premium
        user_premium = await utils.UserInfo.check_premium(ctx.author.id)
        if not user_premium:
            info_command = self.bot.get_command("info").mention  # pyright: ignore
            return await ctx.interaction.response.send_message(
                _(
                    "You need to be a premium subscriber to use this "
                    "command. Please see {info_command} to donate."
                ).format(info_command=info_command),
                ephemeral=True,
            )

        # Get some user information
        async with vbu.Database() as db:


            # Get all of their plants
            user_plants = await utils.UserPlant.fetch_all_by_user_id(
                db,
                ctx.author.id,
            )

        # Defer so we can perform our intensive display operation
        await ctx.interaction.response.defer()

        # Get our image
        images: list[Image.Image] = []
        for p in user_plants:
            images.append(utils.PlantDisplayUtils.get_plant_image(
                p.plant,
                p.nourishment,
                "clay",
                p.pot_hue,
            ))
        compiled = utils.PlantDisplayUtils.compile_plant_images(images)
        image_bytes = utils.PlantDisplayUtils.image_to_bytes(compiled)
        image_file = discord.File(image_bytes, filename="plants.png")

        # Send them their plant in an embed
        embed = vbu.Embed(use_random_colour=True)
        embed.set_image(url="attachment://plants.png")
        self.bot.set_footer_from_config(embed)
        await ctx.interaction.followup.send(
            embeds=[embed],
            files=[image_file],
        )

    show.autocomplete(utils.autocomplete.get_plant_name_autocomplete())  # pyright: ignore
    showother.autocomplete(utils.autocomplete.get_plant_name_autocomplete())  # pyright: ignore


def setup(bot: utils.types.Bot):
    x = PlantShowCommands(bot)
    bot.add_cog(x)
