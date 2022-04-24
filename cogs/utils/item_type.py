from __future__ import annotations


class ItemType(object):

    def __init__(self, item_name:str, display_name:str, item_price:int, usage:str):
        self.name = item_name
        self.display = display_name
        self.price = item_price
        self.usage = usage

    @property
    def display_name(self):
        return self.display
        # return self.name.replace('_', ' ')
