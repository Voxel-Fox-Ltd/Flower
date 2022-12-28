from __future__ import annotations

import typing
from datetime import datetime as dt


__all__ = (
    'UserSettingsRow',
    'PlantLevelsRow',
    'UserInventoryRow',
)


class UserSettingsRow(typing.TypedDict):
    user_id: int
    plant_limit: int
    pot_type: typing.Literal["clay"]
    user_experience: int
    last_plant_shop_time: typing.Optional[dt]
    plant_pot_hue: int
    has_premium: bool
    premium_expiry_time: typing.Optional[dt]
    premium_subscription_delete_url: str


class PlantLevelsRow(typing.TypedDict):
    user_id: int
    plant_name: str
    plant_type: str
    plant_variant: int
    plant_nourishment: int
    last_water_time: dt
    original_owner_id: int
    plant_pot_hue: int
    plant_adoption_time: dt
    notification_sent: bool
    immortal: bool


class UserInventoryRow(typing.TypedDict):
    user_id: int
    item_name: str
    amount: int
