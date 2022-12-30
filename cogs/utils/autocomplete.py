from typing import List
from difflib import SequenceMatcher

import discord
from discord.ext import vbu

from .models import UserPlant


__all__ = (
    'get_plant_name_autocomplete',
)


def get_plant_name_autocomplete(**filters):
    async def plant_name_autocomplete(
            cog: vbu.Cog,
            ctx: vbu.SlashContext,
            interaction: discord.AutocompleteInteraction) -> None:
        """
        Completes the name autocomplete for the plants of a given user.
        """

        # Get our initial user ID
        user_id: int = interaction.user.id

        # Get the options from the command
        options: List[discord.ApplicationCommandInteractionDataOption]
        options = interaction.options  # type: ignore

        # Try and get the plant name from the options
        current_name: str = ""
        if options[0].focused:
            current_name = options[0].value  # pyright: ignore

        # The first option wasn't focused - that should mean that the second option
        # is the typed name and the first is the user object
        else:
            option = options[0]
            if option.type == discord.ApplicationCommandOptionType.user:
                user_id = int(option.value)  # pyright: ignore
            current_name = options[1].value  # pyright: ignore

        # Get the user's plants
        async with vbu.Database() as db:
            user_plants = await UserPlant.fetch_all_by_user_id(db, user_id)

        # Create and sort the options according to how close their spelling is
        filtered_user_plants = user_plants
        for k, v in filters.items():
            filtered_user_plants = [
                i
                for i in user_plants
                if getattr(i, k) == v
            ]
        autocomplete_options = [
            discord.ApplicationCommandOptionChoice(
                name=i.name,
                value=i.name,
            )
            for i in filtered_user_plants
        ]
        autocomplete_options.sort(
            key=lambda c: (
                SequenceMatcher(
                    None,
                    c.name.casefold(),
                    (current_name or "").casefold(),
                ).quick_ratio()
            ),
            reverse=True,
        )

        # Return autocomplete
        await interaction.response.send_autocomplete(autocomplete_options)
    return plant_name_autocomplete
