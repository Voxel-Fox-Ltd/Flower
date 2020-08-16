import random


class PlantType(object):
    """A data type containing the data for any given plant type"""

    def __init__(self, name:str, required_experience:int, experience_gain:dict, available_variants:dict, nourishment_display_levels:dict, soil_hue:int, visible:bool, available:bool):
        self.name = name
        self.required_experience = required_experience
        self.experience_gain = experience_gain
        self.available_variants = available_variants
        self.nourishment_display_levels = nourishment_display_levels
        self.soil_hue = soil_hue
        self.visible = visible
        self.available = available
        self.max_nourishment_level = max([int(i) for i in self.nourishment_display_levels.keys()]) + 1

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
