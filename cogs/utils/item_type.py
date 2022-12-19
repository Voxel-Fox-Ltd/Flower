from __future__ import annotations


__all__ = (
    'ItemType',
)


class ItemType:

    __slots__ = (
        'name',
        'display',
        'price',
        'usage',
    )

    def __init__(
            self,
            item_name: str,
            display_name: str,
            item_price: int,
            usage: str):
        self.name = item_name
        self.display = display_name
        self.price = item_price
        self.usage = usage

    @property
    def display_name(self) -> str:
        return self.display
