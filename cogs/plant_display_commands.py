from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands, vbu

from cogs import utils

if TYPE_CHECKING:
    from .plant_display_utils import PlantDisplayUtils


class PlantDisplayCommands(vbu.Cog[utils.types.Bot]):

    @commands.command(
        aliases=['displayplant', 'show', 'display'],
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="plant_name",
                    description="The plant that you want to see.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),

            ]
        )
    )
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def showplant(
            self,
            ctx: vbu.Context,
            user: Optional[discord.User] = None,
            *,
            plant_name: Optional[str] = None):
        """
        Shows you your plant status.
        """

        # Make sure they gave a plant name
        if plant_name is None:
            return await ctx.invoke(self.bot.get_command("plants"), user)  # type: ignore

        # Fix up the user param
        user = user or ctx.author  # type: ignore
        assert user

        # Get data from database
        async with vbu.Database() as db:
            plant_rows = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                user.id, plant_name,
            )
            if not plant_rows:
                return await ctx.send(
                    f"You have no plant named **{plant_name.capitalize()}**",
                    allowed_mentions=discord.AllowedMentions.none(),
                )

        # Filter into variables
        display_utils: PlantDisplayUtils = self.bot.get_cog("PlantDisplayUtils")  # type: ignore
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
        embed = vbu.Embed(use_random_colour=True, description=text).set_image("attachment://plant.png")
        ctx.bot.set_footer_from_config(embed)
        await ctx.send(embed=embed, file=file)

    @commands.command(
        aliases=['displayall'],
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    @utils.checks.has_premium()
    @commands.bot_has_permissions(send_messages=True, embed_links=True, attach_files=True)
    async def showall(self, ctx: vbu.Context, user: Optional[discord.User] = None):
        """
        Show you all of your plants at once.
        """

        # Fix up user param
        user = user or ctx.author  # type: ignore
        assert user

        # Get data from database
        async with vbu.Database() as db:
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 ORDER BY plant_name DESC", user.id)
            if not plant_rows:
                return await ctx.send(f"<@{user.id}> has no available plants.", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))
        await ctx.trigger_typing()

        # Filter into variables
        display_utils: PlantDisplayUtils = self.bot.get_cog("PlantDisplayUtils")  # type: ignore
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
        embed = vbu.Embed(use_random_colour=True, description=text).set_image("attachment://plant.png")
        ctx.bot.set_footer_from_config(embed)
        await ctx.send(embed=embed, file=file)

    showplant.autocomplete(utils.autocomplete.plant_name_autocomplete)


def setup(bot: utils.types.Bot):
    x = PlantDisplayCommands(bot)
    bot.add_cog(x)
