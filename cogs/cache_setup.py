import os
import glob
import json
import asyncio

from cogs import utils


def setup(bot: utils.types.Bot):
    """
    Load relevant information into the bot object.
    """

    # Load up all the plants
    plant_directories = glob.glob("images/plants/[!_]*/")
    plant_names = [
        i.strip(os.sep).split(os.sep)[-1]
        for i in plant_directories
    ]
    available_plants = []

    # Check the plant JSON file
    for name in plant_names:
        with open(f"images/plants/{name}/pack.json") as a:
            data = json.load(a)
        data.update({"name": name})
        available_plants.append(data)

    # Dictionary it up
    try:
        bot.plants.clear()
    except AttributeError:
        pass
    bot.plants = {
        i['name']: utils.Plant(**i)
        for i in available_plants
    }

    # Add the items
    bot.items = {
        "revival_token": utils.Item(
            item_name="revival_token",
            display_name="revival token",
            item_price=utils.constants.REVIVAL_TOKEN_PRICE,
        ),
        "refresh_token": utils.Item(
            item_name="refresh_token",
            display_name="shop refresh token",
            item_price=utils.constants.REFRESH_TOKEN_PRICE,
        ),
        "immortal_plant_juice": utils.Item(
            item_name="immortal_plant_juice",
            display_name="immortal plant juice",
            item_price=utils.constants.IMMORTAL_PLANT_JUICE_PRICE,
        ),
    }

    # Cache application command IDs
    asyncio.create_task(bot.load_application_command_ids())


def teardown(bot: utils.types.Bot):
    """
    Clear items from the bot's internal cache.
    """

    try:
        bot.plants.clear()
    except AttributeError:
        pass
    try:
        bot.items.clear()
    except AttributeError:
        pass
