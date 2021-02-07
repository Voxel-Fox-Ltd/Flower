class ItemType(object):

    def __init__(self, item_name:str, item_price:int, usage:str):
        self.name = item_name
        self.price = item_price
        self.usage = usage

    @property
    def display_name(self):
        return self.name.replace('_', ' ')
