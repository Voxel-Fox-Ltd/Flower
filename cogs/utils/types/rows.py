import typing
from datetime import datetime as dt


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


UserSettingsRows = typing.List[UserSettingsRow]


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

PlantLevelsRows = typing.List[PlantLevelsRow]


class UserInventoryRow(typing.TypedDict):
    user_id: int
    item_name: str
    amount: int

UserInventoryRows = typing.List[UserInventoryRow]
