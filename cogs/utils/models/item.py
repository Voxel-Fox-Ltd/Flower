from __future__ import annotations


__all__ = (
    'Item',
)


class Item:

    __slots__ = (
        'name',
        'display',
        'price',
    )

    def __init__(
            self,
            item_name: str,
            display_name: str,
            item_price: int):
        self.name = item_name
        self.display = display_name
        self.price = item_price

    @property
    def display_name(self) -> str:
        return self.display
