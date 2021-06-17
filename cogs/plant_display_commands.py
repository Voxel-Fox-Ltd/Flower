import typing

import discord
from discord.ext import commands
import voxelbotutils as utils

from cogs import localutils


class PlantDisplayCommands(utils.Cog):

    @utils.command(aliases=['displayplant', 'show', 'display'], argument_descriptions=(
        "The user whose plant you want to display.",
        "The plant which you want to look at.",
    ))
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def showplant(self, ctx: utils.Context, user: typing.Optional[discord.User], *, plant_name: str = None):
        """
        Shows you your plant status.
        """

        # Make sure they gave a plant name
        if plant_name is None:
            return await ctx.invoke(self.bot.get_command("plants"), user)

        # Get data from database
        user = user or ctx.author
        async with self.bot.database() as db:
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", user.id, plant_name)
            if not plant_rows:
                return await ctx.send(f"You have no plant named **{plant_name.capitalize()}**", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

        # Filter into variables
        display_utils = self.bot.get_cog("PlantDisplayUtils")
        if plant_rows:
            display_data = display_utils.get_display_data(plant_rows[0], user_id=user.id)
        else:
            display_data = display_utils.get_display_data(None, user_id=user.id)

        # Generate text
        if display_data['plant_type'] is None:
            if ctx.author.id == user.id:
                text = f"You don't have a plant yet, {ctx.author.mention}! Run `{ctx.prefix}getplant` to get one!"
            else:
                text = f"<@{user.id}> doesn't have a plant yet!"
        else:
            text = f"<@{user.id}>'s {display_data['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**"
            if int(display_data['plant_nourishment']) > 0:
                if ctx.author.id == user.id:
                    text += f"!\nYou can see all of your plants at once with the `{ctx.clean_prefix}showall` command!"
                else:
                    text += f".\nYou can see all of their plants at once with the `{ctx.clean_prefix}showall` command!"
            elif int(display_data['plant_nourishment']) < 0:
                if ctx.author.id == user.id:
                    text += f". It's looking a tad... dead. Run `{ctx.prefix}deleteplant {plant_name}` to plant some new seeds."
                else:
                    text += ". It looks a bit... worse for wear, to say the least."
            elif int(display_data['plant_nourishment']) == 0:
                if ctx.author.id == user.id:
                    text += f". There are some seeds there, but you need to `{ctx.prefix}water {plant_rows[0]['plant_name']}` them to get them to grow."
                else:
                    text += ". There are some seeds there I think, but they need to be watered."

        # Send image
        image_data = display_utils.image_to_bytes(display_utils.get_plant_image(**display_data))
        file = discord.File(image_data, filename="plant.png")
        embed = utils.Embed(use_random_colour=True, description=text).set_image("attachment://plant.png")
        ctx.bot.set_footer_from_config(embed)
        await ctx.send(embed=embed, file=file)

    @utils.command(hidden=True, argument_descriptions=(
        "The user whose plants you want to show.",
    ))
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def showallold(self, ctx: utils.Context, user: typing.Optional[discord.User]):
        """
        Show you all of your plants.
        """

        # Get data from database
        user = user or ctx.author
        async with self.bot.database() as db:
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 ORDER BY plant_name DESC", user.id)
            if not plant_rows:
                return await ctx.send(f"<@{user.id}> has no available plants.", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))
        await ctx.trigger_typing()

        # Filter into variables
        display_utils = self.bot.get_cog("PlantDisplayUtils")
        plant_rows = display_utils.sort_plant_rows(plant_rows)
        images = []
        for plant_row in plant_rows:
            if plant_row:
                display_data = display_utils.get_display_data(plant_row, user_id=user.id)
            else:
                display_data = display_utils.get_display_data(None, user_id=user.id)
            images.append(display_utils.get_plant_image(**display_data))

        # Get our images
        image = display_utils.compile_plant_images(*images)
        image_to_send = display_utils.image_to_bytes(image)
        text = f"Here are all of <@{user.id}>'s plants!"
        file = discord.File(image_to_send, filename="plant.png")
        embed = utils.Embed(use_random_colour=True, description=text).set_image("attachment://plant.png")
        ctx.bot.set_footer_from_config(embed)
        await ctx.send(embed=embed, file=file)

    @utils.command(aliases=['displayall'], argument_descriptions=(
        "The user whose plants you want to display.",
    ))
    @localutils.checks.has_premium()
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def showall(self, ctx: utils.Context, user: typing.Optional[discord.User]):
        """
        Show you all of your plants at once.
        """

        # Get data from database
        user = user or ctx.author
        async with self.bot.database() as db:
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 ORDER BY plant_name DESC", user.id)
            if not plant_rows:
                return await ctx.send(f"<@{user.id}> has no available plants.", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))
        await ctx.trigger_typing()

        # Filter into variables
        display_utils = self.bot.get_cog("PlantDisplayUtils")
        plant_rows = display_utils.sort_plant_rows(plant_rows)
        images = []
        for plant_row in plant_rows:
            if plant_row:
                display_data = display_utils.get_display_data(plant_row, user_id=user.id)
            else:
                display_data = display_utils.get_display_data(None, user_id=user.id)
            images.append(display_utils.get_plant_image(**display_data, crop_image=False))

        # Get our images
        image = display_utils.compile_plant_images_compressed(*images)
        image_to_send = display_utils.image_to_bytes(image)
        text = f"Here are all of <@{user.id}>'s plants!"
        file = discord.File(image_to_send, filename="plant.png")
        embed = utils.Embed(use_random_colour=True, description=text).set_image("attachment://plant.png")
        ctx.bot.set_footer_from_config(embed)
        await ctx.send(embed=embed, file=file)


def setup(bot:utils.Bot):
    x = PlantDisplayCommands(bot)
    bot.add_cog(x)
