import io
import random

from PIL import Image, ImageOps
import numpy as np
import colorsys
import voxelbotutils as utils


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
        """
        Shift the hue of an image by a given amount.
        """

        image_array = np.array(np.asarray(image).astype('float'))
        return Image.fromarray(cls._shift_hue(image_array, hue).astype('uint8'), 'RGBA')

    @staticmethod
    def crop_image_to_content(image:Image) -> Image:
        """
        Crop out any "wasted" transparent data from an image.
        """

        image_data = np.asarray(image)
        image_data_bw = image_data.max(axis=2)
        non_empty_columns = np.where(image_data_bw.max(axis=0) > 0)[0]
        non_empty_rows = np.where(image_data_bw.max(axis=1) > 0)[0]
        crop_box = (min(non_empty_rows), max(non_empty_rows), min(non_empty_columns), max(non_empty_columns))
        image_data_new = image_data[crop_box[0]:crop_box[1] + 1, crop_box[2]:crop_box[3] + 1, :]
        return Image.fromarray(image_data_new)

    @staticmethod
    def image_to_bytes(image:Image) -> io.BytesIO:
        image_to_send = io.BytesIO()
        image.save(image_to_send, "PNG")
        image_to_send.seek(0)
        return image_to_send

    def get_plant_image(self, plant_type:str, plant_variant:int, plant_nourishment:int, pot_type:str, pot_hue:int) -> Image:
        """
        Get a BytesIO object containing the binary data of a given plant/pot item.
        """

        # See if the plant is dead or not
        plant_is_dead = False
        plant_nourishment = int(plant_nourishment)
        if plant_nourishment < 0:
            plant_is_dead = True
            plant_nourishment = -plant_nourishment

        # Get the plant image we need
        plant_level = 0
        plant_image: Image = None
        plant_overlay_image: Image = None
        if plant_nourishment != 0 and plant_type is not None:
            plant_level = self.bot.plants[plant_type].get_nourishment_display_level(plant_nourishment)
            if plant_is_dead:
                plant_image = Image.open(f"images/plants/{plant_type}/dead/{plant_level}.png").convert("RGBA")
                try:
                    plant_overlay_image = Image.open(f"images/plants/{plant_type}/dead/{plant_level}_overlay.png").convert("RGBA")
                except FileNotFoundError:
                    pass
            else:
                plant_image = Image.open(f"images/plants/{plant_type}/alive/{plant_level}_{plant_variant}.png").convert("RGBA")
                try:
                    plant_overlay_image = Image.open(f"images/plants/{plant_type}/alive/{plant_level}_{plant_variant}_overlay.png").convert("RGBA")
                except FileNotFoundError:
                    pass

        # Paste the bot pack that we want onto the image
        image = Image.open(f"images/pots/{pot_type}/back.png").convert("RGBA")
        image = self.shift_image_hue(image, pot_hue)
        offset = (0, 0)  # The offset for the plant pot being pasted into the image
        if plant_image:
            offset = (int((plant_image.size[0] - image.size[0]) / 2), plant_image.size[1] - image.size[1])
            new_image = Image.new(image.mode, plant_image.size)
            new_image.paste(image, offset, image)
            image = new_image

        # Paste the soil that we want onto the image
        pot_soil = Image.open(f"images/pots/{pot_type}/soil.png").convert("RGBA")
        if plant_type:
            pot_soil = self.shift_image_hue(pot_soil, self.bot.plants[plant_type].soil_hue)
        else:
            pot_soil = self.shift_image_hue(pot_soil, 0)
        image.paste(pot_soil, offset, pot_soil)

        # Paste the plant onto the image
        if plant_nourishment != 0:
            image.paste(plant_image, (0, 0), plant_image)

        # Paste the pot foreground onto the image
        pot_foreground = Image.open(f"images/pots/{pot_type}/front.png").convert("RGBA")
        pot_foreground = self.shift_image_hue(pot_foreground, pot_hue)
        image.paste(pot_foreground, offset, pot_foreground)

        # And see if we have a pot overlay to paste
        if plant_overlay_image:
            image.paste(plant_overlay_image, (0, 0), plant_overlay_image)

        # Read the bytes
        image = self.crop_image_to_content(image.resize((image.size[0] * 5, image.size[1] * 5,), Image.NEAREST))
        return image

    @classmethod
    def compile_plant_images(cls, *plants, add_flipping:bool=True):
        """
        Add together some plant images.
        """

        # Work out our numbers
        max_height = max([i.size[1] for i in plants])
        total_width = sum([i.size[0] for i in plants])

        # Create the new image
        new_image = Image.new("RGBA", (total_width, max_height,))
        width_offset = 0
        for index, image in enumerate(plants):
            if add_flipping:
                if random.randint(0, 1):
                    image = ImageOps.mirror(image)
            new_image.paste(image, (width_offset, max_height - image.size[1],), image)
            width_offset += image.size[0]

        # And Discord it up
        # image = self.crop_image_to_content(new_image.resize((new_image.size[0] * 5, new_image.size[1] * 5,), Image.NEAREST))
        return cls.crop_image_to_content(new_image)

    @staticmethod
    def get_display_data(plant_row, user_id:int=None) -> dict:
        """
        Get the display data of a given plant and return it as a dict.
        """

        plant_type = None
        plant_variant = None
        plant_nourishment = 0
        pot_type = 'clay'
        pot_hue = (user_id or 0) % 360  # the "or 0" is just to avoid errors when the user ID isn't passed

        if plant_row is not None:
            plant_type = plant_row['plant_type']
            plant_nourishment = plant_row['plant_nourishment']
            plant_variant = plant_row['plant_variant']
            pot_hue = plant_row['original_owner_id'] % 360

        return {
            'plant_type': plant_type,
            'plant_variant': plant_variant,
            'plant_nourishment': plant_nourishment,
            'pot_type': pot_type,
            'pot_hue': pot_hue,
        }


def setup(bot:utils.Bot):
    x = PlantDisplayCommands(bot)
    bot.add_cog(x)
