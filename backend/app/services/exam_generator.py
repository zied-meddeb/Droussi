import asyncio
import json

from fastapi.concurrency import run_in_threadpool

from ..models.schemas import ExamContent, ExamSpec
from ..prompts.exam_prompt import SYSTEM_PROMPT, build_user_prompt
from . import llm
from . import usage as usage_service


def _extract_json(text: str) -> str:
    """OpenRouter free models sometimes wrap JSON in markdown fences — strip them.

    Uses plain string operations rather than a regex: the input is untrusted LLM
    output, and an ambiguous regex here would be vulnerable to catastrophic
    backtracking (ReDoS).
    """
    text = text.strip()
    if text.startswith("```"):
        inner = text[3:]
        if inner[:4].lower() == "json":
            inner = inner[4:]
        if inner.endswith("```"):
            inner = inner[:-3]
        text = inner.strip()
    # find first { ... last }
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        return text[first : last + 1]
    return text


def _fix_points(content: ExamContent, spec: ExamSpec) -> ExamContent:
    """Force per-exercise points to match the requested distribution, in case the
    model drifted. Also re-clamps total_points and exercise count to spec where
    safe (truncating extras / padding with the last exercise duplicated if missing)."""
    exercises = list(content.exercises)

    # Truncate if too many
    if len(exercises) > spec.num_exercises:
        exercises = exercises[: spec.num_exercises]

    # If too few, we keep what we have — caller will treat as soft failure.
    for i, ex in enumerate(exercises):
        if i < len(spec.per_exercise_points):
            ex.points = spec.per_exercise_points[i]

    content.exercises = exercises
    content.total_points = spec.total_points
    return content


# Transient LLM failures (all models rate-limited / network blips) are retried
# with exponential backoff before giving up.
_LLM_MAX_ATTEMPTS = 2
_LLM_BACKOFF_BASE_SECONDS = 1.5


async def _chat_with_backoff(messages: list[dict[str, str]]):
    """Call the LLM, retrying transient RuntimeErrors with exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(_LLM_MAX_ATTEMPTS):
        try:
            return await llm.chat(
                messages, response_format_json=True, max_tokens=2500
            )
        except RuntimeError as e:
            last_error = e
            if attempt + 1 < _LLM_MAX_ATTEMPTS:
                await asyncio.sleep(_LLM_BACKOFF_BASE_SECONDS * (2**attempt))
    assert last_error is not None
    raise last_error


async def generate_exam(
    *,
    user_id: str,
    spec: ExamSpec,
    course_text: str,
) -> ExamContent:
    spec.validate_consistency()

    user_prompt = build_user_prompt(spec=spec, course_text=course_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    cost_usd = 0.0  # accumulate across retries so we bill the true spend once
    for _ in range(2):
        try:
            result = await _chat_with_backoff(messages)
            cost_usd += result.cost_usd
            payload = json.loads(_extract_json(result.content))
            content = ExamContent.model_validate(payload)
            if len(content.exercises) != spec.num_exercises:
                raise ValueError(
                    f"Expected {spec.num_exercises} exercises, got {len(content.exercises)}"
                )
            # One exam = one quota credit, billed with the full cost of all attempts.
            # The recording is a synchronous DB write — keep it off the loop.
            await run_in_threadpool(usage_service.record_exam, user_id, cost_usd)
            return _fix_points(content, spec)
        # JSONDecodeError and pydantic's ValidationError both derive from
        # ValueError, so a single ValueError catch covers all three.
        except ValueError as e:
            last_error = e
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response could not be parsed: "
                        f"{e}. Respond again with ONLY the JSON object, "
                        "no markdown or commentary."
                    ),
                }
            )
            continue

    # All attempts failed: no exam credit consumed, but the spend still happened,
    # so account for it in the global budget.
    await run_in_threadpool(usage_service.record_cost, user_id, cost_usd)
    raise RuntimeError(f"Failed to generate a valid exam: {last_error}")
