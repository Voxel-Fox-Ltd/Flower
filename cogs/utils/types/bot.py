from __future__ import annotations

import typing

from discord.ext import vbu

from cogs import utils


class _Plants(typing.TypedDict):
    non_subscriber_plant_cap: int
    hard_plant_cap: int
    revival_token_price: int
    refresh_token_price: int
    immortal_plant_juice_price: int

    death_timeout: dict
    water_cooldown: dict
    notification_time: dict
    guest_water_cooldown: dict


class _BotConfig(vbu.types.BotConfig):
    plants: _Plants


class Bot(vbu.Bot):
    plants: typing.Dict[str, utils.PlantType]
    items: typing.Dict[str, utils.ItemType]
    config: _BotConfig
