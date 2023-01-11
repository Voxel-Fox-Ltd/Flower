from __future__ import annotations

from datetime import datetime as dt
from typing import Optional, Literal
from typing_extensions import Self

from discord.ext import vbu, vfc as checkout

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
    )

    def __init__(
            self,
            user_id: int,
            plant_limit: int = 1,
            pot_type: Literal["clay"] = "clay",
            user_experience: int = 0,
            last_plant_shop_time: Optional[dt] = None,
            plant_pot_hue: Optional[int] = None):
        self.user_id = user_id
        self.plant_limit = plant_limit
        self.pot_type = pot_type
        self.experience = user_experience or 0
        self.last_plant_shop_time = last_plant_shop_time or dt(2000, 1, 1)
        self._plant_pot_hue = plant_pot_hue
        self.has_premium = False

    @classmethod
    def from_row(cls, row: UserSettingsRow):
        return cls(
            user_id=row["user_id"],
            plant_limit=row.get("plant_limit", 1),
            pot_type=row.get("pot_type", "clay"),
            user_experience=row.get("user_experience", 0),
            last_plant_shop_time=row.get("last_plant_shop_time", None),
            plant_pot_hue=row.get("plant_pot_hue", None),
        )

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
            db: vbu.Database | vbu.DatabaseTransaction,
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
            return cls.from_row(dict(user_id=user_id))  # pyright: ignore
        v = cls.from_row(record[0])
        v.has_premium = cls.check_premium(v.user_id)
        return v

    @staticmethod
    async def check_premium(user_id: int) -> bool:
        """
        Check if a given user ID has a Flower Premium subscription.
        """

        try:
            await (
                checkout
                .user_is_active("Flower Premium")
                .predicate(user_id)
            )
        except:
            return False
        else:
            return True

    async def update(
            self,
            db: vbu.Database | vbu.DatabaseTransaction,
            **kwargs) -> None:
        """
        Update this user info object in the database.
        """

        for i, o in kwargs.items():
            setattr(self, i, o)
        await db.call(
            """
            INSERT INTO
                user_settings
                (
                    user_id,
                    plant_limit,
                    pot_type,
                    user_experience,
                    last_plant_shop_time,
                    plant_pot_hue
                )
            VALUES
                (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6
                )
            ON CONFLICT
                (user_id)
            DO UPDATE
            SET
                plant_limit = excluded.plant_limit,
                pot_type = excluded.pot_type,
                user_experience = excluded.user_experience,
                last_plant_shop_time = excluded.last_plant_shop_time,
                plant_pot_hue = excluded.plant_pot_hue
            """,
            self.user_id,
            self.plant_limit,
            self.pot_type,
            self.experience,
            self.last_plant_shop_time,
            self.plant_pot_hue,
        )
