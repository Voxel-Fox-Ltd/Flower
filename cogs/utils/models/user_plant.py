from __future__ import annotations

import uuid
from datetime import datetime as dt
from typing import Optional
from typing_extensions import Self

from discord.ext import vbu

from .plant import Plant
from ..types import PlantLevelsRow
from ..constants import WATER_COOLDOWN


__all__ = (
    'UserPlant',
)


class UserPlant:
    """
    A representation of a user's plant from the database.
    """

    __slots__ = (
        '_id',
        'user_id',
        'name',
        'type',
        'variant',
        'nourishment',
        'last_water_time',
        'original_owner_id',
        'pot_hue',
        'adoption_time',
        'notification_sent',
        'immortal',
    )

    def __init__(
            self,
            id: Optional[uuid.UUID],
            user_id: int,
            plant_name: str,
            plant_type: str,
            plant_variant: int = 0,
            plant_nourishment: int = 0,
            last_water_time: Optional[dt] = None,
            original_owner_id: Optional[int] = None,
            plant_pot_hue: int = 0,
            plant_adoption_time: Optional[dt] = None,
            notification_sent: bool = False,
            immortal: bool = False):
        self.id = id  # pyright: ignore
        self.user_id: int = user_id
        self.name: str = plant_name
        self.type: str = plant_type
        self.variant: int = plant_variant
        self.nourishment: int = plant_nourishment
        self.last_water_time: dt = last_water_time or dt.utcnow()
        self.original_owner_id: int = original_owner_id or user_id
        self.pot_hue: int = plant_pot_hue
        self.adoption_time: dt = plant_adoption_time or dt.utcnow()
        self.notification_sent: bool = notification_sent
        self.immortal: bool = immortal

    @property
    def id(self) -> str:
        if self._id is None:
            self._id = uuid.uuid4()
        return str(self._id)

    @id.setter
    def id(self, value: uuid.UUID | str | None):
        if isinstance(value, str):
            value = uuid.UUID(value)
        self._id = value

    @property
    def is_dead(self) -> bool:
        """
        Returns whether or not the plant is dead.
        """

        return (
            self.nourishment < 0
            and not self.immortal
        )

    @property
    def is_waterable(self) -> bool:
        return (
            self.last_water_time + WATER_COOLDOWN < dt.utcnow()
            or self.nourishment == 0
        )

    @property
    def plant(self) -> Plant:
        return Plant.all_plants[self.type]

    @classmethod
    async def fetch_by_name(
            cls,
            db: vbu.Database,
            user_id: int,
            plant_name: str) -> Optional[Self]:
        """
        Get a user's plant from the database.
        """

        # Get the plant from the database
        plant = await db.call(
            """
            SELECT
                *
            FROM
                plant_levels
            WHERE
                user_id = $1
            AND
                plant_name = $2
            """,
            user_id, plant_name.strip(),
            type=PlantLevelsRow,
        )
        if not plant:
            return None

        # Return the plant object
        return cls(**plant[0])

    @classmethod
    async def fetch_all_by_user_id(
            cls,
            db: vbu.Database,
            user_id: int) -> list[Self]:
        """
        Get a user's plant from the database.
        """

        # Get the plant from the database
        plant = await db.call(
            """
            SELECT
                *
            FROM
                plant_levels
            WHERE
                user_id = $1
            """,
            user_id,
            type=PlantLevelsRow,
        )
        return [
            cls(**p)
            for p in plant
        ]

    async def update(
            self,
            db: vbu.Database | vbu.DatabaseTransaction,
            **kwargs):
        """
        Update the plant in the database.
        """

        for i, o in kwargs.items():
            setattr(self, i, o)

        # Update the plant in the database
        await db.call(
            """
            INSERT INTO
                plant_levels
                (
                    id,
                    user_id,
                    plant_name,
                    plant_type,
                    plant_variant,
                    plant_nourishment,
                    last_water_time,
                    original_owner_id,
                    plant_pot_hue,
                    plant_adoption_time,
                    notification_sent,
                    immortal
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
                    $9,
                    $10,
                    $11,
                    $12
                )
            ON CONFLICT
                (id)
            DO UPDATE
            SET
                user_id = excluded.user_id,
                plant_name = excluded.plant_name,
                plant_type = excluded.plant_type,
                plant_variant = excluded.plant_variant,
                plant_nourishment = excluded.plant_nourishment,
                last_water_time = excluded.last_water_time,
                original_owner_id = excluded.original_owner_id,
                plant_pot_hue = excluded.plant_pot_hue,
                plant_adoption_time = excluded.plant_adoption_time,
                notification_sent = excluded.notification_sent,
                immortal = excluded.immortal
            """,
            self.id,
            self.user_id,
            self.name,
            self.type,
            self.variant,
            self.nourishment,
            self.last_water_time,
            self.original_owner_id,
            self.pot_hue,
            self.adoption_time,
            self.notification_sent,
            self.immortal,
        )

    async def delete(
            self,
            db: vbu.Database):
        """
        Delete the plant from the database.
        """

        # Delete the plant from the database
        await db.call(
            """
            DELETE FROM
                plant_levels
            WHERE
                id = $1
            """,
            self.id,
        )
