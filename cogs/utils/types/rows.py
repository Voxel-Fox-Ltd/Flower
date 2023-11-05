from __future__ import annotations

import uuid
from typing import TypedDict, Optional, Literal
from datetime import datetime as dt


__all__ = (
    'UserSettingsRow',
    'PlantLevelsRow',
    'UserInventoryRow',
    'PlantShopRow',
)


class UserSettingsRow(TypedDict):
    user_id: int
    plant_limit: int
    pot_type: Literal["clay"]
    user_experience: int
    last_plant_shop_time: Optional[dt]
    plant_pot_hue: int
    has_premium: bool
    premium_expiry_time: Optional[dt]
    premium_subscription_delete_url: str


class PlantLevelsRow(TypedDict):
    id: uuid.UUID
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


class UserInventoryRow(TypedDict):
    user_id: int
    item_name: str
    amount: int


class PlantShopRow(TypedDict):
    user_id: int
    plant_level_0: str
    plant_level_1: str
    plant_level_2: str
    plant_level_3: str
    plant_level_4: str
    plant_level_5: str
    plant_level_6: str
    last_shop_timestamp: dt
