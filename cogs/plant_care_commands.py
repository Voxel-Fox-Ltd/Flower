from datetime import datetime as dt, timedelta

import discord
from discord.ext import commands, tasks
import voxelbotutils as utils


class PlantCareCommands(utils.Cog):

    TOPGG_GET_VOTES_ENDPOINT = "https://top.gg/api/bots/{bot_client_id}/check"

    def __init__(self, bot):
        super().__init__(bot)
        self.plant_death_timeout_loop.start()

    def cog_unload(self):
        self.plant_death_timeout_loop.cancel()

    async def get_user_voted(self, user_id:int) -> bool:
        """
        Returns whether or not the user with the given ID has voted for the bot on Top.gg.

        Args:
            user_id (int): The ID of the user we want to check

        Returns:
            bool: Whether or not the user voted for the bot
        """

        topgg_token = self.bot.config.get('bot_listing_api_keys', {}).get('topgg_token')
        if not topgg_token:
            return False
        params = {"userId": user_id}
        headers = {"Authorization": topgg_token}
        url = self.TOPGG_GET_VOTES_ENDPOINT.format(bot_client_id=self.bot.config['oauth']['client_id'])
        async with self.bot.session.get(url, params=params, headers=headers) as r:
            try:
                data = await r.json()
            except Exception:
                return False
            if r.status != 200:
                return False
        return bool(data['voted'])

    @tasks.loop(minutes=1)
    async def plant_death_timeout_loop(self):
        """
        Loop to see if we should kill off any plants that may have been timed out
        """

        async with self.bot.database() as db:
            await db(
                """UPDATE plant_levels SET plant_nourishment=-plant_levels.plant_nourishment WHERE
                plant_nourishment > 0 AND last_water_time + $2 < $1""",
                dt.utcnow(), timedelta(**self.bot.config.get('plants', {}).get('death_timeout', {'days': 3})),
            )

    @plant_death_timeout_loop.before_loop
    async def before_plant_death_timeout_loop(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def validate_name(name:str):
        """
        Validates the name of a plant
        Input is the name, output is their validated plant name.
        """

        return name.strip('"“”\'').replace('\n', ' ').strip()

    @staticmethod
    def get_water_plant_dict(text:str, success:bool=False, gained_experience:int=0, new_nourishment_level:int=0, new_user_experience:int=0, voted_on_topgg:bool=False, multipliers:list=None):
        return {
            "text": text,
            "success": success,
            "gained_experience": gained_experience,
            "new_nourishment_level": new_nourishment_level,
            "new_user_experience": new_user_experience,
            "voted_on_topgg": voted_on_topgg,
            "multipliers": multipliers or list(),
        }

    async def water_plant_backend(self, user_id:int, plant_name:str):
        """
        Run the backend for the plant watering.

        Returns a sexy lil dictionary in format:
            {
                "text": str,
                "success": bool,
                "new_nourishment_level": int,
                "voted_on_topgg": bool,
                "new_user_experience": int,
                "multipliers": [
                    {
                        "multiplier": float,
                        "text": str
                    },
                    ...
                ]
            }
        """

        # Decide on our plant type - will be ignored if there's already a plant
        db = await self.bot.database.get_connection()

        # See if they have a plant available
        plant_level_row = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", user_id, plant_name)
        if not plant_level_row:
            await db.disconnect()
            return self.get_water_plant_dict(f"You don't have a plant with the name **{plant_name}**! Run the `shop` command to plant some new seeds, or `plants` to see the list of plants you have already!")
        plant_data = self.bot.plants[plant_level_row[0]['plant_type']]

        # See if they're allowed to water things
        if plant_level_row[0]['last_water_time'] + timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15})) > dt.utcnow() and user_id not in self.bot.owner_ids:
            await db.disconnect()
            timeout = utils.TimeValue(((plant_level_row[0]['last_water_time'] + timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15}))) - dt.utcnow()).total_seconds())
            return self.get_water_plant_dict(f"You need to wait another {timeout.clean_spaced} to be able water your {plant_level_row[0]['plant_type'].replace('_', ' ')}.")
        last_water_time = plant_level_row[0]['last_water_time']

        # See if the plant should be dead
        if plant_level_row[0]['plant_nourishment'] < 0:
            plant_level_row = await db(
                """UPDATE plant_levels SET
                plant_nourishment=LEAST(-plant_levels.plant_nourishment, plant_levels.plant_nourishment), last_water_time=$3
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *""",
                user_id, plant_name, dt.utcnow(),
            )

        # Increase the nourishment otherwise
        else:
            plant_level_row = await db(
                """UPDATE plant_levels
                SET plant_nourishment=LEAST(plant_levels.plant_nourishment+1, $4), last_water_time=$3
                WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *""",
                user_id, plant_name, dt.utcnow(), plant_data.max_nourishment_level,
            )

        # Add to the user exp if the plant is alive
        user_plant_data = plant_level_row[0]
        gained_experience = 0
        original_gained_experience = 0
        multipliers = []  # List[dict]
        additional_text = []  # List[str]
        voted_on_topgg = False

        # And now let's water the damn thing
        if user_plant_data['plant_nourishment'] > 0:

            # Get the experience that they should have gained
            gained_experience = plant_data.get_experience()
            original_gained_experience = gained_experience

            # See if we want to give them a 30 second water-time bonus
            if dt.utcnow() - last_water_time - timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15})) <= timedelta(seconds=30):
                multipliers.append({"multiplier": 1.5, "text": "You watered within 30 seconds of your plant's cooldown resetting."})

            # See if we want to give the new owner bonus
            if plant_level_row[0]['user_id'] != plant_level_row[0]['original_owner_id']:
                multipliers.append({"multiplier": 1.05, "text": "You watered a plant that you got from a trade."})

            # See if we want to give them the voter bonus
            if self.bot.config.get('bot_listing_api_keys', {}).get('topgg_token') and await self.get_user_voted(user_id):
                multipliers.append({"multiplier": 1.1, "text": f"You [voted for the bot](https://top.gg/bot/{self.bot.config['oauth']['client_id']}/vote) on Top.gg."})
                voted_on_topgg = True

            # See if we want to give them the plant longevity bonus
            if user_plant_data['plant_adoption_time'] < dt.utcnow() - timedelta(days=7):
                multipliers.append({"multiplier": 1.2, "text": "Your plant has been alive for longer than a week."})

            # Add the actual multiplier values
            for obj in multipliers:
                gained_experience *= obj['multiplier']

            # Update db
            gained_experience = int(gained_experience)
            user_experience_row = await db(
                """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2) ON CONFLICT (user_id)
                DO UPDATE SET user_experience=user_settings.user_experience+$2 RETURNING *""",
                user_id, gained_experience,
            )

        # Send an output
        await db.disconnect()
        if user_plant_data['plant_nourishment'] < 0:
            return self.get_water_plant_dict("You sadly pour water into the dry soil of your silently wilting plant :c")

        # Set up our output text
        gained_exp_string = f"**{gained_experience}**" if gained_experience == original_gained_experience else f"~~{original_gained_experience}~~ **{gained_experience}**"
        output_lines = []
        if plant_data.get_nourishment_display_level(user_plant_data['plant_nourishment']) > plant_data.get_nourishment_display_level(user_plant_data['plant_nourishment'] - 1):
            output_lines.append(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_exp_string} experience, watching your plant grow!~")
        else:
            output_lines.append(f"You gently pour water into **{plant_level_row[0]['plant_name']}**'s soil, gaining you {gained_exp_string} experience~")
        for obj in multipliers:
            output_lines.append(f"**{obj['multiplier']}x**: {obj['text']}")
        for t in additional_text:
            output_lines.append(t)

        # And now we output ALL the information that we need for this to be an API route
        return self.get_water_plant_dict(
            text="\n".join(output_lines),
            success=True,
            gained_experience=gained_experience,
            new_nourishment_level=plant_level_row[0]['plant_nourishment'],
            new_user_experience=user_experience_row[0]['user_experience'],
            voted_on_topgg=voted_on_topgg,
            multipliers=multipliers,
        )

    @utils.command(aliases=['water', 'w'], cooldown_after_parsing=True)
    @commands.bot_has_permissions(send_messages=True)
    async def waterplant(self, ctx:utils.Context, *, plant_name:str):
        """
        Increase the growth level of your plant.
        """

        # Let's run all the bullshit
        item = await self.water_plant_backend(ctx.author.id, plant_name)
        if item['success'] is False:
            return await ctx.send(item['text'])
        output_lines = item['text'].split("\n")

        # Try and embed the message
        embed = None
        if ctx.guild is None or ctx.channel.permissions_for(ctx.guild.me).embed_links:

            # Make initial embed
            embed = utils.Embed(use_random_colour=True, description=output_lines[0])

            # Add multipliers
            if len(output_lines) > 1:
                embed.add_field(
                    "Multipliers", "\n".join([i.strip('') for i in output_lines[1:]]), inline=False
                )

            # Add "please vote for Flower" footer
            counter = 0
            ctx._set_footer(embed)

            def check(footer_text) -> bool:
                if item['voted_on_topgg']:
                    return 'vote' not in footer_text
                return 'vote' in footer_text
            while counter < 100 and check(embed.footer.text.lower()):
                ctx._set_footer(embed)
                counter += 1

            # Clear the text we would otherwise output
            output_lines.clear()

        # Send message
        return await ctx.send("\n".join(output_lines), embed=embed)

    async def delete_plant_backend(self, user_id:int, plant_name:str) -> dict:
        """
        The backend function for deleting a plant from the database. Either returns the deleted
        plant's data, or None.
        """

        async with self.bot.database() as db:
            data = await db("DELETE FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) RETURNING *", user_id, plant_name)
        if not data:
            return None
        return data[0]

    @utils.command(aliases=['delete'])
    @commands.bot_has_permissions(send_messages=True)
    async def deleteplant(self, ctx:utils.Context, *, plant_name:str):
        """
        Deletes your plant from the database.
        """

        data = await self.delete_plant_backend(ctx.author.id, plant_name)
        if not data:
            return await ctx.send(f"You have no plant names **{plant_name}**!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        return await ctx.send(f"Done - you've deleted your {data['plant_type'].replace('_', ' ')}.")

    @utils.command(aliases=['rename'])
    @commands.bot_has_permissions(send_messages=True)
    async def renameplant(self, ctx:utils.Context, before:str, *, after:str):
        """
        Gives a new name to your plant. Use "quotes" if your plant has a space in its name.
        """

        # Make sure some names were provided
        after = self.validate_name(after)
        if not after:
            raise utils.MissingRequiredArgumentString("after")
        if len(before) > 50 or len(before) == 0:
            return await ctx.send(f"You have no plants with the name **{before}**.", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        if len(after) > 50 or len(after) == 0:
            await ctx.send("That name is too long! Please give another one instead!")
            return
        if '\n' in after:
            await ctx.send("You can't have names with multiple lines in them! Please give another one instead!")

        # See about changing the name
        async with self.bot.database() as db:

            # Make sure the given name exists
            plant_has_before_name = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before)
            if not plant_has_before_name:
                return await ctx.send(f"You have no plants with the name **{before}**.", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

            # Make sure they own the plant
            if plant_has_before_name[0]['original_owner_id'] != ctx.author.id:
                return await ctx.send("You can't rename plants that you didn't own originally.")

            # Make sure they aren't trying to rename to a currently existing name
            plant_name_exists = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, after)
            if plant_name_exists:
                return await ctx.send(f"You already have a plant with the name **{after}**!", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))

            # Update plant name
            await db("UPDATE plant_levels SET plant_name=$3 WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", ctx.author.id, before, after)
        await ctx.send("Done!~")

    async def revive_plant_backend(self, user_id:int, plant_name:str):
        """
        The backend for reviving a plant.
        Returns a response string and whether or not the revive succeeded, as a tuple.
        """

        async with self.bot.database() as db:

            # See if they have enough revival tokens
            inventory_rows = await db("SELECT * FROM user_inventory WHERE user_id=$1 AND item_name='revival_token'", user_id)
            if not inventory_rows or inventory_rows[0]['amount'] < 1:
                return f"You don't have any revival tokens, <@{user_id}>! :c", False

            # See if the plant they specified exists
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)", user_id, plant_name)
            if not plant_rows:
                return f"You have no plants named **{plant_name}**.", False

            # See if the plant they specified is dead
            if plant_rows[0]['plant_nourishment'] >= 0:
                return f"Your **{plant_rows[0]['plant_name']}** plant isn't dead!", False

            # Revive the plant and remove a token
            await db.start_transaction()
            await db("UPDATE user_inventory SET amount=user_inventory.amount-1 WHERE user_id=$1 AND item_name='revival_token'", user_id)
            await db(
                """UPDATE plant_levels SET plant_nourishment=1, last_water_time=$3,
                plant_adoption_time=TIMEZONE('UTC', NOW()) WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2)""",
                user_id, plant_name, dt.utcnow() - timedelta(**self.bot.config.get('plants', {}).get('water_cooldown', {'minutes': 15}))
            )
            await db.commit_transaction()

        # And now we done
        return f"Revived **{plant_rows[0]['plant_name']}**, your {plant_rows[0]['plant_type'].replace('_', ' ')}! :D", True

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    async def revive(self, ctx:utils.Context, *, plant_name:str):
        """
        Use one of your revival tokens to be able to revive your plant.
        """

        response, success = await self.revive_plant_backend(ctx.author.id, plant_name)
        return await ctx.send(response, allowed_mentions=discord.AllowedMentions.none())


def setup(bot:utils.Bot):
    x = PlantCareCommands(bot)
    bot.add_cog(x)
