# kanban_builder.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Iterable, Tuple
from datetime import date, timedelta
import itertools
import json
import inspect
import sys

# ============================================================
#                         UTIL / IDs
# ============================================================

class IdSeq:
    """Порождение строковых ID вида project_1, column_1, task_1."""
    _counters: Dict[str, itertools.count] = {}
    @classmethod
    def next(cls, kind: str) -> str:
        c = cls._counters.setdefault(kind, itertools.count(1))
        return f"{kind}_{next(c)}"

def caller_info(depth: int = 2) -> Tuple[str, int]:
    """Файл и строка вызова (для сообщений валидации)."""
    frame = inspect.stack()[depth]
    return (frame.filename, frame.lineno)

# ============================================================
#                     VALIDATION / ERRORS
# ============================================================

@dataclass
class ValidationError:
    message: str
    object_kind: str
    object_id: Optional[str]
    file: str
    line: int

    def __str__(self) -> str:
        oid = self.object_id or "-"
        return f"[{self.file}:{self.line}] {self.object_kind}({oid}): {self.message}"

class ValidationBag:
    def __init__(self) -> None:
        self._errors: List[ValidationError] = []

    def add(self, msg: str, kind: str, oid: Optional[str], file: str, line: int) -> None:
        self._errors.append(ValidationError(msg, kind, oid, file, line))

    def extend(self, others: Iterable[ValidationError]) -> None:
        self._errors.extend(others)

    @property
    def errors(self) -> List[ValidationError]:
        return list(self._errors)

    def raise_if_any(self) -> None:
        if self._errors:
            joined = "\n".join(str(e) for e in self._errors)
            raise ValueError(f"Validation failed with {len(self._errors)} error(s):\n{joined}")

# ============================================================
#                IMMUTABLE OUTPUT ("DB-like" storage)
# ============================================================

@dataclass(frozen=True)
class Project:
    id: str
    name: str
    created_at: date
    owner: Optional[str]
    column_ids: List[str]
    task_ids: List[str]

@dataclass(frozen=True)
class Column:
    id: str
    project_id: str
    name: str
    task_ids: List[str]

@dataclass(frozen=True)
class Task:
    id: str
    project_id: str
    column_id: str
    title: str
    description: Optional[str]
    assignee: Optional[str]
    priority: str               # Low | Normal | High | Critical
    due_date: Optional[date]
    created_at: date

@dataclass(frozen=True)
class BoardDB:
    projects: Dict[str, Project]
    columns: Dict[str, Column]
    tasks: Dict[str, Task]

    def to_json(self, *, indent: int = 2) -> str:
        def encode(obj):
            if isinstance(obj, (Project, Column, Task)):
                d = asdict(obj)
                # сериализуем даты в ISO
                for k, v in list(d.items()):
                    if isinstance(v, date):
                        d[k] = v.isoformat()
                return d
            if isinstance(obj, set):
                return list(obj)
            return obj
        data = {
            "projects": {k: encode(v) for k, v in self.projects.items()},
            "columns":  {k: encode(v) for k, v in self.columns.items()},
            "tasks":    {k: encode(v) for k, v in self.tasks.items()},
        }
        return json.dumps(data, indent=indent, ensure_ascii=False)

# ============================================================
#                     MUTABLE DRAFT MODELS
# ============================================================

@dataclass
class DraftProject:
    name: Optional[str] = None
    owner: Optional[str] = None
    created_at: date = field(default_factory=date.today)
    column_ids: List[str] = field(default_factory=list)
    task_ids: List[str] = field(default_factory=list)

@dataclass
class DraftColumn:
    name: Optional[str] = None
    task_ids: List[str] = field(default_factory=list)

@dataclass
class DraftTask:
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    priority: str = "Normal"        # Low | Normal | High | Critical
    due_date: Optional[date] = None
    created_at: date = field(default_factory=date.today)
    column_id: Optional[str] = None

# ============================================================
#                        BUILDERS (fluent)
#   Допы: fluent + делегаты + scope | high-level методы | усиленная валидация
# ============================================================

ALLOWED_PRIORITIES = {"Low", "Normal", "High", "Critical"}

