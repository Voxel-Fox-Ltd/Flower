import json
import random

import discord
from discord.ext import commands

from cogs import utils


class PlantInfoCommands(utils.Cog):

    def __init__(self, bot:utils.Bot):
        self.bot = bot
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
    async def herbiary(self, ctx:utils.Context, *, plant_name:str):
        """Get the information for a given plant"""

        # See if the given name is valid
        plant_name = plant_name.replace(' ', '_').lower()
        if plant_name not in self.bot.plants:
            return await ctx.send(f"There's no plant with the name **{plant_name.replace('_', ' ')}** :c", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        plant = self.bot.plants[plant_name]

        # Work out our artist info to be displayed
        artist_info_embed_list = []
        artist_info = self.artist_info[plant.artist].copy()
        discord_id = artist_info.pop('discord', None)
        if discord_id:
            user = await self.bot.fetch_user(discord_id)
            artist_info_embed_list.append(f"**Artist `{user!s}`**")
            artist_info_embed_list.append(f"Discord: {user.mention}")
        else:
            artist_info_embed_list.append(f"**Artist `{plant.artist}`**")
        for i, o in sorted(artist_info.items()):
            artist_info_embed_list.append(f"{i.capitalize()}: [Link]({o})")

        # Embed the data
        with utils.Embed(use_random_colour=True) as embed:
            embed.title = plant.display_name.capitalize()
            embed.description = '\n'.join(artist_info_embed_list)
            embed.set_image("attachment://plant.png")
        display_cog = self.bot.get_cog("PlantDisplayCommands")
        plant_image_bytes = display_cog.image_to_bytes(display_cog.get_plant_image(plant.name, 0, 21, "clay", random.randint(0, 360)))
        await ctx.send(embed=embed, file=discord.File(plant_image_bytes, filename="plant.png"))


def setup(bot:utils.Bot):
    x = PlantInfoCommands(bot)
    bot.add_cog(x)
