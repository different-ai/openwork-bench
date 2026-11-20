"""Task schema. A task is a folder with task.yaml, world.yaml, reference.yaml and workspace/."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CATEGORIES: dict[str, str] = {
    "research": "Research & analysis",
    "documents": "Documents & writing",
    "spreadsheets": "Spreadsheets & data",
    "communication": "Communication & coordination",
    "operations": "Multi-app operations",
    "projects": "Long-horizon projects",
}

Category = Literal["research", "documents", "spreadsheets", "communication", "operations", "projects"]
Split = Literal["public-dev", "public-test", "private"]


class Occupation(BaseModel):
    soc: str = Field(description="US SOC 2018 code, e.g. 13-1023")
    title: str


class Budgets(BaseModel):
    max_steps: int = 40
    max_tokens: int = 400_000
    timeout_s: int = 900


class ExpertBaseline(BaseModel):
    minutes: float = Field(description="Time a competent professional needs for the task")
    hourly_rate_usd: float = Field(description="Typical fully loaded hourly rate for the occupation")
    source: str = "author-estimate"

    @property
    def cost_usd(self) -> float:
        return round(self.minutes / 60.0 * self.hourly_rate_usd, 2)


class Check(BaseModel):
    """A deterministic check on the final world state. Extra keys are the check's parameters."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    weight: float = 1.0
    critical: bool = False
    description: str | None = None

    @property
    def params(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class RubricItem(BaseModel):
    id: str
    text: str
    weight: float = 1.0
    critical: bool = False


class Allow(BaseModel):
    """Exceptions to the global safety rules for this task."""

    deletes: list[str] = Field(default_factory=list, description="Services where deleting is part of the job")
    external_recipients: list[str] = Field(default_factory=list)


class Provenance(BaseModel):
    author: str
    created: str
    license: str = "CC-BY-4.0"
    notes: str | None = None


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,80}$")
    version: int = 1
    title: str
    category: Category
    occupation: Occupation
    difficulty: Literal["easy", "medium", "hard"]
    horizon: Literal["single", "multi-step", "project"]
    split: Split
    brief: str
    budgets: Budgets = Field(default_factory=Budgets)
    expert_baseline: ExpertBaseline
    checks: list[Check]
    safety: list[Check] = Field(default_factory=list)
    rubric: list[RubricItem] = Field(default_factory=list)
    allow: Allow = Field(default_factory=Allow)
    tags: list[str] = Field(default_factory=list)
    provenance: Provenance
    canary: str
