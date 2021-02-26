import random
import re
import math


class PlantType(object):
    """A data type containing the data for any given plant type"""

    PLANT_LEVEL_MAPPING = {
        0: {
            "cost": 0,
            "experience_gain": {
                "maximum": 50,
                "minimum": 30,
            },
        },
        1: {
            "cost": 500,
            "experience_gain": {
                "maximum": 80,
                "minimum": 30,
            },
        },
        2: {
            "cost": 1_720,
            "experience_gain": {
                "maximum": 120,
                "minimum": 50,
            },
        },
        3: {
            "cost": 3_720,
            "experience_gain": {
                "maximum": 150,
                "minimum": 80,
            },
        },
        4: {
            "cost": 5_030,
            "experience_gain": {
                "maximum": 230,
                "minimum": 150,
            },
        },
        5: {
            "cost": 9_500,
            "experience_gain": {
                "maximum": 250,
                "minimum": 150,
            },
        },
        6: {
            "cost": 12_500,
            "experience_gain": {
                "maximum": 300,
                "minimum": 160,
            },
        },
    }

    def __init__(self, name:str, plant_level:int, soil_hue:int, visible:bool, available:bool, artist:str, stages:int=None, nourishment_display_levels:dict=None, available_variants:dict=None):
        self.name = name
        self.plant_level = plant_level
        self.required_experience = self.PLANT_LEVEL_MAPPING[self.plant_level]["cost"]
        self.experience_gain = self.PLANT_LEVEL_MAPPING[self.plant_level]["experience_gain"]
        self.available_variants = available_variants
        self.nourishment_display_levels = nourishment_display_levels if nourishment_display_levels else self.calculate_display_for_stages(stages)
        self.stages = stages if stages else len(nourishment_display_levels)
        self.soil_hue = soil_hue
        self.visible = visible
        self.available = available
        self.artist = artist
        self.max_nourishment_level = 21  # max([int(i) for i in self.nourishment_display_levels.keys()]) + 1

    @staticmethod
    def calculate_display_for_stages(stages:int) -> dict:
        """
        Work out which stages should level up a plant display level.
        """

        return {i: math.ceil((i * stages) / 20) for i in range(1, 21)}

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

        return 1
        # return self.available_variants[str(stage)]

    def get_nourishment_display_level(self, nourishment:int) -> int:
        """Get the display level for a given amount of nourishment"""

        if nourishment <= 0:
            return self.get_nourishment_display_level(1)
        if str(nourishment) in self.nourishment_display_levels:
            return self.nourishment_display_levels[str(nourishment)]
        return self.get_nourishment_display_level(nourishment - 1)

    @staticmethod
    def validate_name(name:str):
        """
        Validates the name of a plant
        Input is the name, output is their validated plant name.
        """

        name = name.strip('"“”\'').replace('\n', ' ').strip()
        while "  " in name:
            name = name.replace("  ", " ")
        name = re.sub(r"<@[&!]?(\d+?)>", lambda m: m.group(1), name)
        name = re.sub(r"<#(\d+?)>", lambda m: m.group(1), name)
        name = re.sub(r"<(?:a)?:(.+?):(\d+?)>", lambda m: m.group(1), name)
        return name
