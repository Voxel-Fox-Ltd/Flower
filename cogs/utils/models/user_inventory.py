from __future__ import annotations

from dataclasses import dataclass, field
from typing_extensions import Self

from discord.ext import vbu

from ..types import UserInventoryRow


__all__ = (
    'UserInventoryItem',
    'UserInventory',
)


@dataclass
class UserInventoryItem:
    user_id: int
    name: str
    amount: int


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
            item_name,
            UserInventoryItem(
                self.user_id,
                item_name,
                0,
            ),
        )

    @classmethod
    async def fetch_by_id(
            cls,
            db: vbu.Database,
            user_id: int) -> Self:
        """
        Fetch a user inventory object by user ID.
        """

        inventory_rows = await db.call(
            """
            SELECT
                name, amount
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
                row['item_name']: UserInventoryItem(
                    user_id=user_id,
                    name=row['item_name'],
                    amount=row['amount'],
                )
                for row in inventory_rows
            }
        )

    async def save(self, db: vbu.Database) -> None:
        """
        Save the user inventory object to the database.
        """

        async with db.transaction(commit_on_exit=False) as transaction:
            await transaction.execute_many(
                """
                INSERT INTO
                    user_inventory
                    (
                        user_id,
                        name,
                        amount
                    )
                VALUES
                    (
                        $1,
                        $2,
                        $3
                    )
                ON CONFLICT
                    (user_id, name)
                DO UPDATE
                SET
                    amount = excluded.amount
                """,
                [
                    (self.user_id, item.name, item.amount)
                    for item in self.items.values()
                ]
            )
            await transaction.commit()
