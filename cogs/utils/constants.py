from datetime import timedelta


__all__ = (
    'NON_SUBSCRIBER_PLANT_CAP',
    'HARD_PLANT_CAP',
    'REVIVAL_TOKEN_PRICE',
    'REFRESH_TOKEN_PRICE',
    'IMMORTAL_PLANT_JUICE_PRICE',
    'DEATH_TIMEOUT',
    'WATER_COOLDOWN',
    'NOTIFICATION_TIME',
    'GUEST_WATER_COOLDOWN',
)


NON_SUBSCRIBER_PLANT_CAP = 5
"""The maximum number of plants a non-subscriber can have."""
HARD_PLANT_CAP = 10
"""The maximum number of plants a user can have."""

REVIVAL_TOKEN_PRICE = 3_000
"""The price of a revival token."""
REFRESH_TOKEN_PRICE = 10_000
"""The price of a refresh token."""
IMMORTAL_PLANT_JUICE_PRICE = 1_000
"""The price of a bottle of immortal plant juice."""

DEATH_TIMEOUT = timedelta(
    days=3,
)
"""The amount of time a plant can go without being watered before it dies."""

WATER_COOLDOWN = timedelta(
    minutes=15,
)
"""The amount of time a plant has to wait before it can be watered again."""

NOTIFICATION_TIME = timedelta(
    hours=1,
)
"""The amount of time before a plant dies that a notification will be sent."""

GUEST_WATER_COOLDOWN = timedelta(
    minutes=60,
)
"""The amount of time a guest has to wait wait before they can water a plant again."""
