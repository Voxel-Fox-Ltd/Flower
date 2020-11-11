import random


class PlantType(object):
    """A data type containing the data for any given plant type"""

    PLANT_LEVEL_MAPPING = {
        0: {
            "cost": 0,
            "experience_gain": {
                "maximum": 5,
                "minimum": 3,
            },
        },
        1: {
            "cost": 50,
            "experience_gain": {
                "maximum": 8,
                "minimum": 3,
            },
        },
        2: {
            "cost": 172,
            "experience_gain": {
                "maximum": 12,
                "minimum": 5,
            },
        },
        3: {
            "cost": 372,
            "experience_gain": {
                "maximum": 15,
                "minimum": 8,
            },
        },
        4: {
            "cost": 503,
            "experience_gain": {
                "maximum": 23,
                "minimum": 15,
            },
        },
        5: {
            "cost": 950,
            "experience_gain": {
                "maximum": 25,
                "minimum": 15,
            },
        },
        6: {
            "cost": 1250,
            "experience_gain": {
                "maximum": 30,
                "minimum": 16,
            },
        },
    }

    def __init__(self, name:str, plant_level:int, available_variants:dict, nourishment_display_levels:dict, soil_hue:int, visible:bool, available:bool, artist:str):
        self.name = name
        self.plant_level = plant_level
        self.required_experience = self.PLANT_LEVEL_MAPPING[self.plant_level]["cost"]
        self.experience_gain = self.PLANT_LEVEL_MAPPING[self.plant_level]["experience_gain"]
        self.available_variants = available_variants
        self.nourishment_display_levels = nourishment_display_levels
        self.soil_hue = soil_hue
        self.visible = visible
        self.available = available
        self.artist = artist
        self.max_nourishment_level = max([int(i) for i in self.nourishment_display_levels.keys()]) + 1

    def __str__(self):
        return f"<Plant {self.name} - level {self.plant_level}>"

    @property
    def display_name(self):
        return self.name.replace("_", " ")

    def __gt__(self, other):
        if not isinstance(other, self.__class__):
            raise ValueError()
        return (self.required_experience, self.name) > (other.required_experience, other.name)

    def __lt__(self, other):
        if not isinstance(other, self.__class__):
            raise ValueError()
        return (self.required_experience, self.name) < (other.required_experience, other.name)

    def __ge__(self, other):
        if not isinstance(other, self.__class__):
            raise ValueError()
        return self.__gt__(other) or self.required_experience == other.required_experience

    def get_experience(self) -> int:
        """Gets a random amount of experience"""

        return random.randint(self.experience_gain['minimum'], self.experience_gain['maximum'])

    def get_available_variants(self, stage:int) -> int:
        """Tells you how many variants are available for a given growth stage"""

        return self.available_variants[str(stage)]

    def get_nourishment_display_level(self, nourishment:int) -> int:
        """Get the display level for a given amount of nourishment"""

        if nourishment <= 0:
            return self.get_nourishment_display_level(1)
        if str(nourishment) in self.nourishment_display_levels:
            return self.nourishment_display_levels[str(nourishment)]
        return self.get_nourishment_display_level(nourishment - 1)
