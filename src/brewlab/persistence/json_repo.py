"""JSON file-based persistence repository (Phase 7).

Concrete implementation of ``Repository[T]``. Each item is serialized to a
single JSON file named by its id, stored in a directory. Supports dataclasses,
``pint.Quantity``, and ``datetime`` via a small JSONable transformer so that
domain objects round-trip without losing units or types.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from brewlab.persistence.repository import Repository, T
from brewlab.units import Quantity, ureg

_QUANTITY_MARKER = "__quantity__"
_DATETIME_MARKER = "__datetime__"
_DATACLASS_MARKER = "__dataclass__"
_MODULE_MARKER = "__module__"
_ID_FIELD = "id"


def to_jsonable(obj: Any) -> Any:
    """Convert a domain object to JSON-native form."""
    if isinstance(obj, Quantity):
        return {
            _QUANTITY_MARKER: True,
            "magnitude": float(obj.magnitude),
            "units": str(obj.units),
        }
    if isinstance(obj, datetime):
        return {_DATETIME_MARKER: True, "iso": obj.isoformat()}
    if is_dataclass(obj) and not isinstance(obj, type):
        cls = type(obj)
        data: dict[str, Any] = {
            _DATACLASS_MARKER: cls.__name__,
            _MODULE_MARKER: cls.__module__,
        }
        for f in fields(cls):
            data[f.name] = to_jsonable(getattr(obj, f.name))
        return data
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    raise TypeError(f"Not JSON serializable: {type(obj)!r}")


def from_jsonable(obj: Any) -> Any:
    """Reconstruct a domain object from JSON-native form."""
    if isinstance(obj, dict):
        if _QUANTITY_MARKER in obj:
            return ureg.Quantity(obj["magnitude"], obj["units"])
        if _DATETIME_MARKER in obj:
            return datetime.fromisoformat(obj["iso"])
        if _DATACLASS_MARKER in obj:
            cls_name = obj[_DATACLASS_MARKER]
            module_name = obj[_MODULE_MARKER]
            module = import_module(module_name)
            cls = getattr(module, cls_name)
            field_names = {f.name for f in fields(cls)}
            kwargs = {
                k: from_jsonable(v)
                for k, v in obj.items()
                if k not in (_DATACLASS_MARKER, _MODULE_MARKER) and k in field_names
            }
            return cls(**kwargs)
        return {k: from_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [from_jsonable(v) for v in obj]
    return obj


def _item_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("id") or item.get("name") or uuid.uuid4().hex)
    return str(getattr(item, "id", None) or getattr(item, "name", None) or uuid.uuid4().hex)


@dataclass
class JsonRepository(Repository[T]):
    """File-based JSON repository storing one item per ``{id}.json`` file."""

    directory: Path

    def __post_init__(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, id: str) -> Path:
        return self.directory / f"{id}.json"

    def add(self, item: T) -> None:
        item_id = _item_id(item)
        payload = to_jsonable(item)
        if isinstance(payload, dict) and _ID_FIELD not in payload:
            payload[_ID_FIELD] = item_id
        path = self._path(item_id)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, id: str) -> T | None:
        path = self._path(id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return cast(T | None, from_jsonable(data))

    def list(self) -> list[T]:
        items: list[T] = []
        for path in sorted(self.directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append(cast(T, from_jsonable(data)))
        return items


__all__ = ["JsonRepository", "to_jsonable", "from_jsonable"]
