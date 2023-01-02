from __future__ import annotations

from typing import TYPE_CHECKING

from enum import Enum

from discord.ext import vbu


__all__ = (
    'Achievement',
    'update_achievement_count',
)


class Achievement(Enum):
    waters = "water_count"
    gives = "give_count"
    trades = "trade_count"
    revives = "revive_count"
    immortalizes = "immortalize_count"
    deaths = "death_count"


async def update_achievement_count(
            db: vbu.Database,
            user_id: int,
            achievement: Achievement,
            count: int = 1):
        """
        Update the achievement count for a given user.

        Parameters
        ----------
        """

        await db.call(
            """
            INSERT INTO
                user_achievement_counts
                (
                    user_id,
                    {0}
                )
            VALUES
                (
                    $1,
                    $2
                )
            ON CONFLICT
                (user_id)
            DO UPDATE
            SET
                {0} = user_achievement_counts.{0} + excluded.{0}
            """.format(achievement.value),
            user_id, count,
        )
