from context import Context
from library_api import USER_ID, USER_NAME, REQUEST_ID, GreetUser, TraceRequest

def run_demo() -> None:
    ctx = Context()

    # тестовые даныные
    ctx.set(USER_ID, 101)
    ctx.set(USER_NAME, "Alice")
    ctx.set(REQUEST_ID, "№_1")

    # библиотека читает из контекста через свои ключи
    ops = [GreetUser(), TraceRequest()]
    for op in ops:
        print(op.execute(ctx))

if __name__ == "__main__":
    run_demo()
