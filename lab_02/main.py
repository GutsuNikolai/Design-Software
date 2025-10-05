# academic_pipeline.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, TypeVar, Generic, List, Dict, Any, Optional, runtime_checkable
from io import StringIO
import sys
import hashlib


# Generics
TContext = TypeVar("TContext")

@runtime_checkable
class Stoppable(Protocol):
    is_done: bool  # флаг для ранней остановки (Chain of Responsibility)

class PipelineStep(Protocol, Generic[TContext]):
    def execute(self, context: TContext) -> None: ...
    def introspect(self, sink: StringIO) -> None: ...

# Первый пайплайн
class Pipeline(Generic[TContext]):
    def __init__(self) -> None:
        self._steps: List[PipelineStep[TContext]] = []

    # конструктор + модификации (higl-level)
    def add(self, step: PipelineStep[TContext]) -> "Pipeline[TContext]":
        self._steps.append(step)
        return self

    def replace_first_instance(self, type_to_replace: type, new_step: PipelineStep[TContext]) -> bool:
        for i, s in enumerate(self._steps):
            if isinstance(s, type_to_replace):
                self._steps[i] = new_step
                return True
        return False

    def replace_all(self, type_to_replace: type, new_step: PipelineStep[TContext]) -> int:
        cnt = 0
        for i, s in enumerate(self._steps):
            if isinstance(s, type_to_replace):
                self._steps[i] = new_step
                cnt += 1
        return cnt

    def move_to(self, type_to_move: type, index: int) -> bool:
        for i, s in enumerate(self._steps):
            if isinstance(s, type_to_move):
                step = self._steps.pop(i)
                index = max(0, min(index, len(self._steps)))
                self._steps.insert(index, step)
                return True
        return False

    # выполнение / интроспекция
    def execute(self, context: TContext) -> None:
        for step in list(self._steps):
            step.execute(context)
            if isinstance(context, Stoppable) and getattr(context, "is_done", False):
                break

    def print_all_steps(self, writer=sys.stdout) -> None:
        sink = StringIO()
        for step in self._steps:
            step.introspect(sink)
        print(sink.getvalue().rstrip(), file=writer)


#  ПАЙПЛАЙН A: ПРОВЕРКА РАБОТЫ


@dataclass
class SubmissionContext:
    student_id: str
    course_id: str
    content: str
    meta: Dict[str, Any] = field(default_factory=dict)

    is_valid: bool = False
    similarity_score: float = 0.0  # 0..1 (псевдо-плагиат)
    grade: float = 0.0
    flags: List[str] = field(default_factory=list)
    is_done: bool = False  # Chain of Responsibility

_seen_hashes_per_course: Dict[str, set] = {}

class ValidateSubmission(PipelineStep[SubmissionContext]):
    # Проверка длины текста
    def __init__(self, min_len: int = 100) -> None:
        self.min_len = min_len
    def execute(self, ctx: SubmissionContext) -> None:
        ok = len(ctx.content.strip()) >= self.min_len
        ctx.is_valid = ok
        if not ok:
            ctx.flags.append(f"too_short<{self.min_len}")
            ctx.is_done = True
    def introspect(self, sink: StringIO) -> None:
        sink.write(f"- ValidateSubmission(min_len={self.min_len})\n")

class DeduplicateSubmission(PipelineStep[SubmissionContext]):
    # Лоха нашел? Проверка на плагиат
    def execute(self, ctx: SubmissionContext) -> None:
        h = hashlib.sha256(ctx.content.encode("utf-8")).hexdigest()[:16]
        seen = _seen_hashes_per_course.setdefault(ctx.course_id, set())
        if h in seen:
            ctx.flags.append("duplicate_submission")
            ctx.is_done = True
        else:
            seen.add(h)
    def introspect(self, sink: StringIO) -> None:
        sink.write("- DeduplicateSubmission\n")

class SimilarityHeuristic(PipelineStep[SubmissionContext]):
    # Банальная проверка на "воду в работе" (процент уникальных слов)
    def execute(self, ctx: SubmissionContext) -> None:
        words = [w.lower() for w in ctx.content.split()]
        uniq = len(set(words))
        total = max(1, len(words))
        # примитивная метрика «однообразности» текста
        ctx.similarity_score = round(1.0 - (uniq / total), 3)
        if ctx.similarity_score >= 0.6:
            ctx.flags.append("high_similarity")
    def introspect(self, sink: StringIO) -> None:
        sink.write("- SimilarityHeuristic\n")

class RejectIfTooSimilar(PipelineStep[SubmissionContext]):
    def __init__(self, threshold: float = 0.7) -> None:
        self.threshold = threshold
    def execute(self, ctx: SubmissionContext) -> None:
        if ctx.similarity_score >= self.threshold:
            ctx.is_done = True
            ctx.grade = 0.0
            ctx.flags.append("rejected_by_similarity")
    def introspect(self, sink: StringIO) -> None:
        sink.write(f"- RejectIfTooSimilar(th={self.threshold})\n")

