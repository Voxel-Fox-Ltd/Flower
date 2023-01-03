from __future__ import annotations

import json
import random
from typing import TYPE_CHECKING, Dict, List, Optional

import discord
from discord.ext import commands, vbu

from cogs import utils

if TYPE_CHECKING:
    import io

    from PIL import Image

    from .plant_display_utils import PlantDisplayUtils


if __debug__:
    _poedit = lambda x: x

    # TRANSLATORS: Name of a command. Must be lowercase.
    _poedit("herbiary")
    # TRANSLATORS: Description of a command.
    _poedit("Get the information for a given plant.")
    # TRANSLATORS: Name of a command option. Must be lowercase.
    _poedit("plant")
    # TRANSLATORS: Description of a command option.
    _poedit(
        "The name of the plant that you want to see "
        "the information for."
    )


_t = lambda i, x: vbu.translation(i, "flower").gettext(x)


class HerbiaryCommands(vbu.Cog[utils.types.Bot]):

    def __init__(self, bot: utils.types.Bot):
        super().__init__(bot)
        self._artist_info: Dict[str, utils.types.ArtistInfo] = {}

    @property
    def artist_info(self) -> Dict[str, utils.types.ArtistInfo]:
        """
        Get the artist info for each of the people. Caches if this is the
        first read, returns cached if not.
        """

        if self._artist_info:
            return self._artist_info
        with open("images/artists.json") as a:
            data = json.load(a)
        self._artist_info = data
        return data

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "herbiary")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Get the information for a given plant.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="plant",
                    description=(
                        "The name of the plant that you want to see the "
                        "information for."
                    ),
                    type=discord.ApplicationCommandOptionType.string,
                    required=False,
                    name_localizations={
                        i: _t(i, "plant")
                        for i in discord.Locale
                    },
                    description_localizations={
                        i: _t(
                            i, (
                                "The name of the plant that you want to see "
                                "the information for."
                            )
                        )
                        for i in discord.Locale
                    },
                ),
            ],
        ),
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def herbiary(
            self,
            ctx: vbu.SlashContext,
            *,
            plant: Optional[str] = None):
        """
        Get the information for a given plant.
        """

        # See if a name was given
        if plant is None:
            plant_list = list()
            for plant_object in self.bot.plants.values():
                if plant_object.available is False or plant_object.visible is False:
                    continue
                plant_list.append(plant_object.display_name.capitalize())
            plant_list.sort()
            embed = vbu.Embed(
                use_random_colour=True,
                description="\n".join(plant_list),
            )
            self.bot.set_footer_from_config(embed)
            return await ctx.interaction.response.send_message(embed=embed)

        # See if the given name is valid
        plant = plant.replace(' ', '_').lower()
        if plant not in self.bot.plants:
            return await ctx.interaction.response.send_message(
                _("There's no plant with that name."),
                allowed_mentions=discord.AllowedMentions.none()
            )
        plant_object = self.bot.plants[plant]

        # Work out our artist info to be displayed
        description_list = []
        artist_info = self.artist_info.get(plant_object.artist, {}).copy()
        discord_id: str | None = artist_info.pop('discord', None)  # pyright: ignore
        description_list.append(f"**Artist `{plant_object.artist}`**")
        if discord_id:
            description_list.append(f"Discord: <@{discord_id}> (`{discord_id}`)")
        for i, o in sorted(artist_info.items()):
            description_list.append(f"{i.capitalize()}: [Link]({o})")
        description_list.append("")

        # Embed the data
        with vbu.Embed(use_random_colour=True) as embed:
            embed.title = plant_object.display_name.capitalize()
            embed.description = '\n'.join(description_list)
            embed.set_image("attachment://plant.gif")
            ctx.bot.set_footer_from_config(embed)
        display_vbu: Optional[PlantDisplayUtils]
        display_vbu = self.bot.get_cog("PlantDisplayUtils")  # pyright: ignore
        assert display_vbu, "PlantDisplayUtils not loaded"

        # Make a gif of the stages
        pot_hue: int = random.randint(0, 360)  # Get a random colour
        display_levels: List[int] = []  # All display stages
        added_display_stages: List[int] = []  # All unique display stages
        for i, o in plant_object.nourishment_display_levels.items():
            if o not in added_display_stages:
                display_levels.insert(0, int(i))
                added_display_stages.append(o)
        gif_frames: List[Image.Image] = [
            display_vbu.get_plant_image(plant_object.name, i, "clay", pot_hue)
            for i in [0, *display_levels]
        ]
        plant_image_bytes: io.BytesIO = display_vbu.gif_to_bytes(
            *gif_frames[::-1],
            duration=1_000,
        )

        # And send image
        return await ctx.interaction.response.send_message(
            embed=embed,
            file=discord.File(
                plant_image_bytes,
                filename="plant.gif",
            ),
        )


def setup(bot: utils.types.Bot):
    x = HerbiaryCommands(bot)
    bot.add_cog(x)
