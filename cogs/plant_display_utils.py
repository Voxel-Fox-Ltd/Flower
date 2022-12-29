from __future__ import annotations

import io
import random
from typing import Optional

from PIL import Image, ImageOps
import numpy as np
import colorsys
from discord.ext import vbu

from cogs import utils


class PlantDisplayUtils(vbu.Cog[utils.types.Bot]):

    PLANT_SCALE_SIZE = 5

    rgb_to_hsv = np.vectorize(colorsys.rgb_to_hsv)
    hsv_to_rgb = np.vectorize(colorsys.hsv_to_rgb)

    def __init__(self, bot):
        super().__init__(bot)
        self._available_plants = None

    @staticmethod
    def sort_plant_rows(rows: list[utils.types.PlantLevelsRow]) -> list[utils.types.PlantLevelsRow]:
        return sorted(
            rows,
            key=lambda i: (
                i['plant_name'],
                i['plant_type'],
                i['plant_nourishment'],
                i['last_water_time'],
            ),
        )

    @classmethod
    def _shift_hue(cls, image_array, hue_value: float):
        r, g, b, a = np.rollaxis(image_array, axis=-1)
        h, s, v = cls.rgb_to_hsv(r, g, b)
        r, g, b = cls.hsv_to_rgb(hue_value / 360, s, v)
        image_array = np.dstack((r, g, b, a))
        return image_array

    @classmethod
    def shift_image_hue(cls, image: Image.Image, hue: int) -> Image.Image:
        """
        Shift the hue of an image by a given amount.
        """

        image_array = np.array(np.asarray(image).astype('float'))
        return Image.fromarray(
            cls._shift_hue(image_array, hue).astype('uint8'),
            'RGBA',
        )

    @staticmethod
    def crop_image_to_content(image: Image.Image) -> Image.Image:
        """
        Crop out any "wasted" transparent data from an image.
        """

        image_data = np.asarray(image)
        image_data_bw = image_data.max(axis=2)
        non_empty_columns = np.where(image_data_bw.max(axis=0) > 0)[0]
        non_empty_rows = np.where(image_data_bw.max(axis=1) > 0)[0]
        crop_box = (
            min(non_empty_rows),
            max(non_empty_rows),
            min(non_empty_columns),
            max(non_empty_columns),
        )
        image_data_new = image_data[
            crop_box[0]:crop_box[1] + 1,
            crop_box[2]:crop_box[3] + 1,
            :
        ]
        return Image.fromarray(image_data_new, "RGBA")

    @staticmethod
    def image_to_bytes(image: Image.Image) -> io.BytesIO:
        image_to_send = io.BytesIO()
        image.save(image_to_send, "PNG")
        image_to_send.seek(0)
        return image_to_send

    @staticmethod
    def gif_to_bytes(
            *images: Image.Image,
            duration: int = 150) -> io.BytesIO:
        """
        Change a list of images into a gif.
        """

        image_to_send = io.BytesIO()
        max_size = (
            max([i.size[0] for i in images]),
            max([i.size[1] for i in images]),
        )
        new_images = []
        for i in images:
            base = Image.new("RGBA", max_size, (0, 0, 0, 0))
            base.paste(
                i,
                (
                    (max_size[0] - i.size[0]) // 2,
                    max_size[1] - i.size[1]
                ),
                i,
            )
            new_images.append(base)
        utils.save_transparent_gif(new_images, duration, image_to_send)
        image_to_send.seek(0)
        return image_to_send

    def get_plant_image(
            self,
            plant_type: str,
            plant_nourishment: int,
            pot_type: str,
            pot_hue: int,
            crop_image: bool = True) -> Image.Image:
        """
        Get a BytesIO object containing the binary data of a given plant/pot item.
        """

        # See if the plant is dead or not
        plant_is_dead = False
        plant_nourishment = int(plant_nourishment)
        if plant_nourishment < 0:
            plant_is_dead = True
            plant_nourishment = -plant_nourishment
        file_folder = {False: "alive", True: "dead"}[plant_is_dead]

        # Set up the variables we need for later
        plant_image: Optional[Image.Image] = None
        plant_overlay_image: Optional[Image.Image] = None
        plant_underlay_image: Optional[Image.Image] = None

        # Work out the
        if plant_nourishment != 0 and plant_type is not None:
            plant_level = (
                self.bot.plants[plant_type]
                .get_nourishment_display_level(plant_nourishment)
            )
            plant_image = Image.open(
                (
                    f"images/plants/{plant_type}/{file_folder}"
                    f"/{plant_level}.png"
                )
            ).convert("RGBA")
            try:
                plant_overlay_image = Image.open(
                    (
                        f"images/plants/{plant_type}/{file_folder}"
                        f"/{plant_level}_overlay.png"
                    )
                ).convert("RGBA")
            except FileNotFoundError:
                pass
            try:
                plant_underlay_image = Image.open(
                    (
                        f"images/plants/{plant_type}/{file_folder}"
                        f"/{plant_level}_underlay.png"
                    )
                ).convert("RGBA")
            except FileNotFoundError:
                pass

        """
        Plants are drawn in the following layer order:
            Plant underlay
            Pot back
            Pot soil
            Plant image
            Pot front
            Plant overlay
        """

        # Start with the underlay image, if it exists
        image = None
        if plant_underlay_image:
            image = plant_underlay_image

        # Paste the bot pack that we want onto the image
        offset = (0, 0)  # The offset for the plant pot being pasted into the image
        pot_back = (
            Image.open(f"images/pots/{pot_type}/back.png")
            .convert("RGBA")
        )
        pot_back = self.shift_image_hue(pot_back, pot_hue)
        if plant_image:
            # Work out the offset for the pot based on the image size
            # This works with or without an underlay
            offset = (
                int((plant_image.size[0] - pot_back.size[0]) / 2),
                plant_image.size[1] - pot_back.size[1],
            )
            if image is None:
                image = Image.new(pot_back.mode, plant_image.size)
            image.paste(pot_back, offset, pot_back)
        else:
            # There was no plant image and there was no underlay
            image = pot_back

        # Paste the soil that we want onto the image
        pot_soil = (
            Image.open(f"images/pots/{pot_type}/soil.png")
            .convert("RGBA")
        )
        if plant_type:
            pot_soil = self.shift_image_hue(
                pot_soil,
                self.bot.plants[plant_type].soil_hue,
            )
        else:
            pot_soil = self.shift_image_hue(pot_soil, 0)
        image.paste(pot_soil, offset, pot_soil)

        # Paste the plant onto the image
        if plant_nourishment != 0 and plant_image:
            image.paste(plant_image, (0, 0), plant_image)

        # Paste the pot foreground onto the image
        pot_foreground = (
            Image.open(f"images/pots/{pot_type}/front.png")
            .convert("RGBA")
        )
        pot_foreground = self.shift_image_hue(pot_foreground, pot_hue)
        image.paste(pot_foreground, offset, pot_foreground)

        # And see if we have a pot overlay to paste
        if plant_overlay_image:
            image.paste(plant_overlay_image, (0, 0), plant_overlay_image)

        # Read the bytes
        image = image.resize(
            (
                image.size[0] * self.PLANT_SCALE_SIZE,
                image.size[1] * self.PLANT_SCALE_SIZE,
            ),
            Image.NEAREST,
        )
        if crop_image:
            return self.crop_image_to_content(image)
        return image

    @classmethod
    def compile_plant_images(
            cls,
            *plants,
            add_flipping: bool = True):
        """
        Add together some plant images.
        """

        # Work out our numbers
        max_height = max([i.size[1] for i in plants])
        total_width = sum([i.size[0] for i in plants])

        # Work out which of our images to flip
        new_plants = []
        for _, image in enumerate(plants):
            if add_flipping:
                if random.randint(0, 1):
                    image = ImageOps.mirror(image)
            new_plants.append(image)

        # Create the new image
        new_image = Image.new("RGBA", (total_width, max_height,))
        width_offset = 0
        for _, image in enumerate(new_plants):
            new_image.paste(
                image,
                (width_offset, max_height - image.size[1],),
                image,
            )
            width_offset += image.size[0]

        # And Discord it up
        return cls.crop_image_to_content(new_image)

    @staticmethod
    def get_plant_hang(plant, pot_width):
        return (plant.size[0] - pot_width) // 2

    @classmethod
    def get_offset(
            cls,
            plants,
            index: int,
            pot_width: int,
            spacer_pixels: int = 4) -> int:
        """
        Get the offset for a plant to be added to a compiled list of multiple
        plants given its position.
        """

        if index == 0:
            return 0
        a1 = cls.get_plant_hang(plants[0], pot_width)
        return (
            a1
            + (
                index
                * (
                    pot_width
                    + (spacer_pixels * cls.PLANT_SCALE_SIZE)
                )
            )
            - cls.get_plant_hang(plants[index], pot_width)
        )

    @classmethod
    def compile_plant_images_compressed(
            cls,
            *plants,
            add_flipping: bool = True) -> Image.Image:
        """
        Add together some plant images.
        """

        # Work out our numbers
        spacer_pixels = 1
        max_height = max([
            i.size[1]
            for i in plants
        ])
        total_width = sum([
            i.size[0] + (spacer_pixels * cls.PLANT_SCALE_SIZE)
            for i in plants
        ])
        pot_image = Image.open("images/pots/clay/front.png").convert("RGBA")
        pot_width = pot_image.size[0] * cls.PLANT_SCALE_SIZE

        # Work out which of our images to flip
        new_plants = []
        for index, image in enumerate(plants):
            if add_flipping:
                if random.randint(0, 1):
                    image = ImageOps.mirror(image)
            new_plants.append(image)

        # Create the new image
        new_image = Image.new("RGBA", (total_width, max_height,))
        for index, image in enumerate(new_plants[::-1]):
            offset_index = len(new_plants) - index - 1
            new_image.paste(
                image,
                (
                    cls.get_offset(
                        plants,
                        offset_index,
                        pot_width,
                        spacer_pixels,
                    ),
                    max_height - image.size[1],
                ),
                image,
            )

        # And Discord it up
        return cls.crop_image_to_content(new_image)

    @staticmethod
    def get_display_data(
            plant_row: Optional[utils.types.PlantLevelsRow],
            user_id: Optional[int] = None) -> utils.types.UserPlantDisplayData:
        """
        Get the display data of a given plant and return it as a dict.

        Parameters
        -----------
        plant_row: dict
            The row from the database continaing the data for the plant.
        user_id: Optional[int]
            An optional user ID for the display data, which gives the default
            colour for the plant pot.

        Returns
        --------
        dict
            A formatted dictionary of all the things that are necessary to
            display a plant.
        """

        plant_type = None
        plant_nourishment = 0
        pot_hue = (user_id or 0) % 360  # A default plant pot colour based on the user ID

        if plant_row is not None:
            plant_type = plant_row['plant_type']
            plant_nourishment = plant_row['plant_nourishment']
            if plant_row['plant_pot_hue']:
                pot_hue = plant_row['plant_pot_hue']
            elif plant_row['original_owner_id']:
                pot_hue = plant_row['original_owner_id'] % 360

        return {
            'plant_type': plant_type,
            'plant_nourishment': plant_nourishment,
            'pot_type': 'clay',
            'pot_hue': pot_hue,
        }


def setup(bot: utils.types.Bot):
    x = PlantDisplayUtils(bot)
    bot.add_cog(x)
