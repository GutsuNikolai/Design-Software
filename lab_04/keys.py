# src/keys.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, TypeVar, Dict, Type, Any

T = TypeVar("T")


@dataclass(frozen=True)
class TypedKey(Generic[T]):
    """Ключ с ожидаемым типом значения"""
    name: str
    value_type: Type[T]


class KeyRegistry:
    """Глобальный реестр ключей для предотвращения коллизий между проектами/библиотеками."""
    _registry: Dict[str, TypedKey[Any]] = {}

    @classmethod
    def register(cls, name: str, value_type: Type[T]) -> TypedKey[T]:
        if name in cls._registry:
            existing = cls._registry[name]
            raise ValueError(
                f"Key '{name}' already registered with type {existing.value_type.__name__}"
            )
        key = TypedKey[T](name=name, value_type=value_type)  # type: ignore[arg-type]
        cls._registry[name] = key  # keep as Any internally
        return key

    @classmethod
    def get(cls, name: str) -> TypedKey[Any] | None:
        return cls._registry.get(name)

    @classmethod
    def clear_for_tests(cls) -> None:
        cls._registry.clear()
