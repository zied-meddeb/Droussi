"""Unit tests for the derived properties on Settings."""
from app.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-key",
        supabase_jwt_secret="jwt-secret",
        openrouter_api_key="or-key",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


class TestCorsOrigins:
    def test_splits_strips_and_dedupes(self):
        s = _settings(
            allowed_origins="http://localhost:5173, https://app.test/ , http://localhost:5173"
        )
        assert s.cors_origins == ["http://localhost:5173", "https://app.test"]

    def test_empty_entries_are_dropped(self):
        s = _settings(allowed_origins="https://a.test,, ,https://b.test")
        assert s.cors_origins == ["https://a.test", "https://b.test"]


class TestSuperAdmins:
    def test_lowercases_and_trims(self):
        s = _settings(super_admin_emails="Admin@Test.com, Owner@Test.COM")
        assert s.super_admins == ["admin@test.com", "owner@test.com"]

    def test_empty_string_yields_empty_list(self):
        assert _settings(super_admin_emails="").super_admins == []


class TestOpenRouterModels:
    def test_primary_comes_first_then_fallbacks_deduped(self):
        s = _settings(
            openrouter_model="primary/model",
            openrouter_fallback_models="fallback/a, primary/model, fallback/b",
        )
        assert s.openrouter_models == ["primary/model", "fallback/a", "fallback/b"]