class BaseBuilder:
    def __init__(self, vb: ValidationBag, kind: str, oid: Optional[str]) -> None:
        self._vb = vb
        self._kind = kind
        self._oid = oid
        self._file, self._line = caller_info(depth=3)  # место создания (внешний вызов)

    # Валидация базовых условий:
    def _non_empty(self, value: Optional[str], field_name: str, max_len: int = 200) -> Optional[str]:
        if value is None or not str(value).strip():
            self._vb.add(f"'{field_name}' must be non-empty", self._kind, self._oid, self._file, self._line)
            return None
        if len(value) > max_len:
            self._vb.add(f"'{field_name}' length must be <= {max_len}", self._kind, self._oid, self._file, self._line)
        return value

    def _in_set(self, value: Optional[str], allowed: set, field_name: str) -> Optional[str]:
        if value is None:
            self._vb.add(f"'{field_name}' must be set", self._kind, self._oid, self._file, self._line)
            return None
        if value not in allowed:
            self._vb.add(f"'{field_name}' must be in {sorted(allowed)} (got '{value}')", self._kind, self._oid, self._file, self._line)
        return value

    def _due_not_past(self, d: Optional[date], allow_past: bool) -> None:
        if d is None: return
        if (not allow_past) and d < date.today():
            self._vb.add("due_date cannot be in the past", self._kind, self._oid, self._file, self._line)

class ProjectBuilder(BaseBuilder):
    def __init__(self) -> None:
        super().__init__(ValidationBag(), "Project", None)
        self._pid: str = IdSeq.next("project")
        self._draft = DraftProject()
        self._columns: Dict[str, DraftColumn] = {}
        self._tasks: Dict[str, DraftTask] = {}
        self._allow_past_due: bool = False

    # ---------- fluent setters ----------
    def name(self, value: str) -> "ProjectBuilder":
        self._draft.name = value
        # базовая проверка прямо при установке:
        self._non_empty(value, "project.name")
        return self

    def owner(self, value: str) -> "ProjectBuilder":
        self._draft.owner = value.strip()
        return self

    def allow_past_due(self, value: bool = True) -> "ProjectBuilder":
        self._allow_past_due = bool(value)
        return self

    # ---------- children factories ----------
    def column(self, name: str, configure: Optional[Callable[[ColumnBuilder], None]] = None) -> "ColumnBuilder":
        cid = IdSeq.next("column")
        self._columns[cid] = DraftColumn()
        self._draft.column_ids.append(cid)
        builder = ColumnBuilder(self._vb, cid, self._pid, self, self._columns[cid]).name(name)
        if configure:
            configure(builder)
        return builder

    def task(self, title: str, configure: Optional[Callable[[TaskBuilder], None]] = None, *, column: Optional[str] = None) -> "TaskBuilder":
        """Если column не указан — кладём в первую колонку проекта (если есть)."""
        tid = IdSeq.next("task")
        self._tasks[tid] = DraftTask()
        self._draft.task_ids.append(tid)
        builder = TaskBuilder(self._vb, tid, self._pid, self, self._tasks[tid])
        builder.title(title)
        if column is None and self._draft.column_ids:
            builder.in_column(self._draft.column_ids[0])   # первая колонка
        elif column is not None:
            builder.in_column(column)
        if configure:
            configure(builder)
        return builder

    # ---------- scope ----------
    def scope(self) -> "ProjectScope":
        return ProjectScope(self)

    # ---------- build ----------
    def build(self) -> BoardDB:
        # финальные проверки
        if not self._draft.name:
            self._non_empty(self._draft.name, "project.name")
        if not self._draft.column_ids:
            self._vb.add("project must have at least one column", "Project", self._pid, *caller_info(depth=2))

        # уникальность имён колонок
        names = [self._columns[cid].name for cid in self._draft.column_ids]
        duplicates = {n for n in names if n is not None and names.count(n) > 1}
        for n in duplicates:
            self._vb.add(f"duplicate column name '{n}'", "Project", self._pid, *caller_info(depth=2))

        # построение immutable и финальная валидация задач/ссылок
        projects: Dict[str, Project] = {}
        columns: Dict[str, Column] = {}
        tasks: Dict[str, Task] = {}

        # колонки
        for cid in self._draft.column_ids:
            draft = self._columns[cid]
            if not self._non_empty(draft.name, f"column[{cid}].name"):
                # имя пустое — но продолжим строить, чтобы собрать все ошибки
                col_name = draft.name or f"<invalid:{cid}>"
            else:
                col_name = draft.name or ""
            columns[cid] = Column(id=cid, project_id=self._pid, name=col_name, task_ids=[])

        # задачи
        for tid in self._draft.task_ids:
            d = self._tasks[tid]
            self._non_empty(d.title, f"task[{tid}].title")
            self._in_set(d.priority, ALLOWED_PRIORITIES, f"task[{tid}].priority")
            self._due_not_past(d.due_date, allow_past=self._allow_past_due)

            # проверка и нормализация column_id (по ID или по имени)
            col_id = d.column_id
            if col_id and col_id in columns:
                pass
            elif col_id and col_id not in columns:
                # возможно это имя колонки
                found = [cid for cid, col in columns.items() if col.name == col_id]
                if len(found) == 1:
                    col_id = found[0]
                else:
                    self._vb.add(f"unknown column '{col_id}' for task", "Task", tid, *caller_info(depth=2))
                    # создадим «валидный» placeholder, чтобы не ронять сборку
                    if self._draft.column_ids:
                        col_id = self._draft.column_ids[0]
            elif not col_id:
                # никуда не положили — если есть первая колонка, используем её
                if self._draft.column_ids:
                    col_id = self._draft.column_ids[0]
                else:
                    self._vb.add("task has no column and project has no columns", "Task", tid, *caller_info(depth=2))
                    # оставим None — но продолжим

            # соберём immutable таск
            t = Task(
                id=tid,
                project_id=self._pid,
                column_id=col_id or "unknown_column",
                title=d.title or "",
                description=d.description,
                assignee=d.assignee,
                priority=d.priority if d.priority in ALLOWED_PRIORITIES else "Normal",
                due_date=d.due_date,
                created_at=d.created_at,
            )
            tasks[tid] = t
            if col_id in columns:
                columns[col_id].task_ids.append(tid)

        # проект
        p = Project(
            id=self._pid,
            name=self._draft.name or "",
            created_at=self._draft.created_at,
            owner=self._draft.owner,
            column_ids=list(self._draft.column_ids),
            task_ids=list(self._draft.task_ids),
        )
        projects[self._pid] = p

        # финальный выброс, если есть ошибки
        self._vb.raise_if_any()
        return BoardDB(projects=projects, columns=columns, tasks=tasks)