class ComputeGrade(PipelineStep[SubmissionContext]):
    # Проверка работы и начиление баллов
    def __init__(self, base: float = 6.0, structure_bonus: float = 2.0, refs_bonus: float = 2.0) -> None:
        self.base = base
        self.structure_bonus = structure_bonus
        self.refs_bonus = refs_bonus
    def execute(self, ctx: SubmissionContext) -> None:
        grade = self.base
        text = ctx.content.lower()
        if any(h in text for h in ("# ", "introduction", "conclusion", "summary")):
            grade += self.structure_bonus
        if "http://" in text or "https://" in text or "doi:" in text:
            grade += self.refs_bonus
        ctx.grade = min(10.0, grade)
    def introspect(self, sink: StringIO) -> None:
        sink.write(f"- ComputeGrade(base={self.base}, structure_bonus={self.structure_bonus}, refs_bonus={self.refs_bonus})\n")

class PrintSubmission(PipelineStep[SubmissionContext]):
    #Синглтон для печати результата
    _instance: Optional["PrintSubmission"] = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def execute(self, ctx: SubmissionContext) -> None:
        print(f"Submission(student={ctx.student_id}, course={ctx.course_id}, "
              f"valid={ctx.is_valid}, sim={ctx.similarity_score}, grade={ctx.grade:.1f}, flags={ctx.flags})")
    def introspect(self, sink: StringIO) -> None:
        sink.write("- PrintSubmission\n")


#  ПАЙПЛАЙН 2 : ВЫДАЧА СЕРТИФИКАТА

@dataclass
class CertificateContext:
    student_id: str
    earned_credits: int
    required_credits: int
    gpa: float
    certificate: Optional[str] = None
    is_done: bool = False

class CheckCredits(PipelineStep[CertificateContext]):
    def execute(self, ctx: CertificateContext) -> None:
        if ctx.earned_credits < ctx.required_credits:
            ctx.certificate = None
            ctx.is_done = True
    def introspect(self, sink: StringIO) -> None:
        sink.write("- CheckCredits\n")

class DetermineHonors(PipelineStep[CertificateContext]):
    # Гралация уровня диплома по баллу
    def execute(self, ctx: CertificateContext) -> None:
        if ctx.gpa >= 9.5:
            ctx.certificate = "МаШиНа"
        elif ctx.gpa >= 9.0:
            ctx.certificate = "Есть чему учиться"
        elif ctx.gpa >= 8.5:
            ctx.certificate = "Могло быть и хуже"
        else:
            ctx.certificate = "Certificate of Completion"
    def introspect(self, sink: StringIO) -> None:
        sink.write("- DetermineHonors\n")

class PrintCertificate(PipelineStep[CertificateContext]):
    _instance: Optional["PrintCertificate"] = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def execute(self, ctx: CertificateContext) -> None:
        status = ctx.certificate or "Not eligible (insufficient credits)"
        print(f"Certificate(student={ctx.student_id}, credits={ctx.earned_credits}/{ctx.required_credits}, gpa={ctx.gpa:.2f}, result='{status}')")
    def introspect(self, sink: StringIO) -> None:
        sink.write("- PrintCertificate\n")


#  ДЕМО

def demo_submission_pipeline() -> None:
    print("SUBMISSION PIPELINE")
    pipeline = Pipeline[SubmissionContext]()
    pipeline.add(ValidateSubmission(min_len=80)) \
            .add(DeduplicateSubmission()) \
            .add(SimilarityHeuristic()) \
            .add(RejectIfTooSimilar(threshold=0.7)) \
            .add(ComputeGrade(base=6.0, structure_bonus=2.0, refs_bonus=2.0)) \
            .add(PrintSubmission())

    #pipeline.replace_first_instance(ComputeGrade, ComputeGrade(base=2.0, structure_bonus=2.0, refs_bonus=2.0))
    #pipeline.replace_all(RejectIfTooSimilar, RejectIfTooSimilar(threshold=1))
    # pipeline.move_to(PrintSubmission, 0)

    pipeline.print_all_steps()

    cases = [
        SubmissionContext(student_id="s1", course_id="cAI", content="Introduction... conclusion... https:// references... " + "some text with normal structure"), # нормальная работа
        SubmissionContext(student_id="s2", course_id="cAI", content="random text" * 20),                      # слишком много повторов
        SubmissionContext(student_id="s3", course_id="cAI", content="Introduction... conclusion... https:// references... " + "some text with normal structure"),  # дубликат первого
        SubmissionContext(student_id="s4", course_id="cAI", content="too short"),                       # Слишком короткий текст
    ]
    for ctx in cases:
        pipeline.execute(ctx)
    print()


def demo_certificate_pipeline() -> None:
    print("CERTIFICATE PIPELINE")
    pipeline = Pipeline[CertificateContext]()
    pipeline.add(CheckCredits()) \
            .add(DetermineHonors()) \
            .add(PrintCertificate())

    pipeline.print_all_steps()

    cases = [
        CertificateContext(student_id="s1", earned_credits=180, required_credits=180, gpa=9.7),     # норм
        CertificateContext(student_id="s2", earned_credits=175, required_credits=180, gpa=9.8),     # не хватает кредитов
        CertificateContext(student_id="s3", earned_credits=180, required_credits=180, gpa=8.9),     # норм
    ]
    for ctx in cases:
        pipeline.execute(ctx)
    print()

if __name__ == "__main__":
    demo_submission_pipeline()
    demo_certificate_pipeline()
