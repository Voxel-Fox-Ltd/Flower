from __future__ import annotations

from typing import TypedDict, Optional


class ArtistInfo(TypedDict):
    website: Optional[str]
    fiverr: Optional[str]
    instagram: Optional[str]
    discord: Optional[int]
