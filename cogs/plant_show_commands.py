import discord
from discord.ext import vbu, commands

from cogs import utils


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
    @vbu.i18n("flower")
    async def show(
            self,
            ctx: vbu.SlashContext,
            plant: str):
        """
        Take a look at one of your plants.
        """

        # Get the plant that they want to look at
        async with vbu.Database() as db:
            user_plant = await utils.UserPlant.fetch_by_name(
                db,
                ctx.author.id,
                plant,
            )
            if user_plant is None:
                return await ctx.interaction.response.send_message(
                    _("You have no plant named **{plant}**")
                        .format(plant=plant.capitalize()),
                    ephemeral=True,
                )

        # Defer so we can perform our intensive display operation
        await ctx.interaction.response.defer()

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
        await ctx.interaction.followup.send(
            embeds=[embed],
            files=[image_file],
        )

    show.autocomplete(utils.autocomplete.get_plant_name_autocomplete())  # pyright: ignore


def setup(bot: utils.types.Bot):
    x = PlantShowCommands(bot)
    bot.add_cog(x)
