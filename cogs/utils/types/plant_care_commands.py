from __future__ import annotations

from typing import List, TypedDict


class WaterPlantMultiplier(TypedDict):
    multiplier: float
    text: str


class WaterPlantPayload(TypedDict):
    text: str
    success: bool
    gained_experience: int
    new_nourishment_level: int
    voted_on_topgg: bool
    new_user_experience: int
    multipliers: List[WaterPlantMultiplier]
