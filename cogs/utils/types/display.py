from typing import TypedDict


__all__ = (
    'UserPlantDisplayData',
)


class UserPlantDisplayData(TypedDict):
    """
    A dict of data used to display a plant.
    """

    plant_type: str
    plant_nourishment: int
    pot_type: str
    pot_hue: int
