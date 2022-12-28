from __future__ import annotations

from datetime import datetime as dt
from typing import Optional
from typing_extensions import Self

from discord.ext import vbu

from .plant import Plant
from ..types import PlantLevelsRow


__all__ = (
    'UserPlant',
)


class UserPlant:
    """
    A representation of a user's plant from the database.
    """

    __slots__ = (
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
            user_id: int,
            plant_name: str,
            plant_type: str,
            plant_variant: int,
            plant_nourishment: int,
            last_water_time: dt,
            original_owner_id: int,
            plant_pot_hue: int,
            plant_adoption_time: dt,
            notification_sent: bool = False,
            immortal: bool = False):
        self.user_id: int = user_id
        self.name: str = plant_name
        self.type: str = plant_type
        self.variant: int = plant_variant
        self.nourishment: int = plant_nourishment
        self.last_water_time: dt = last_water_time
        self.original_owner_id: int = original_owner_id
        self.pot_hue: int = plant_pot_hue
        self.adoption_time: dt = plant_adoption_time
        self.notification_sent: bool = notification_sent
        self.immortal: bool = immortal

    @property
    def is_dead(self) -> bool:
        """
        Returns whether or not the plant is dead.
        """

        return (
            self.nourishment <= 0
            and not self.immortal
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
            user_id, plant_name,
            type=PlantLevelsRow,
        )
        if not plant:
            return None

        # Return the plant object
        return cls(**plant[0])

    async def update(
            self,
            db: vbu.Database,
            **kwargs):
        """
        Update the plant in the database.
        """

        for i, o in kwargs.items():
            setattr(self, i, o)

        # Update the plant in the database
        await db.call(
            """
            UPDATE
                plant_levels
            SET
                user_id = $1,
                plant_name = $2,
                plant_type = $3,
                plant_variant = $4,
                plant_nourishment = $5,
                last_water_time = $6,
                original_owner_id = $7,
                plant_pot_hue = $8,
                plant_adoption_time = $9,
                notification_sent = $10,
                immortal = $11
            WHERE
                user_id = $1
            AND
                plant_name = $2
            """,
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
                user_id = $1
            AND
                plant_name = $2
            """,
            self.user_id, self.name,
        )