class ColumnBuilder(BaseBuilder):
    def __init__(self, vb: ValidationBag, column_id: str, project_id: str, root: ProjectBuilder, draft: DraftColumn) -> None:
        super().__init__(vb, "Column", column_id)
        self._cid = column_id
        self._pid = project_id
        self._root = root
        self._draft = draft

    # fluent setters
    def name(self, value: str) -> "ColumnBuilder":
        self._draft.name = value
        self._non_empty(value, "column.name")
        return self

    # high-level (комбо) — просто читабельный ярлык
    def as_backlog(self) -> "ColumnBuilder":
        # никакой спец-логики — это «семантическая метка»
        if self._draft.name and self._draft.name.lower() != "backlog":
            # мягкое предупреждение не как ошибка: оставим как есть
            pass
        return self


class TaskBuilder(BaseBuilder):
    def __init__(self, vb: ValidationBag, task_id: str, project_id: str, root: ProjectBuilder, draft: DraftTask) -> None:
        super().__init__(vb, "Task", task_id)
        self._tid = task_id
        self._pid = project_id
        self._root = root
        self._draft = draft

    # fluent setters
    def title(self, value: str) -> "TaskBuilder":
        self._draft.title = value
        self._non_empty(value, "task.title")
        return self

    def description(self, value: str) -> "TaskBuilder":
        self._draft.description = value
        return self

    def assignee(self, value: str) -> "TaskBuilder":
        self._draft.assignee = value.strip()
        return self

    def priority(self, value: str) -> "TaskBuilder":
        self._draft.priority = value
        self._in_set(value, ALLOWED_PRIORITIES, "task.priority")
        return self

    def due(self, value: date) -> "TaskBuilder":
        self._draft.due_date = value
        self._due_not_past(value, allow_past=self._root._allow_past_due)
        return self

    def in_column(self, column_name_or_id: str) -> "TaskBuilder":
        self._draft.column_id = column_name_or_id
        return self

    # high-level (комбо)
    def mark_urgent(self) -> "TaskBuilder":
        return self.priority("High").due(date.today() + timedelta(days=2))

    def assign_and_due(self, user: str, d: date) -> "TaskBuilder":
        return self.assignee(user).due(d)

    def copy_from(self, other: "TaskBuilder", fields: Tuple[str, ...] = ("title", "description", "assignee", "priority", "due_date")) -> "TaskBuilder":
        for f in fields:
            if f == "title" and other._draft.title is not None:
                self.title(other._draft.title)
            elif f == "description" and other._draft.description is not None:
                self.description(other._draft.description)
            elif f == "assignee" and other._draft.assignee is not None:
                self.assignee(other._draft.assignee)
            elif f == "priority" and other._draft.priority:
                self.priority(other._draft.priority)
            elif f == "due_date" and other._draft.due_date is not None:
                self.due(other._draft.due_date)
        return self

    # делегат конфигурации
    def configure(self, fn: Callable[["TaskBuilder"], None]) -> "TaskBuilder":
        fn(self)
        return self

