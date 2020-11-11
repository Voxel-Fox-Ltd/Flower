class ItemType(object):

    def __init__(self, item_name:str, item_price:int):
        self.name = item_name
        self.price = item_price

    @property
    def display_name(self):
        return self.name.replace('_', ' ')
