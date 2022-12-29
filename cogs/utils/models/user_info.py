from __future__ import annotations

from datetime import datetime as dt
from typing import Optional, Literal
from typing_extensions import Self

from discord.ext import vbu

from ..types import UserSettingsRow


class UserInfo:

    __slots__ = (
        'user_id',
        'plant_limit',
        'pot_type',
        'experience',
        'last_plant_shop_time',
        '_plant_pot_hue',
        'has_premium',
        'premium_expiry_time',
        'premium_subscription_delete_url',
    )

    def __init__(
            self,
            user_id: int,
            plant_limit: int = 1,
            pot_type: Literal["clay"] = "clay",
            user_experience: int = 0,
            last_plant_shop_time: Optional[dt] = None,
            plant_pot_hue: Optional[int] = None,
            has_premium: bool = False,
            premium_expiry_time: Optional[dt] = None,
            premium_subscription_delete_url: Optional[str] = None):
        self.user_id = user_id
        self.plant_limit = plant_limit
        self.pot_type = pot_type
        self.experience = user_experience
        self.last_plant_shop_time = last_plant_shop_time
        self._plant_pot_hue = plant_pot_hue
        self.has_premium = has_premium
        self.premium_expiry_time = premium_expiry_time
        self.premium_subscription_delete_url = premium_subscription_delete_url

    @property
    def plant_pot_hue(self) -> int:
        if self._plant_pot_hue is None:
            return self.user_id % 360
        return self._plant_pot_hue

    @plant_pot_hue.setter
    def plant_pot_hue(self, value: int) -> None:
        self._plant_pot_hue = value

    @classmethod
    async def fetch_by_id(
            cls,
            db: vbu.Database,
            user_id: int) -> Self:
        """
        Fetch a user info object by user ID.
        """

        record = await db.call(
            """
            SELECT
                *
            FROM
                user_settings
            WHERE
                user_id = $1
            """,
            user_id,
            type=UserSettingsRow,
        )
        if not record:
            return cls(user_id=user_id)
        return cls(**record[0])

    async def update(
            self,
            db: vbu.Database,
            **kwargs) -> None:
        """
        Update this user info object in the database.
        """

        for i, o in kwargs.items():
            setattr(self, i, o)
        await db.call(
            """
            INSERT INTO
                user_info
                (
                    user_id,
                    plant_limit,
                    pot_type,
                    user_experience,
                    last_plant_shop_time,
                    plant_pot_hue,
                    has_premium,
                    premium_expiry_time,
                    premium_subscription_delete_url
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
                plant_limit = excluded.plant_limit,
                pot_type = excluded.pot_type,
                user_experience = excluded.user_experience,
                last_plant_shop_time = excluded.last_plant_shop_time,
                plant_pot_hue = excluded.plant_pot_hue,
                has_premium = excluded.has_premium,
                premium_expiry_time = excluded.premium_expiry_time,
                premium_subscription_delete_url = excluded.premium_subscription_delete_url
            """,
            self.user_id,
            self.plant_limit,
            self.pot_type,
            self.experience,
            self.last_plant_shop_time,
            self.plant_pot_hue,
            self.has_premium,
            self.premium_expiry_time,
            self.premium_subscription_delete_url,
        )
