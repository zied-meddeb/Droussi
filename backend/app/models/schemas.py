from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


Difficulty = Literal["easy", "medium", "hard"]
QuestionType = Literal["mcq", "open"]
ExportFormat = Literal["pdf", "docx"]
Language = Literal["en", "fr"]


class ExamSpec(BaseModel):
    difficulty: Difficulty
    question_types: list[QuestionType] = Field(min_length=1)
    num_exercises: int = Field(ge=1, le=20)
    total_points: int = Field(ge=1, le=5000)
    per_exercise_points: list[int]
    export_format: ExportFormat
    language: Language = "en"
    extra_instructions: Optional[str] = None

    @field_validator("per_exercise_points")
    @classmethod
    def _positive(cls, v: list[int]) -> list[int]:
        if any(p < 0 for p in v):
            raise ValueError("per_exercise_points must be non-negative")
        return v

    def validate_consistency(self) -> None:
        if len(self.per_exercise_points) != self.num_exercises:
            raise ValueError(
                "per_exercise_points length must equal num_exercises"
            )
        if sum(self.per_exercise_points) != self.total_points:
            raise ValueError("per_exercise_points must sum to total_points")


class RegisterDocumentRequest(BaseModel):
    filename: str
    storage_path: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None


class DocumentOut(BaseModel):
    id: str
    user_id: str
    filename: str
    storage_path: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: str


class Exercise(BaseModel):
    type: QuestionType
    question: str
    choices: Optional[list[str]] = None
    answer: str
    explanation: Optional[str] = None
    points: int


class ExamContent(BaseModel):
    title: str
    total_points: int
    exercises: list[Exercise]


class GenerateExamRequest(BaseModel):
    document_id: str
    document_ids: Optional[list[str]] = None
    spec: ExamSpec


class UpdateExamContentRequest(BaseModel):
    """User edits to a generated exam. total_points is recomputed server-side
    from the per-exercise points, so the client doesn't need to send it."""
    title: str = Field(min_length=1)
    exercises: list[Exercise] = Field(min_length=1)
    export_format: Optional[ExportFormat] = None

    @field_validator("exercises")
    @classmethod
    def _points_non_negative(cls, v: list[Exercise]) -> list[Exercise]:
        if any(ex.points < 0 for ex in v):
            raise ValueError("exercise points must be non-negative")
        return v

    def to_content(self) -> "ExamContent":
        return ExamContent(
            title=self.title,
            total_points=sum(ex.points for ex in self.exercises),
            exercises=self.exercises,
        )


class ExamOut(BaseModel):
    id: str
    user_id: str
    document_id: Optional[str] = None
    title: Optional[str] = None
    spec: ExamSpec | dict
    content: Optional[ExamContent | dict] = None
    export_format: Optional[ExportFormat] = None
    export_path: Optional[str] = None
    status: str
    created_at: str


class UsageOut(BaseModel):
    exams_used: int
    exams_limit: int
    remaining: int
    percent: float
    cost_usd_today: float
    usage_date: str
    resets_at: str


class MeOut(BaseModel):
    id: str
    email: Optional[str] = None
    is_admin: bool = False


class AdminUserUsage(BaseModel):
    user_id: str
    email: Optional[str] = None
    exams_today: int
    exams_total: int
    cost_usd_today: float
    cost_usd_total: float


class AdminOverviewOut(BaseModel):
    user_count: int
    exams_today: int
    exams_total: int
    cost_usd_today: float
    cost_usd_total: float
    per_user_exam_limit: int
    global_daily_cost_limit_usd: float
    # Live OpenRouter account credit status (None if it couldn't be fetched).
    account_usage_usd: Optional[float] = None
    account_limit_usd: Optional[float] = None
    account_remaining_usd: Optional[float] = None
    account_is_free_tier: Optional[bool] = None
    rankings: list[AdminUserUsage]
