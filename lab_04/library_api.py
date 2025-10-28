from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from context import Context
from keys import KeyRegistry

# Регистрируем ключи централизованно
USER_ID = KeyRegistry.register("user.id", int)
USER_NAME = KeyRegistry.register("user.name", str)
REQUEST_ID = KeyRegistry.register("request.id", str)


@dataclass
class UserInfo:
    user_id: int
    name: str


class Operation(Protocol):
    """Контракт операции, которая работает на данных из контекста."""
    def execute(self, ctx: Context) -> str: ...


@dataclass
class GreetUser(Operation):
    def execute(self, ctx: Context) -> str:
        uid = ctx.get(USER_ID)
        name = ctx.get(USER_NAME)
        return f"Hello, {name} (id={uid})"


@dataclass
class TraceRequest(Operation):
    def execute(self, ctx: Context) -> str:
        rid = ctx.get(REQUEST_ID)
        return f"[trace] request={rid}"
