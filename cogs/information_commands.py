from __future__ import annotations

import json
import random

import discord
from discord.ext import commands, vbu


class InformationCommands(vbu.Cog):

    def __init__(self, bot: vbu.Bot):
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

    @vbu.command(argument_descriptions=(
        "The name of the plant that you want to see the information for.",
    ))
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def herbiary(self, ctx: vbu.Context, *, plant_name: str = None):
        """
        Get the information for a given plant.
        """

        # See if a name was given
        if plant_name is None:
            plant_list = list()
            for plant in self.bot.plants.values():
                plant_list.append(plant.display_name.capitalize())
            plant_list.sort()
            embed = vbu.Embed(use_random_colour=True, description="\n".join(plant_list))
            ctx.bot.set_footer_from_config(embed)
            return await ctx.send(embed=embed)

        # See if the given name is valid
        plant_name = plant_name.replace(' ', '_').lower()
        if plant_name not in self.bot.plants:
            return await ctx.send(f"There's no plant with the name **{plant_name.replace('_', ' ')}** :c", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        plant = self.bot.plants[plant_name]

        # Work out our artist info to be displayed
        description_list = []
        artist_info = self.artist_info.get(plant.artist, {}).copy()
        discord_id = artist_info.pop('discord', None)
        description_list.append(f"**Artist `{plant.artist}`**")
        if discord_id:
            description_list.append(f"Discord: <@{discord_id}> (`{discord_id}`)")
        for i, o in sorted(artist_info.items()):
            description_list.append(f"{i.capitalize()}: [Link]({o})")
        description_list.append("")

        # Embed the data
        with vbu.Embed(use_random_colour=True) as embed:
            embed.title = plant.display_name.capitalize()
            embed.description = '\n'.join(description_list)
            embed.set_image("attachment://plant.gif")
            ctx.bot.set_footer_from_config(embed)
        display_vbu = self.bot.get_cog("PlantDisplayUtils")

        # Make a gif of the stages
        pot_hue = random.randint(0, 360)
        display_levels = []
        added_display_stages = []
        for i, o in plant.nourishment_display_levels.items():
            if o not in added_display_stages:
                display_levels.insert(0, int(i))
                added_display_stages.append(o)
        gif_frames = [display_vbu.get_plant_image(plant.name, i, "clay", pot_hue) for i in display_levels]
        plant_image_bytes = display_vbu.gif_to_bytes(*gif_frames, duration=1_000)
        await ctx.send(embed=embed, file=discord.File(plant_image_bytes, filename="plant.gif"))

    @vbu.command()
    @commands.bot_has_permissions(send_messages=True)
    async def volunteer(self, ctx:vbu.Context):
        """
        Get the information for volunteering.
        """

        VOLUNTEER_INFORMATION = (
            "Want to help out with Flower, and watch it grow? Heck yeah! There's a few ways you can help out:\n\n"
            "**Art**\n"
            "Flower takes a lot of art, being a bot entirely about watching things grow. Unfortunately, I'm awful at art. Anything you can help out "
            "with would be amazing, if you had some kind of artistic talent yourself. If you [go here](https://github.com/Voxel-Fox-Ltd/Flower/blob/master/images/pots/clay/full.png) "
            "you can get an empty pot image you can use as a base. Every plant in Flower has a minimum of 6 distinct growth stages "
            "(which you can [see here](https://github.com/Voxel-Fox-Ltd/Flower/tree/master/images/plants/blue_daisy/alive) if you need an example).\n"
            "If this is the kind of thing you're interested in, I suggest you join [the support server](https://discord.gg/vfl) to ask for more information, or "
            "[email Kae](mailto://kae@voxelfox.co.uk) - the bot's developer.\n"
            "\n"
            "**Programming**\n"
            "If you're any good at programming, you can help out on [the bot's Github](https://github.com/Voxel-Fox-Ltd/Flower)! Ideas are discussed on "
            "[the support server](https://discord.gg/vfl) if you want to do that, but otherwise you can PR fixes, add issues, etc from there as you would "
            "with any other git repository.\n"
            "\n"
            "**Ideas**\n"
            "Flower is in constant need of feedback from the people who like to use it, and that's where you can shine. Even if you don't want to "
            "help out with art, programming, or anything else: it would be _absolutely amazing_ if you could give your experiences, gripes, and suggestions for "
            "Flower via the `{ctx.clean_prefix}suggest` command. That way I know where to change things, what to do to add new stuff, etcetc. If you want to "
            "discuss in more detail, I'm always around on [the support server](https://discord.gg/vfl)."
        ).format(ctx=ctx)
        embed = vbu.Embed(
            use_random_colour=True,
            description=VOLUNTEER_INFORMATION,
        )
        ctx.bot.set_footer_from_config(embed)
        try:
            await ctx.author.send(embed=embed)
        except discord.HTTPException:
            return await ctx.send("I wasn't able to send you a DM :<")
        if ctx.guild is not None:
            return await ctx.send("Sent you a DM!")


def setup(bot: vbu.Bot):
    x = InformationCommands(bot)
    bot.add_cog(x)
