from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any

@dataclass
class TaskAnalysis:
    needs_carpenter: bool
    sqm: float | None = None
    rooms: int | None = None
    estimated_minutes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict[str, Any] | None) -> "TaskAnalysis | None":
        if not d:
            return None
        return TaskAnalysis(
            needs_carpenter=bool(d.get("needs_carpenter")),
            sqm=d.get("sqm"),
            rooms=d.get("rooms"),
            estimated_minutes=int(d.get("estimated_minutes") or 0),
        )

@dataclass
class PlanBlock:
    label: str
    start: str  # ISO string
    end: str    # ISO string

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class TaskPlan:
    painter_id: int
    bucket: str
    blocks: list[PlanBlock] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "painter_id": self.painter_id,
            "bucket": self.bucket,
            "blocks": [b.to_dict() for b in self.blocks],
        }

@dataclass
class TaskRecord:
    task_id: str
    source_message_id: str
    received_at: str
    from_address: str | None
    subject: str
    address: str
    pdf_paths: list[str]
    text_raw: str
    status: str = "NEW"
    analysis: TaskAnalysis | None = None
    plan: TaskPlan | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # asdict kan håndtere dataclasses, men vi vil have pæn struktur:
        d["analysis"] = self.analysis.to_dict() if self.analysis else None
        d["plan"] = self.plan.to_dict() if self.plan else None
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TaskRecord":
        analysis = TaskAnalysis.from_dict(d.get("analysis"))
        plan_d = d.get("plan")
        plan = None
        if plan_d:
            blocks = [PlanBlock(**b) for b in plan_d.get("blocks", [])]
            plan = TaskPlan(
                painter_id=int(plan_d.get("painter_id")),
                bucket=str(plan_d.get("bucket")),
                blocks=blocks,
            )

        return TaskRecord(
            task_id=str(d["task_id"]),
            source_message_id=str(d["source_message_id"]),
            received_at=str(d.get("received_at", "")),
            from_address=d.get("from") or d.get("from_address"),
            subject=str(d.get("subject", "")),
            address=str(d.get("address", "")),
            pdf_paths=list(d.get("pdf_paths", [])),
            text_raw=str(d.get("text_raw", "")),
            status=str(d.get("status", "NEW")),
            analysis=analysis,
            plan=plan,
        )
