import typing

from discord.ext import vbu

from cogs import utils


class Bot(vbu.Bot):
    plants: typing.Dict[str, utils.PlantType]
    items: typing.Dict[str, utils.ItemType]