# ============================================================
#                             SCOPE
# ============================================================

class ProjectScope:
    """Паттерн scope: дефолты для ВСЕХ задач, создаваемых внутри with-блока."""
    def __init__(self, root: ProjectBuilder) -> None:
        self._root = root
        self._default_assignee: Optional[str] = None
        self._default_priority: Optional[str] = None
        self._default_due: Optional[date] = None

    # fluent для дефолтов
    def assignee(self, value: str) -> "ProjectScope":
        self._default_assignee = value.strip()
        return self

    def priority(self, value: str) -> "ProjectScope":
        self._default_priority = value
        # мягкая базовая проверка при установке:
        if value not in ALLOWED_PRIORITIES:
            self._root._vb.add(f"default priority must be in {sorted(ALLOWED_PRIORITIES)} (got '{value}')",
                               "Scope", None, *caller_info(depth=2))
        return self

    def due(self, value: date) -> "ProjectScope":
        self._default_due = value
        if (not self._root._allow_past_due) and value < date.today():
            self._root._vb.add("default due_date cannot be in the past", "Scope", None, *caller_info(depth=2))
        return self

    # фабрика задач, учитывающая дефолты
    def task(self, title: str, configure: Optional[Callable[[TaskBuilder], None]] = None, *, column: Optional[str] = None) -> TaskBuilder:
        tb = self._root.task(title, None, column=column)
        if self._default_assignee: tb.assignee(self._default_assignee)
        if self._default_priority: tb.priority(self._default_priority)
        if self._default_due: tb.due(self._default_due)
        if configure: configure(tb)
        return tb

    # контекстный менеджер (чтобы красиво писать with project.scope() as s:)
    def __enter__(self) -> "ProjectScope":
        return self
    def __exit__(self, exc_type, exc, tb) -> None:
        return None

# ============================================================
#                           DEMO
# ============================================================

def demo() -> None:
    board = (ProjectBuilder()
             .name("Sprint 17")
             .owner("PM"))

    board.column("Backlog", lambda c: c.as_backlog())
    board.column("In Progress")
    board.column("Done")

    with board.scope().assignee("Alina").priority("High") as s:
        s.task("Login bug", lambda t: t.mark_urgent()
               .description("Wrong redirect after auth"))
        s.task("Payment refactor", lambda t: t.description("Split module")
               .due(date.today() + timedelta(days=3)))

    # переиспользуем настройки через assign_and_due
    board.task("Hotfix prod", lambda t: t.assign_and_due("Alina", date.today() + timedelta(days=1))
               .in_column("In Progress"))

    # продемонстрируем copy_from
    tmpl = board.task("Template task", lambda t: t.description("Base desc").priority("Low")
                      ).in_column("Backlog")
    board.task("Cloned from template", lambda t: t.copy_from(tmpl)
               .in_column("In Progress"))

    # Задача вне scope, со своей конфигурацией
    board.task("Release notes", lambda t: t.assignee("PM").priority("Normal").description("Prepare RN")).in_column("Done")


    # покажем результат или ошибки
    try:
        db = board.build()
        print(db.to_json(indent=2))
    except ValueError as e:
        print(str(e), file=sys.stderr)

if __name__ == "__main__":
    demo()
