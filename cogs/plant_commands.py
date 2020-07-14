import typing
import io
import random
from datetime import datetime as dt, timedelta
from glob import glob
import os
import json
import asyncio

import discord
from discord.ext import commands
from PIL import Image, ImageColor as ImageColour
import numpy as np

from cogs import utils


class PlantCommands(utils.Cog):

    def __init__(self, bot):
        super().__init__(bot)
        self._available_plants = None

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

    def get_plant_bytes(self, plant_type:str, plant_variant:int, plant_nourishment:int, pot_type:str, pot_colour:tuple) -> io.BytesIO:
        """Get a BytesIO object containing the binary data of a given plant/pot item"""

        # See if the plant is dead or not
        plant_is_dead = False
        plant_nourishment = int(plant_nourishment)
        if plant_nourishment < 0:
            plant_is_dead = True
            plant_nourishment = -plant_nourishment

        # Get the plant image we need
        plant_level = 0
        if plant_nourishment != 0:
            plant_level = self.get_available_plants()[plant_type]['nourishment_display_levels'][str(plant_nourishment)]
            if plant_is_dead:
                plant_image = Image.open(f"images/plants/{plant_type}/dead/{plant_level}.png")
            else:
                plant_image = Image.open(f"images/plants/{plant_type}/alive/{plant_level}_{plant_variant}.png")

        # Paste the bot pack that we want onto the image
        image = Image.open(f"images/pots/{pot_type}/back.png")
        colour_mask = Image.new("RGBA", image.size, pot_colour)
        pot_back_mask = Image.open(f"images/pots/{pot_type}/back_mask.png")
        image = Image.composite(image, colour_mask, pot_back_mask)

        # Paste the soil that we want onto the image
        pot_soil = Image.open(f"images/pots/{pot_type}/soil.png")
        if plant_type:
            soil_colour_mask = Image.new("RGBA", image.size, tuple(self.get_available_plants()[plant_type]['soil_colour']))
        else:
            soil_colour_mask = Image.new("RGBA", image.size, (43, 29, 14,))
        pot_soil_mask = Image.open(f"images/pots/{pot_type}/soil_mask.png")
        pot_soil_composite = Image.composite(pot_soil, soil_colour_mask, pot_soil_mask)
        image.paste(pot_soil_composite, (0, 0), pot_soil_composite)

        # Paste the plant onto the image
        if plant_nourishment != 0:
            image.paste(plant_image, (0, 0), plant_image)

        # Paste the pot foreground onto the image
        pot_foreground = Image.open(f"images/pots/{pot_type}/front.png")
        pot_foreground_mask = Image.open(f"images/pots/{pot_type}/front_mask.png")
        pot_foreground_composite = Image.composite(pot_foreground, colour_mask, pot_foreground_mask)
        image.paste(pot_foreground_composite, (0, 0), pot_foreground_composite)

        # Read the bytes
        image = self.crop_image_to_content(image)
        image_to_send = io.BytesIO()
        image.save(image_to_send, "PNG")
        image_to_send.seek(0)
        return image_to_send

    def get_available_plants(self) -> typing.List[dict]:
        """Returns a list of the available plant names and the exp required for them"""

        # See if there's already cached data
        if self._available_plants:
            return self._available_plants

        # Check direcotries
        plant_directories = glob("images/plants/*/")
        plant_names = [i.strip(os.sep).split(os.sep)[-1] for i in plant_directories]
        available_plants = []

        # Check the plant JSON file
        for name in plant_names:
            with open(f"images/plants/{name}/pack.json") as a:
                data = json.load(a)

            # Add the plant's name to it
            data.update({"name": name})

            # Add some more nourishment data - it displays by default as {nourishment: level}
            # This just adds in the missing levels, 0, and (max + 1)
            nourishment = data['nourishment_display_levels']
            nourishment.update({"0": nourishment.get("1")})
            nourishment_ints = [int(i) for i in nourishment.keys()]
            for i in range(1, max(nourishment_ints) + 2):
                if nourishment.get(str(i)) is None:
                    nourishment.update({str(i): nourishment.get(str(i - 1))})
            data.update({"nourishment_display_levels": nourishment, "max_nourishment_level": max(nourishment_ints) + 1})

            # Shove that into the plant data
            available_plants.append(data)

        # Dictionary it up
        self._available_plants = {i['name']: i for i in available_plants}
        return self._available_plants

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
            pot_colour = (120, 80, 39,)
        else:
            pot_type = user_rows[0]['pot_type'] or 'clay'
            pot_colour = ImageColour.getrgb(f"#{user_rows[0]['pot_colour']:0>6X}") if user_rows[0]['pot_colour'] else (120, 80, 39,)

        # Generate text
        if plant_type is None:
            if ctx.author.id == user.id:
                text = f"You don't have a plant yet, {ctx.author.mention}! Run `{ctx.prefix}getplant` to get one!"
            else:
                text = f"<@{user.id}> doesn't have a plant yet!"
        else:
            if int(plant_nourishment) > 0:
                if ctx.author.id == user.id:
                    text = f"<@{user.id}>'s {plant_rows[0]['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**! Change your pot colour with `{ctx.prefix}usersettings`~"
                else:
                    text = f"<@{user.id}>'s {plant_rows[0]['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**!"
            elif int(plant_nourishment) < 0:
                if ctx.author.id == user.id:
                    text = f"<@{user.id}>'s {plant_rows[0]['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**. It's looking a tad... dead. Run `{ctx.prefix}deleteplant` to plant some new seeds."
                else:
                    text = f"<@{user.id}>'s {plant_rows[0]['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**. It looks a bit... worse for wear, to say the least."
            elif int(plant_nourishment) == 0:
                if ctx.author.id == user.id:
                    text = f"<@{user.id}>'s {plant_rows[0]['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**. There are some seeds there, but you need to `{ctx.prefix}water {plant_rows[0]['plant_name']}` them to get them to grow."
                else:
                    text = f"<@{user.id}>'s {plant_rows[0]['plant_type'].replace('_', ' ')} - **{plant_rows[0]['plant_name']}**. There are some seeds there I think, but they need to be watered."

        # Send image
        image_data = self.get_plant_bytes(plant_type, plant_variant, plant_nourishment, pot_type, pot_colour)
        file = discord.File(image_data, filename="plant.png")
        await ctx.send(text, file=file, allowed_mentions=discord.AllowedMentions(users=[ctx.author], roles=False, everyone=False))

    @commands.command(cls=utils.Command, aliases=['getplant'])
    async def newplant(self, ctx:utils.Context):
        """Shows you the available plants"""

        # Get the experience
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", ctx.author.id)
        if user_rows:
            user_experience = user_rows[0]['user_experience']
        else:
            user_experience = 0

        # See what plants are available
        text_rows = [f"What seeds would you like to plant, {ctx.author.mention}?"]
        for plant_name, plant in self.get_available_plants().items():
            if plant['required_experience'] <= user_experience:
                text_rows.append(f"**{plant_name.capitalize().replace('_', ' ')}** - {plant['required_experience']} exp")
            else:
                text_rows.append(f"~~**{plant_name.capitalize().replace('_', ' ')}** - {plant['required_experience']} exp~~")
        await ctx.send('\n'.join(text_rows))

        # Wait for them to respond
        try:
            plant_type_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel == ctx.channel and m.content, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out asking for plant type {ctx.author.mention}.")

        # See what they want
        try:
            plant_type = self.get_available_plants()[plant_type_message.content.lower().replace(' ', '_')]
        except KeyError:
            return await ctx.send(f"That isn't an available plant name, {ctx.author.mention}.")
        if plant_type['required_experience'] > user_experience:
            return await ctx.send(f"You don't have the required experience to get that plant, {ctx.author.mention}.")

        # Get a name for the plant
        await ctx.send("What name do you want to give your plant?")
        try:
            plant_name_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel == ctx.channel and m.content, timeout=120)
        except asyncio.TimeoutError:
            return await ctx.send(f"Timed out asking for plant name {ctx.author.mention}.")

        # Save that to database
        async with self.bot.database() as db:
            plant_name_exists = await db(
                "SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)",
                ctx.author.id, plant_name_message.content
            )
            if plant_name_exists:
                return await ctx.send(f"You've already used the name `{plant_name_message.content}` for one of your other plants - please run this command again to give a new one!", allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))
            await db(
                """INSERT INTO plant_levels (user_id, plant_name, plant_type, plant_nourishment, last_water_time)
                VALUES ($1, $2, $3, 0, $4) ON CONFLICT (user_id, plant_name) DO UPDATE
                SET plant_nourishment=0, last_water_time=$4""",
                ctx.author.id, plant_name_message.content, plant_type['name'], dt.utcnow(),
            )
            await db(
                "UPDATE user_settings SET user_experience=user_settings.user_experience-$2 WHERE user_id=$1",
                ctx.author.id, plant_type['required_experience'],
            )
        self.bot.get_command("water").reset_cooldown(ctx)
        await ctx.send(f"Planted your **{plant_type['name'].replace('_', ' ')}** seeds!")

    @commands.command(cls=utils.Command, aliases=['water'], cooldown_after_parsing=True)
    @utils.cooldown.cooldown(1, 60 * 15, commands.BucketType.user)
    async def waterplant(self, ctx:utils.Context, *, plant_name:str):
        """Increase the growth level of your plant"""

        # Decide on our plant type - will be ignored if there's already a plant
        db = await self.bot.database.get_connection()

        # See if they have a plant available
        plant_level_row = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, plant_name)
        if not plant_level_row:
            await db.disconnect()
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"You don't have a plant with the name **{plant_name.capitalize()}**! Run `{ctx.prefix}getplant` to plant some new seeds, or `{ctx.prefix}plants` to see the list of plants you have already!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        plant_data = self.get_available_plants()[plant_level_row[0]['plant_type']]

        # See if the plant should be dead
        if plant_level_row[0]['last_water_time'] + timedelta(days=2) < dt.utcnow() or plant_level_row[0]['plant_nourishment'] < 0:
            plant_level_row = await db(
                """UPDATE plant_levels SET
                plant_nourishment=LEAST(-plant_levels.plant_nourishment, plant_levels.plant_nourishment), last_water_time=$3
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)
                RETURNING plant_nourishment""",
                ctx.author.id, plant_name, dt.utcnow(),
            )

        # Increase the nourishment otherwise
        else:
            plant_level_row = await db(
                """UPDATE plant_levels
                SET plant_nourishment=LEAST(plant_levels.plant_nourishment+1, $4), last_water_time=$3
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)
                RETURNING plant_name, plant_nourishment""",
                ctx.author.id, plant_name, dt.utcnow(), plant_data['max_nourishment_level'],
            )

        # Add to the user exp
        plant_nourishment = plant_level_row[0]['plant_nourishment']
        if plant_nourishment > 0:
            gained_experience = random.randint(plant_data['experience_gain']['minimum'], plant_data['experience_gain']['maximum'])
            await db(
                """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                DO UPDATE SET user_experience=user_settings.user_experience+$2""",
                ctx.author.id, gained_experience,
            )
        else:
            gained_experience = 0
        await db.disconnect()

        # Send an output
        if plant_nourishment < 0:
            await ctx.send("You sadly pour water into the dry soil of your silently wilting plant :c")
        elif plant_data['nourishment_display_levels'][str(plant_nourishment)] > plant_data['nourishment_display_levels'][str(plant_nourishment - 1)]:
            # await ctx.send(f"You gently pour water into your **{plant_data['name'].replace('_', ' ')}**'s soil, gaining you {gained_experience} experience, watching your plant grow!~")
            await ctx.send(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_experience} experience, watching your plant grow!~")
        else:
            # await ctx.send(f"You gently pour water into your **{plant_data['name'].replace('_', ' ')}**'s soil, gaining you {gained_experience} experience~")
            await ctx.send(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_experience} experience~")

    @commands.command(cls=utils.Command, aliases=['delete'], hidden=True)
    async def deleteplant(self, ctx:utils.Context, *, plant_name:str):
        """Deletes your plant from the database"""

        async with self.bot.database() as db:
            await db("DELETE FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, plant_name)
        await ctx.send("Done.")

    @commands.command(cls=utils.Command, aliases=['rename'])
    async def renameplant(self, ctx:utils.Context, before:str, *, after:str):
        """Deletes your plant from the database"""

        async with self.bot.database() as db:
            plant_has_before_name = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before)
            if not plant_has_before_name:
                return await ctx.send(f"You have no plants with the name `{before}`.", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
            await db("UPDATE plant_levels SET plant_name=$3 WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before, after)
        await ctx.send("Done!~")

    @commands.command(cls=utils.Command, aliases=['exp'])
    async def experience(self, ctx:utils.Context, user:utils.converters.UserID=None):
        """Shows you how much experience a user has"""

        user = discord.Object(user) if user else ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM user_settings WHERE user_id=$1", user.id)
        if user_rows:
            exp_value = user_rows[0]['user_experience']
        else:
            exp_value = 0
        return await ctx.send(f"<@{user.id}> has **{exp_value:,}** experience.", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))

    @commands.command(cls=utils.Command, aliases=['list'])
    async def plants(self, ctx:utils.Context, user:utils.converters.UserID=None):
        """Shows you all the plants that a given user has"""

        user = discord.Object(user) if user else ctx.author
        async with self.bot.database() as db:
            user_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", user.id)
        plant_names = sorted([(i['plant_name'], i['plant_type'], i['plant_nourishment']) for i in user_rows])
        if not plant_names:
            return await ctx.send(f"<@{user.id}> has no plants :c", allowed_mentions=discord.AllowedMentions(users=[ctx.author]))
        plant_output_string = []
        for i in plant_names:
            if i[2] >= 0:
                plant_output_string.append(f"**{i[0]}** ({i[1].replace('_', ' ')}, nourishment level {i[2]}/{self.get_available_plants()[i[1]]['max_nourishment_level']})")
            else:
                plant_output_string.append(f"**{i[0]}** ({i[1].replace('_', ' ')}, dead)")
        return await ctx.send(
            f"<@{user.id}> has the following:\n" + '\n'.join(plant_output_string),
            allowed_mentions=discord.AllowedMentions(users=[ctx.author], everyone=False, roles=False)
        )


def setup(bot:utils.Bot):
    x = PlantCommands(bot)
    bot.add_cog(x)
