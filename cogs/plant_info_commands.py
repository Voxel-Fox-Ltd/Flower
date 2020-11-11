import json
import random

import discord
from discord.ext import commands

from cogs import utils


class PlantInfoCommands(utils.Cog):

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self._artist_info = None

    @property
    def artist_info(self):
        if self._artist_info:
            return self._artist_info
        with open("images/artists.json") as a:
            data = json.load(a)
        self._artist_info = data
        return data

    @commands.command(cls=utils.Command, aliases=['describe', 'info', 'information'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def herbiary(self, ctx:utils.Context, *, plant_name:str=None):
        """Get the information for a given plant"""

        # See if a name was given
        if plant_name is None:
            with utils.Embed(use_random_colour=True) as embed:
                plants = sorted(self.bot.plants.values(), key=lambda x: (x.plant_level, x.name))
                embed.description = '\n'.join([f"**{i.display_name.capitalize()}** - level {i.plant_level}" for i in plants])
            return await ctx.send(embed=embed)

        # See if the given name is valid
        plant_name = plant_name.replace(' ', '_').lower()
        if plant_name not in self.bot.plants:
            return await ctx.send(f"There's no plant with the name **{plant_name.replace('_', ' ')}** :c", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        plant = self.bot.plants[plant_name]

        # Work out our artist info to be displayed
        description_list = []
        artist_info = self.artist_info[plant.artist].copy()
        discord_id = artist_info.pop('discord', None)
        if discord_id:
            description_list.append(f"**Artist `{plant.artist}`**")
            description_list.append(f"Discord: <@{discord_id}> (`{discord_id}`)")
        else:
            description_list.append(f"**Artist `{plant.artist}`**")
        for i, o in sorted(artist_info.items()):
            description_list.append(f"{i.capitalize()}: [Link]({o})")
        description_list.append("")

        # Work out some other info we want displayed
        description_list.append(f"Plant level {plant.plant_level}")
        description_list.append(f"Costs {plant.required_experience} exp")
        description_list.append(f"Gives between {plant.experience_gain['minimum']} and {plant.experience_gain['maximum']} exp")

        # Embed the data
        with utils.Embed(use_random_colour=True) as embed:
            embed.title = plant.display_name.capitalize()
            embed.description = '\n'.join(description_list)
            embed.set_image("attachment://plant.png")
        display_cog = self.bot.get_cog("PlantDisplayCommands")
        plant_image_bytes = display_cog.image_to_bytes(display_cog.get_plant_image(plant.name, 0, 21, "clay", random.randint(0, 360)))
        await ctx.send(embed=embed, file=discord.File(plant_image_bytes, filename="plant.png"))


def setup(bot:utils.Bot):
    x = PlantInfoCommands(bot)
    bot.add_cog(x)
