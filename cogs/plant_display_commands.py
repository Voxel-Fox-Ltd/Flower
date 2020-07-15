import typing
import io

import discord
from discord.ext import commands
from PIL import Image
import numpy as np
import colorsys

from cogs import utils


class PlantDisplayCommands(utils.Cog):

    rgb_to_hsv = np.vectorize(colorsys.rgb_to_hsv)
    hsv_to_rgb = np.vectorize(colorsys.hsv_to_rgb)

    def __init__(self, bot):
        super().__init__(bot)
        self._available_plants = None

    @classmethod
    def _shift_hue(cls, image_array, hue_value:float):
        r, g, b, a = np.rollaxis(image_array, axis=-1)
        h, s, v = cls.rgb_to_hsv(r, g, b)
        r, g, b = cls.hsv_to_rgb(hue_value / 360, s, v)
        image_array = np.dstack((r, g, b, a))
        return image_array

    @classmethod
    def shift_image_hue(cls, image:Image, hue:int) -> Image:
        """Shift the hue of an image by a given amount"""

        image_array = np.array(np.asarray(image).astype('float'))
        return Image.fromarray(cls._shift_hue(image_array, hue).astype('uint8'), 'RGBA')

    @staticmethod
    def crop_image_to_content(image:Image) -> Image:
        """Crop out any "wasted" transparent data from an image"""

        image_data = np.asarray(image)
        image_data_bw = image_data.max(axis=2)
        non_empty_columns = np.where(image_data_bw.max(axis=0) > 0)[0]
        non_empty_rows = np.where(image_data_bw.max(axis=1) > 0)[0]
        cropBox = (min(non_empty_rows), max(non_empty_rows), min(non_empty_columns), max(non_empty_columns))
        image_data_new = image_data[cropBox[0]:cropBox[1] + 1, cropBox[2]:cropBox[3] + 1, :]
        return Image.fromarray(image_data_new)

    def get_plant_bytes(self, plant_type:str, plant_variant:int, plant_nourishment:int, pot_type:str, pot_hue:int) -> io.BytesIO:
        """Get a BytesIO object containing the binary data of a given plant/pot item"""

        # See if the plant is dead or not
        plant_is_dead = False
        plant_nourishment = int(plant_nourishment)
        if plant_nourishment < 0:
            plant_is_dead = True
            plant_nourishment = -plant_nourishment

        # Get the plant image we need
        plant_level = 0
        plant_image = None
        if plant_nourishment != 0:
            plant_level = self.bot.plants[plant_type].get_nourishment_display_level(plant_nourishment)
            if plant_is_dead:
                plant_image = Image.open(f"images/plants/{plant_type}/dead/{plant_level}.png")
            else:
                plant_image = Image.open(f"images/plants/{plant_type}/alive/{plant_level}_{plant_variant}.png")

        # Paste the bot pack that we want onto the image
        image = Image.open(f"images/pots/{pot_type}/back.png")
        image = self.shift_image_hue(image, pot_hue)
        if plant_image:
            offset = (0, plant_image.size[1] - image.size[1])
            new_image = Image.new(image.mode, plant_image.size)
            new_image.paste(image, offset, image)
            image = new_image
        else:
            offset = (0, 0)

        # Paste the soil that we want onto the image
        pot_soil = Image.open(f"images/pots/{pot_type}/soil.png")
        if plant_type:
            pot_soil = self.shift_image_hue(pot_soil, self.bot.plants[plant_type].soil_hue)
        else:
            pot_soil = self.shift_image_hue(pot_soil, 0)
        image.paste(pot_soil, offset, pot_soil)

        # Paste the plant onto the image
        if plant_nourishment != 0:
            image.paste(plant_image, (0, 0), plant_image)

        # Paste the pot foreground onto the image
        pot_foreground = Image.open(f"images/pots/{pot_type}/front.png")
        pot_foreground = self.shift_image_hue(pot_foreground, pot_hue)
        image.paste(pot_foreground, offset, pot_foreground)

        # Read the bytes
        image = self.crop_image_to_content(image.resize((image.size[0] * 5, image.size[1] * 5,), Image.NEAREST))
        image_to_send = io.BytesIO()
        image.save(image_to_send, "PNG")
        image_to_send.seek(0)
        return image_to_send

    @commands.command(cls=utils.Command, aliases=['showplant', 'show', 'display'])
    async def displayplant(self, ctx:utils.Context, user:typing.Optional[utils.converters.UserID], *, plant_name:str):
        """Shows you your plant status"""

        # Get data from database
        user = discord.Object(user) if user else ctx.author
        async with self.bot.database() as db:
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", user.id, plant_name)
            if not plant_rows:
                return await ctx.send(f"You have no plant named **{plant_name.capitalize()}**", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", user.id)

        # Filter into variables
        plant_type = None
        plant_variant = None
        if not plant_rows:
            plant_nourishment = 0
        else:
            plant_type = plant_rows[0]['plant_type']
            plant_nourishment = plant_rows[0]['plant_nourishment']
            plant_variant = plant_rows[0]['plant_variant']
        if not user_rows:
            pot_type = 'clay'
            pot_hue = 180
        else:
            pot_type = user_rows[0]['pot_type'] or 'clay'
            pot_hue = user_rows[0]['pot_hue'] or 180

        # Generate text
        if plant_type is None:
            if ctx.author.id == user.id:
                text = f"You don't have a plant yet, {ctx.author.mention}! Run `{ctx.prefix}getplant` to get one!"
            else:
                text = f"<@{user.id}> doesn't have a plant yet!"
        else:
            text = f"<@{user.id}>'s {plant_rows[0]['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**"
            if int(plant_nourishment) > 0:
                if ctx.author.id == user.id:
                    text += f"! Change your pot colour with `{ctx.prefix}usersettings`~"
                else:
                    text += "!"
            elif int(plant_nourishment) < 0:
                if ctx.author.id == user.id:
                    text += f". It's looking a tad... dead. Run `{ctx.prefix}deleteplant` to plant some new seeds."
                else:
                    text += ". It looks a bit... worse for wear, to say the least."
            elif int(plant_nourishment) == 0:
                if ctx.author.id == user.id:
                    text += f". There are some seeds there, but you need to `{ctx.prefix}water {plant_rows[0]['plant_name']}` them to get them to grow."
                else:
                    text += ". There are some seeds there I think, but they need to be watered."

        # Send image
        image_data = self.get_plant_bytes(plant_type, plant_variant, plant_nourishment, pot_type, pot_hue)
        file = discord.File(image_data, filename="plant.png")
        await ctx.send(text, file=file, allowed_mentions=discord.AllowedMentions(users=[ctx.author], roles=False, everyone=False))


def setup(bot:utils.Bot):
    x = PlantDisplayCommands(bot)
    bot.add_cog(x)
