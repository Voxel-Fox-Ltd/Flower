import json
import random

import discord
from discord.ext import commands
import voxelbotutils as utils


class InformationCommands(utils.Cog):

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

    @utils.command(aliases=['describe', 'info', 'information'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def herbiary(self, ctx:utils.Context, *, plant_name:str=None):
        """
        Get the information for a given plant.
        """

        # See if a name was given
        if plant_name is None:
            with utils.Embed(use_random_colour=True) as embed:
                plants = sorted(self.bot.plants.values(), key=lambda x: (x.plant_level, x.name))
                embed.description = '\n'.join([f"**{i.display_name.capitalize()}** - level {i.plant_level}" for i in plants])
                ctx._set_footer(embed)
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

        # Work out some other info we want displayed
        description_list.append(f"Plant level {plant.plant_level}")
        description_list.append(f"Costs {plant.required_experience} exp")
        description_list.append(f"Gives between {plant.experience_gain['minimum']} and {plant.experience_gain['maximum']} exp")

        # Embed the data
        with utils.Embed(use_random_colour=True) as embed:
            embed.title = plant.display_name.capitalize()
            embed.description = '\n'.join(description_list)
            embed.set_image("attachment://plant.png")
            ctx._set_footer(embed)
        display_utils = self.bot.get_cog("PlantDisplayUtils")
        plant_image_bytes = display_utils.image_to_bytes(display_utils.get_plant_image(plant.name, 21, "clay", random.randint(0, 360)))
        await ctx.send(embed=embed, file=discord.File(plant_image_bytes, filename="plant.png"))

    @utils.command()
    @utils.cooldown.cooldown(1, 10, commands.BucketType.user)
    @commands.bot_has_permissions(send_messages=True)
    @utils.checks.is_config_set('command_data', 'suggestion_channel_id')
    async def suggest(self, ctx:utils.Context, *, suggestion:str):
        """
        Send a suggestion for Flower to the bot developer.
        """

        # Make sure they can send in suggestions
        async with self.bot.database() as db:
            rows = await db("SELECT * FROM blacklisted_suggestion_users WHERE user_id=$1", ctx.author.id)
        if rows:
            return await ctx.send("You've been blacklisted from sending in suggestions.")

        # See if they said something valid
        if ctx.message.attachments:
            return await ctx.send("I can't send images as suggestions :<")

        # Send it to the channel
        text = f"`G{ctx.guild.id if ctx.guild else 'DMs'}`\\|\\|`C{ctx.channel.id}`\\|\\|`U{ctx.author.id}`\\|\\|{ctx.author.mention}\\|\\|{suggestion}"
        try:
            await self.bot.http.send_message(self.bot.config['command_data']['suggestion_channel_id'], text)
        except discord.HTTPException:
            return await ctx.send("I couldn't send in your suggestion!")

        # Tell them it's done
        return await ctx.send("Sent in your suggestion!")

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    async def volunteer(self, ctx:utils.Context):
        """
        Get the information for volunteering.
        """

        VOLUNTEER_INFORMATION = (
            "Want to help out with Flower, and watch it grow? Heck yeah! There's a few ways you can help out:\n\n"
            "**Art**\n"
            "Flower takes a lot of art, being a bot entirely about watching things grow. Unfortunately, I'm awful at art. Anything you can help out "
            "with would be amazing, if you had some kind of artistic talent yourself. If you [go here](https://github.com/Voxel-Fox-Ltd/Flower/blob/botutils-rewrite/images/pots/clay/full.png) "
            "you can get an empty pot image you can use as a base. Every plant in Flower has a minimum of 6 distinct growth stages "
            "(which you can [see here](https://github.com/Voxel-Fox-Ltd/Flower/tree/botutils-rewrite/images/plants/blue_daisy/alive) if you need an example).\n"
            "If this is the kind of thing you're interested in, I suggest you join [the support server](https://discord.gg/vfl) to ask for more information, or "
            "[email Kae](mailto://callum@voxelfox.co.uk) - the bot's developer.\n"
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
        embed = utils.Embed(
            use_random_colour=True,
            description=VOLUNTEER_INFORMATION,
        )
        ctx._set_footer(embed)
        try:
            await ctx.author.send(embed=embed)
        except discord.HTTPException:
            return await ctx.send("I wasn't able to send you a DM :<")
        if ctx.guild is not None:
            return await ctx.send("Sent you a DM!")


def setup(bot:utils.Bot):
    x = InformationCommands(bot)
    bot.add_cog(x)
