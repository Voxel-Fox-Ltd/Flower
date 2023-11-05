from __future__ import annotations

from dataclasses import dataclass, field
from typing_extensions import Self

from discord.ext import vbu

from ..types import UserInventoryRow


__all__ = (
    'UserInventoryItem',
    'UserInventory',
)


class UserInventoryItem:

    __slots__ = (
        'user_id',
        'name',
        '_amount',
    )

    def __init__(
            self,
            user_id: int,
            name: str,
            amount: int):
        self.user_id = user_id
        self.name = name
        self._amount = amount

    @property
    def amount(self) -> int:
        if self._amount < 0:
            return 0
        return self._amount

    @amount.setter
    def amount(self, value: int):
        self._amount = value

    @property
    def display_name(self):
        return self.name.replace("_", " ")


@dataclass
class UserInventory:
    """
    A representation of the inventory for a user.

    Attributes
    -----------
    user_id : int
        The ID of the associated user.
    items : dict[str, UserInventoryItem]
        A dictionary of the items in the user's inventory.
    """

    user_id: int
    items: dict[str, UserInventoryItem] = field(default_factory=dict)

    def get(self, item_name: str) -> UserInventoryItem:
        """
        Get an item from the user inventory.

        Parameters
        ----------
        item_name : str
            The name of the item to get.

        Returns
        -------
        UserInventoryItem
            The item in the user's inventory.
        """

        return self.items.get(
            item_name.lower(),
            UserInventoryItem(
                self.user_id,
                item_name,
                0,
            ),
        )

    @classmethod
    async def fetch_by_id(
            cls,
            db: vbu.Database | vbu.DatabaseTransaction,
            user_id: int) -> Self:
        """
        Fetch a user inventory object by user ID.
        """

        inventory_rows = await db.call(
            """
            SELECT
                item_name, amount
            FROM
                user_inventory
            WHERE
                user_id = $1
            """,
            user_id,
            type=UserInventoryRow,
        )
        return cls(
            user_id=user_id,
            items={
                row['item_name'].lower(): UserInventoryItem(
                    user_id=user_id,
                    name=row['item_name'],
                    amount=row['amount'],
                )
                for row in inventory_rows
            }
        )

    async def update(
            self,
            db: vbu.Database | vbu.DatabaseTransaction,
            **kwargs):
        """
        Update the amounts of specific items in the user inventory. This is a
        change rather than a set operation, eg ``amount += x`` rather than
        ``amount = x``.
        """

        for item_name, amount in kwargs.items():
            item = self.get(item_name)
            item.amount += amount
            self.items[item_name] = item
        if isinstance(db, vbu.DatabaseTransaction):
            await self._save(db)
        else:
            await self.save(db)

    async def save(self, db: vbu.Database) -> None:
        """
        Save the user inventory object to the database.
        """

        async with db.transaction(commit_on_exit=False) as transaction:
            await self._save(transaction)
            await transaction.commit()

    async def _save(self, db: vbu.Database | vbu.DatabaseTransaction) -> None:
        await db.execute_many(
            """
            INSERT INTO
                user_inventory
                (
                    user_id,
                    item_name,
                    amount
                )
            VALUES
                (
                    $1,
                    $2,
                    $3
                )
            ON CONFLICT
                (user_id, item_name)
            DO UPDATE
            SET
                amount = excluded.amount
            """,
            *[
                (self.user_id, item.name, item.amount)
                for item in self.items.values()
            ]
        )
