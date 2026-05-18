from __future__ import annotations

from dataclasses import dataclass

from database.db import DEFAULT_ESTABLISHMENT_ID, DEFAULT_ESTABLISHMENT_NAME, DEFAULT_ESTABLISHMENT_SLUG


@dataclass(frozen=True)
class EstablishmentContext:
    id: int
    name: str
    slug: str


DEFAULT_ESTABLISHMENT_CONTEXT = EstablishmentContext(
    id=DEFAULT_ESTABLISHMENT_ID,
    name=DEFAULT_ESTABLISHMENT_NAME,
    slug=DEFAULT_ESTABLISHMENT_SLUG,
)

ALL_ESTABLISHMENTS_ID = -1


def default_establishment_id() -> int:
    return DEFAULT_ESTABLISHMENT_CONTEXT.id


def is_all_establishments_scope(establishment_id: int | None) -> bool:
    return establishment_id == ALL_ESTABLISHMENTS_ID
