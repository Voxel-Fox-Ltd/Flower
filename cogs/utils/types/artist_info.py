from __future__ import annotations

from typing import TypedDict, Optional


__all__ = (
    'ArtistInfo',
)


class ArtistInfo(TypedDict):
    website: Optional[str]
    fiverr: Optional[str]
    instagram: Optional[str]
    discord: Optional[int]
