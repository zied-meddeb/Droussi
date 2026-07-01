"""Shared fixtures and builders for backend tests."""
import os

# Required settings must exist before app modules import get_settings().
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("SUPER_ADMIN_EMAILS", "admin@test.com")

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.main import create_app
from app.models.schemas import ExamContent, ExamSpec, Exercise


TEST_USER = CurrentUser(id="user123", email="user@test.com")


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    """TestClient with authentication overridden to a fixed test user."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_exercise(**overrides) -> Exercise:
    base = dict(
        type="mcq",
        question="What is 2 + 2?",
        choices=["3", "4", "5"],
        answer="4",
        explanation="Basic arithmetic.",
        points=5,
    )
    base.update(overrides)
    return Exercise(**base)


def make_content(exercises=None, title="Sample Exam", total_points=10) -> ExamContent:
    if exercises is None:
        exercises = [make_exercise(), make_exercise(type="open", choices=None)]
    return ExamContent(title=title, total_points=total_points, exercises=exercises)


def make_spec(**overrides) -> ExamSpec:
    base = dict(
        difficulty="medium",
        question_types=["mcq", "open"],
        num_exercises=2,
        total_points=10,
        per_exercise_points=[3, 7],
        export_format="pdf",
    )
    base.update(overrides)
    return ExamSpec(**base)
