"""Unit tests for the LLM output helpers and the generate_exam orchestration."""
import json

import pytest

from app.services import exam_generator
from app.services.exam_generator import (
    _chat_with_backoff,
    _extract_json,
    _fix_points,
    generate_exam,
)
from app.services.llm import ChatResult

from .conftest import make_content, make_exercise, make_spec


VALID_EXAM_JSON = json.dumps(
    {
        "title": "Generated Exam",
        "total_points": 10,
        "exercises": [
            {"type": "mcq", "question": "q1", "choices": ["a", "b", "c"], "answer": "a", "points": 3},
            {"type": "open", "question": "q2", "answer": "a2", "points": 7},
        ],
    }
)


def _chat_result(content: str) -> ChatResult:
    return ChatResult(content=content, prompt_tokens=1, completion_tokens=1, total_tokens=2, cost_usd=0.001)


async def _instant_sleep(_seconds):
    """Patch asyncio.sleep so backoff tests don't actually wait."""
    return None


@pytest.fixture
def _no_billing(monkeypatch):
    recorded = {}
    monkeypatch.setattr(
        "app.services.exam_generator.usage_service.record_exam",
        lambda uid, cost: recorded.update(exam=(uid, cost)),
    )
    monkeypatch.setattr(
        "app.services.exam_generator.usage_service.record_cost",
        lambda uid, cost: recorded.update(cost=(uid, cost)),
    )
    return recorded


def _stub_chat(monkeypatch, contents):
    """Patch llm.chat to yield the given contents in order across retries."""
    queue = list(contents)

    async def fake_chat(*_a, **_k):
        return _chat_result(queue.pop(0))

    monkeypatch.setattr("app.services.exam_generator.llm.chat", fake_chat)


class TestExtractJson:
    def test_strips_json_fenced_block(self):
        text = '```json\n{"a": 1}\n```'
        assert _extract_json(text) == '{"a": 1}'

    def test_strips_plain_fenced_block(self):
        text = '```\n{"a": 1}\n```'
        assert _extract_json(text) == '{"a": 1}'

    def test_extracts_object_from_surrounding_prose(self):
        text = 'Here is your exam: {"a": 1, "b": 2} Hope it helps!'
        assert _extract_json(text) == '{"a": 1, "b": 2}'

    def test_returns_text_unchanged_when_no_object(self):
        assert _extract_json("no json here") == "no json here"

    def test_trims_surrounding_whitespace(self):
        assert _extract_json('   {"a": 1}   ') == '{"a": 1}'


class TestFixPoints:
    def test_truncates_extra_exercises_to_spec(self):
        content = make_content(
            exercises=[make_exercise() for _ in range(4)], total_points=99
        )
        spec = make_spec(num_exercises=2, per_exercise_points=[3, 7], total_points=10)
        fixed = _fix_points(content, spec)
        assert len(fixed.exercises) == 2

    def test_overrides_per_exercise_and_total_points(self):
        content = make_content(
            exercises=[make_exercise(points=1), make_exercise(points=1)],
            total_points=2,
        )
        spec = make_spec(num_exercises=2, per_exercise_points=[4, 6], total_points=10)
        fixed = _fix_points(content, spec)
        assert [ex.points for ex in fixed.exercises] == [4, 6]
        assert fixed.total_points == 10

    def test_keeps_fewer_exercises_when_model_returns_too_few(self):
        content = make_content(exercises=[make_exercise(points=1)], total_points=1)
        spec = make_spec(num_exercises=3, per_exercise_points=[2, 3, 5], total_points=10)
        fixed = _fix_points(content, spec)
        assert len(fixed.exercises) == 1
        assert fixed.exercises[0].points == 2


class TestChatWithBackoff:
    async def test_retries_transient_runtime_error_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(exam_generator.asyncio, "sleep", _instant_sleep)
        calls = {"n": 0}

        async def flaky(*_a, **_k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("all models rate-limited")
            return _chat_result(VALID_EXAM_JSON)

        monkeypatch.setattr("app.services.exam_generator.llm.chat", flaky)
        result = await _chat_with_backoff([{"role": "user", "content": "x"}])
        assert result.content == VALID_EXAM_JSON
        assert calls["n"] == 2

    async def test_gives_up_after_max_attempts(self, monkeypatch):
        monkeypatch.setattr(exam_generator.asyncio, "sleep", _instant_sleep)

        async def always_fail(*_a, **_k):
            raise RuntimeError("still failing")

        monkeypatch.setattr("app.services.exam_generator.llm.chat", always_fail)
        with pytest.raises(RuntimeError):
            await _chat_with_backoff([{"role": "user", "content": "x"}])


class TestGenerateExam:
    async def test_success_records_exam(self, monkeypatch, _no_billing):
        _stub_chat(monkeypatch, [VALID_EXAM_JSON])
        content = await generate_exam(
            user_id="user123", spec=make_spec(), course_text="course"
        )
        assert content.title == "Generated Exam"
        assert _no_billing["exam"][0] == "user123"

    async def test_retries_then_succeeds(self, monkeypatch, _no_billing):
        _stub_chat(monkeypatch, ["not json", VALID_EXAM_JSON])
        content = await generate_exam(
            user_id="user123", spec=make_spec(), course_text="course"
        )
        assert content.title == "Generated Exam"

    async def test_all_attempts_fail_raises_and_records_cost(self, monkeypatch, _no_billing):
        _stub_chat(monkeypatch, ["nope", "still nope"])
        with pytest.raises(RuntimeError):
            await generate_exam(user_id="user123", spec=make_spec(), course_text="course")
        assert _no_billing["cost"][0] == "user123"

    async def test_wrong_exercise_count_is_rejected(self, monkeypatch, _no_billing):
        one_exercise = json.dumps(
            {
                "title": "T",
                "total_points": 10,
                "exercises": [{"type": "open", "question": "q", "answer": "a", "points": 10}],
            }
        )
        _stub_chat(monkeypatch, [one_exercise, one_exercise])
        with pytest.raises(RuntimeError):
            await generate_exam(user_id="user123", spec=make_spec(), course_text="course")
