# src/context.py
from __future__ import annotations
from typing import Any, TypeVar, Generic
from keys import TypedKey

T = TypeVar("T")


class Context:
    """Тут создаем контекст, ассоциативный массив (dict в питоне) - изолируем библиотеку от потребителя через ключи."""
    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def set(self, key: TypedKey[T], value: T) -> None:
        if value is not None and not isinstance(value, key.value_type):
            raise TypeError(
                f"Value for '{key.name}' must be {key.value_type.__name__}, got {type(value).__name__}"
            )
        self._data[key.name] = value

    def get(self, key: TypedKey[T]) -> T:
        if key.name not in self._data:
            raise KeyError(f"Key '{key.name}' not found in context")
        value = self._data[key.name]
        # доп. защита, если положили не тот тип
        if value is not None and not isinstance(value, key.value_type):
            raise TypeError(
                f"Stored value for '{key.name}' expected {key.value_type.__name__}, got {type(value).__name__}"
            )
        return value

    def try_get(self, key: TypedKey[T]) -> tuple[bool, T | None]:
        value = self._data.get(key.name, None)
        if value is None:
            return False, None
        if not isinstance(value, key.value_type):
            return False, None
        return True, value

    def contains(self, key: TypedKey[Any]) -> bool:
        return key.name in self._data

    def remove(self, key: TypedKey[Any]) -> None:
        self._data.pop(key.name, None)
