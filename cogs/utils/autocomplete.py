from typing import TYPE_CHECKING, List

import discord
from discord.ext import commands, vbu

if TYPE_CHECKING:
    from .types import PlantLevelsRow


__all__ = (
    'plant_name_autocomplete',
)


async def plant_name_autocomplete(
        cog: commands.Cog,
        ctx: commands.SlashContext,
        interaction: discord.Interaction) -> None:
    """
    Completes the name autocomplete for the plants of a given user.
    """

    # Get the valid user ID
    user_id: int = interaction.user.id

    # Get the options
    options: List[discord.ApplicationCommandInteractionDataOption]
    options = interaction.options  # type: ignore
    if options[0].focused:
        pass  # The current option is the plant name
    else:
        # This option MAY be a user
        option = options[0]
        if option.type == discord.ApplicationCommandOptionType.user and interaction.resolved.users:
            user_id = list(interaction.resolved.users.values())[0].id

    # Get the user's plants
    async with vbu.Database() as db:
        rows = await db.call(
            """
            SELECT
                *
            FROM
                plant_levels
            WHERE
                user_id = $1
            """,
            user_id,
            type=PlantLevelsRow,
        )

    # Return autocomplete
    await interaction.response.send_autocomplete([
        discord.ApplicationCommandOptionChoice(name=i['plant_name'])
        for i in rows
    ])
