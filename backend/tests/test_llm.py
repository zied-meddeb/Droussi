"""Unit tests for the OpenRouter client."""
import pytest

from app.services import llm
from app.services.llm import _parse_result, chat, get_key_status

from .fakes import FakeAsyncClient, FakeResponse


def _patch_client(monkeypatch, **client_kwargs):
    monkeypatch.setattr(
        "app.services.llm.httpx.AsyncClient",
        lambda *_a, **_k: FakeAsyncClient(**client_kwargs),
    )


def _chat_ok(content="hello", cost=0.002):
    return FakeResponse(
        json_data={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8, "cost": cost},
        }
    )


def _payload(**usage):
    return {
        "choices": [{"message": {"content": "hello"}}],
        "usage": usage,
    }


class TestParseResult:
    def test_reads_content_tokens_and_cost(self):
        result = _parse_result(
            _payload(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.002)
        )
        assert result.content == "hello"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.total_tokens == 15
        assert result.cost_usd == 0.002

    def test_total_tokens_falls_back_to_sum(self):
        result = _parse_result(_payload(prompt_tokens=7, completion_tokens=3))
        assert result.total_tokens == 10

    def test_missing_usage_defaults_to_zero(self):
        result = _parse_result({"choices": [{"message": {"content": "x"}}]})
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0
        assert result.cost_usd == 0.0


class TestChat:
    async def test_success_returns_first_model_result(self, monkeypatch):
        _patch_client(monkeypatch, post_responses=[_chat_ok("answer")])
        result = await chat([{"role": "user", "content": "hi"}])
        assert result.content == "answer"
        assert result.cost_usd == 0.002

    async def test_falls_back_to_next_model_on_rate_limit(self, monkeypatch):
        # First model: 429 with a long Retry-After (no wait, move on). Second: OK.
        _patch_client(
            monkeypatch,
            post_responses=[
                FakeResponse(status_code=429, headers={"Retry-After": "100"}),
                _chat_ok("second model"),
            ],
        )
        result = await chat([{"role": "user", "content": "hi"}])
        assert result.content == "second model"

    async def test_all_models_rate_limited_raises(self, monkeypatch):
        _patch_client(
            monkeypatch,
            post_responses=[FakeResponse(status_code=429, headers={"Retry-After": "100"})] * 5,
        )
        with pytest.raises(RuntimeError, match="All configured OpenRouter models failed"):
            await chat([{"role": "user", "content": "hi"}])

    async def test_json_mode_requests_json_object(self, monkeypatch):
        _patch_client(monkeypatch, post_responses=[_chat_ok("{}")])
        result = await chat([{"role": "user", "content": "hi"}], response_format_json=True)
        assert result.content == "{}"


class TestGetKeyStatus:
    async def test_parses_credit_status(self, monkeypatch):
        _patch_client(
            monkeypatch,
            get_response=FakeResponse(
                json_data={
                    "data": {"usage": 1.5, "limit": 5.0, "limit_remaining": 3.5, "is_free_tier": True}
                }
            ),
        )
        status = await get_key_status()
        assert status.usage_usd == 1.5
        assert status.limit_usd == 5.0
        assert status.is_free_tier is True

    async def test_pay_as_you_go_null_limit(self, monkeypatch):
        _patch_client(
            monkeypatch,
            get_response=FakeResponse(json_data={"data": {"usage": 2.0, "is_free_tier": False}}),
        )
        status = await get_key_status()
        assert status.limit_usd is None
        assert status.limit_remaining_usd is None
