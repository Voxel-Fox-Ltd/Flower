from datetime import datetime as dt
import random

import discord
from discord.ext import vbu, commands

from cogs import utils

if __debug__:
    _poedit = lambda x: x

    # TRANSLATORS: Name of a command. Must be lowercase.
    _poedit("shop")
    # TRANSLATORS: Description of a command.
    _poedit("Opens the shop.")


_t = lambda i, x: vbu.translation(i, "flower").gettext(x)


class ShopCommand(vbu.Cog[utils.types.Bot]):

    @staticmethod
    def get_points_for_plant_pot(current_limit: int) -> int:
        """
        Get the amount of points needed to get the next level of pot.
        """

        if current_limit < 10:
            return 5_000 * (current_limit ** 2)
        return (45_000 * (current_limit - 9)) + 405_000

    async def get_user_available_plants(
            self,
            db: vbu.Database,
            user_id: int) -> dict[int, utils.Plant]:
        """
        Get the plants that the given user should have available to them.
        """

        # Check what plants they have available
        plant_shop_rows = await db.call(
            """
            SELECT
                *
            FROM
                user_available_plants
            WHERE
                user_id = $1
            """,
            user_id,
            type=utils.types.PlantShopRow,
        )

        # See if we have to generate some new plants
        generate_new = True
        if plant_shop_rows:
            now = dt.utcnow()
            last_shop = (
                plant_shop_rows[0]['last_shop_timestamp']
                or dt(2000, 1, 1)
            )
            generate_new = (
                (last_shop.year, last_shop.month)
                != (now.year, now.month)
            )

        # If they don't have any available plants (or their shop has
        # expired), generate new ones
        if generate_new:

            # Set up a list of everything that they might possibly be able
            # to get
            possible_available_plants: list[utils.Plant] = list()
            for item in self.bot.plants.values():
                if item.available is False:
                    continue
                if plant_shop_rows and item.name in plant_shop_rows[0].values():
                    continue
                possible_available_plants.append(item)

            # Decide randomly what they should have available
            available_plants = {}
            level = 0
            while level <= 6:
                add = random.choice(possible_available_plants)
                possible_available_plants.remove(add)
                available_plants[level] = add
                level += 1

            # Insert into database
            await db.call(
                """
                INSERT INTO
                    user_available_plants
                    (
                        user_id,
                        last_shop_timestamp,
                        plant_level_0,
                        plant_level_1,
                        plant_level_2,
                        plant_level_3,
                        plant_level_4,
                        plant_level_5,
                        plant_level_6
                    )
                VALUES
                    (
                        $1,
                        $2,
                        $3,
                        $4,
                        $5,
                        $6,
                        $7,
                        $8,
                        $9
                    )
                ON CONFLICT
                    (user_id)
                DO UPDATE
                SET
                    last_shop_timestamp = excluded.last_shop_timestamp,
                    plant_level_0 = excluded.plant_level_0,
                    plant_level_1 = excluded.plant_level_1,
                    plant_level_2 = excluded.plant_level_2,
                    plant_level_3 = excluded.plant_level_3,
                    plant_level_4 = excluded.plant_level_4,
                    plant_level_5 = excluded.plant_level_5,
                    plant_level_6 = excluded.plant_level_6
                """,
                user_id,
                dt.utcnow(),
                available_plants[0].name,
                available_plants[1].name,
                available_plants[2].name,
                available_plants[3].name,
                available_plants[4].name,
                available_plants[5].name,
                available_plants[6].name,
            )

            # Remove the last two items from the dict since we no longer
            # care about them
            del available_plants[6]
            del available_plants[5]

        # They have available plants, format into new dictionary
        else:
            available_plants = {
                0: self.bot.plants[plant_shop_rows[0]['plant_level_0']],
                1: self.bot.plants[plant_shop_rows[0]['plant_level_1']],
                2: self.bot.plants[plant_shop_rows[0]['plant_level_2']],
                3: self.bot.plants[plant_shop_rows[0]['plant_level_3']],
                4: self.bot.plants[plant_shop_rows[0]['plant_level_4']],
            }

        # And done
        return available_plants

    async def get_shop_components(
            self,
            db: vbu.Database,
            interaction: discord.Interaction):
        """
        Get the components that should be present for a user's shop.
        """

        # Get the user's information
        user_info = await utils.UserInfo.fetch_by_id(
            db,
            interaction.user.id,
        )
        user_plants = await utils.UserPlant.fetch_all_by_user_id(
            db,
            interaction.user.id,
        )

        # Get what plants they have available
        available_plants = await self.get_user_available_plants(
            db,
            interaction.user.id,
        )

        # Get what items the bot has available
        available_items = self.bot.items.copy()

        # Make buttons for each of the items
        plant_buttons: list[discord.ui.Button] = []
        item_buttons: list[discord.ui.Button] = []
        for plant in available_plants.values():
            plant_buttons.append(
                discord.ui.Button(
                    label=plant.display_name.capitalize(),
                    style=discord.ButtonStyle.primary,
                    custom_id=f"GETPLANT {plant.name}",
                    disabled=len(user_plants) >= user_info.plant_limit,
                )
            )
        for item in available_items.values():
            item_buttons.append(
                discord.ui.Button(
                    label=f"{item.display_name.capitalize()} (${item.price:,})",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"GETITEM {item.name}",
                    disabled=item.price > user_info.experience,
                )
            )

        # Add the plant pot to the item buttons
        if user_info.plant_limit < utils.constants.HARD_PLANT_CAP:
            plant_pot_price = self.get_points_for_plant_pot(user_info.plant_limit)
            item_buttons.insert(
                0,
                discord.ui.Button(
                    label=f"Plant pot (${plant_pot_price:,})",
                    style=discord.ButtonStyle.secondary,
                    custom_id="GETITEM plant_pot",
                    disabled=plant_pot_price > user_info.experience,
                )
            )

        # Present a list of buttons for them
        return discord.ui.MessageComponents(
            discord.ui.ActionRow(*plant_buttons),
            discord.ui.ActionRow(*item_buttons),
        )

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "shop")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Opens the shop.")
                for i in discord.Locale
            },
        ),
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def shop(self, ctx: vbu.SlashContext):
        """
        Opens the shop.
        """

        async with vbu.Database() as db:
            components = await self.get_shop_components(db, ctx.interaction)
        await ctx.interaction.response.send_message(
            _("What would you like to get from your shop?"),
            components=components,
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.checks.interaction_filter(start="GETPLANT")
    @vbu.i18n("flower")
    async def shop_plant_get(
            self,
            interaction: discord.ComponentInteraction,
            plant_type: str):
        """
        Pinged when a user clicks to get a plant added to their garden.
        """

        # Open the database to do some checks
        async with vbu.Database() as db:

            # Make sure they have space available in their pots
            user_plants = await utils.UserPlant.fetch_all_by_user_id(
                db,
                interaction.user.id,
            )
            if len(user_plants) >= utils.constants.HARD_PLANT_CAP:
                components = await self.get_shop_components(db, interaction)
                await interaction.response.edit_message(components=components)
                await interaction.followup.send(
                    _("You have no more available pots!"),
                    ephemeral=True,
                )
                return

            # See if they've hit their personal plant limit
            user_info = await utils.UserInfo.fetch_by_id(
                db,
                interaction.user.id,
            )
            if len(user_plants) >= user_info.plant_limit:
                components = await self.get_shop_components(db, interaction)
                await interaction.response.edit_message(components=components)
                await interaction.followup.send(
                    _("You have no more available pots!"),
                    ephemeral=True,
                )
                return

        # Spawn a modal for them to input their plant name
        modal = discord.ui.Modal(
            title=_("Plant Name"),
            custom_id=f"NAMEPLANT {plant_type}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        label=_("What would you like to name your plant?"),
                        style=discord.TextStyle.short,
                        required=True,
                        custom_id="PLANTNAME",
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_modal_submit")
    @vbu.checks.interaction_filter(start="NAMEPLANT")
    @vbu.i18n("flower")
    async def shop_plant_modal_name_submit(
            self,
            interaction: discord.ModalInteraction,
            plant_type: str):
        """
        Pinged when a user names a plant that they're buying from the shop.
        """

        # Get their given plant name from the modal's components
        plant_name: str = (
            interaction
            .components[0]  # pyright: ignore (actionrow)
            .components[0]  # (inputtext)
            .value
        )

        # Open a database connection to do some checks.
        async with vbu.Database() as db:

            # Make sure they've not hit the global plant limit
            user_plants = await utils.UserPlant.fetch_all_by_user_id(
                db,
                interaction.user.id,
            )
            if len(user_plants) >= utils.constants.HARD_PLANT_CAP:
                components = await self.get_shop_components(db, interaction)
                await interaction.response.edit_message(components=components)
                await interaction.followup.send(
                    _("You have no more available pots!"),
                    ephemeral=True,
                )
                return

            # Make sure they've not hit their own personal limit
            user_info = await utils.UserInfo.fetch_by_id(
                db,
                interaction.user.id,
            )
            if len(user_plants) >= user_info.plant_limit:
                components = await self.get_shop_components(db, interaction)
                await interaction.response.edit_message(components=components)
                await interaction.followup.send(
                    _("You have no more available pots!"),
                    ephemeral=True,
                )
                return

            # Make sure the name they gave isn't in use already
            in_use_plant_names: list[str] = [
                i.name.casefold()
                for i in user_plants
            ]
            if plant_name.casefold() in in_use_plant_names:
                await interaction.response.send_message(
                    _("You already have a plant with that name!"),
                    ephemeral=True,
                )
                return

            # All seems well and good; add the plant to the user's list :)
            new_plant = utils.UserPlant(
                id=None,
                user_id=interaction.user.id,
                plant_type=plant_type,
                plant_name=plant_name,
                original_owner_id=interaction.user.id,
                plant_pot_hue=user_info.plant_pot_hue,
            )
            await new_plant.update(db)

            # Get the new components
            components = await self.get_shop_components(db, interaction)

        # Tell the user it's been done
        await interaction.response.defer_update()
        await interaction.edit_original_message(components=components)
        await interaction.followup.send(
            _("You have successfully bought a new plant!"),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.checks.interaction_filter(start="GETITEM")
    @vbu.i18n("flower")
    async def shop_item_get(
            self,
            interaction: discord.ComponentInteraction,
            item_name: str):
        """
        Pinged when a user tries to buy an item from the shop.
        """

        # Get the item from the cache
        if item_name == "plant_pot":
            item_object = utils.Item(
                item_name="plant_pot",
                display_name="plant pot",
                item_price=0,
            )
        else:
            item_object = self.bot.items[item_name]

        # See if the user has enough experience to buy it
        async with vbu.Database() as db:
            user_info = await utils.UserInfo.fetch_by_id(
                db,
                interaction.user.id,
            )
            if item_object.name == "plant_pot":
                item_object.price = self.get_points_for_plant_pot(user_info.plant_limit)
            if user_info.experience < item_object.price:
                components = await self.get_shop_components(db, interaction)
                await interaction.response.edit_message(components=components)
                await interaction.followup.send(
                    _("You don't have enough experience to buy that!"),
                    ephemeral=True,
                )
                return

            # They do - start a transaction, reduce the user's experience, and
            # add the item to the user via the inventory object
            if item_object.name == "plant_pot":
                await user_info.update(
                    db,
                    experience=user_info.experience - item_object.price,
                    plant_limit=user_info.plant_limit + 1,
                )
            else:
                async with db.transaction() as trans:
                    await user_info.update(
                        trans,
                        experience=user_info.experience - item_object.price,
                    )
                    user_inventory = await utils.UserInventory.fetch_by_id(
                        trans,
                        interaction.user.id,
                    )
                    await user_inventory.update(
                        trans,
                        **{
                            item_object.name: 1,
                        },
                    )

            # Get new shop components
            components = await self.get_shop_components(db, interaction)

        # Tell the user they got one successfully
        await interaction.response.edit_message(components=components)
        await interaction.followup.send(
            _("You have successfully bought a new item!"),
            ephemeral=True,
        )

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "refreshshop")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, (
                    "Use one of your refresh tokens to give you a new set of "
                    "shop items."
                ))
                for i in discord.Locale
            },
        ),
    )
    @commands.is_slash_command()
    @vbu.i18n("flower")
    async def refreshshop(
            self,
            ctx: vbu.SlashContext):
        """
        Use one of your refresh tokens to give you a new set of shop items.
        """

        # Get the user's inventory
        async with vbu.Database() as db:
            user_inventory = await utils.UserInventory.fetch_by_id(
                db,
                ctx.author.id,
            )

        # See if they have any refresh tokens
        if user_inventory.get("refresh_token").amount <= 0:
            await ctx.interaction.response.send_message(
                _("You don't have any refresh tokens!"),
                ephemeral=True,
            )
            return

        # They do - start a transaction, reduce the user's refresh tokens, and
        # add the new items to the shop
        async with vbu.Database() as db:
            async with db.transaction() as trans:
                await user_inventory.update(
                    trans,
                    refresh_token=-1,
                )
                await trans.call(
                    """
                    UPDATE
                        user_available_plants
                    SET
                        last_shop_timestamp = '2000-01-01 00:00:00'
                    WHERE
                        user_id = $1
                    """,
                    ctx.interaction.user.id,
                )

        # Tell them we've done it
        await ctx.interaction.response.send_message(
            _("You have successfully refreshed your shop!"),
        )


def setup(bot: utils.types.Bot):
    x = ShopCommand(bot)
    bot.add_cog(x)
