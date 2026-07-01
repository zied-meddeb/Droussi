"""Tests for the exam prompt builder."""
from app.prompts.exam_prompt import build_user_prompt

from .conftest import make_spec


class TestBuildUserPrompt:
    def test_includes_spec_details(self):
        prompt = build_user_prompt(spec=make_spec(), course_text="Some course text")
        assert "Difficulty: medium" in prompt
        assert "exercise 1: 3 pts" in prompt
        assert "exercise 2: 7 pts" in prompt
        assert "Some course text" in prompt

    def test_maps_language_label(self):
        prompt = build_user_prompt(spec=make_spec(language="fr"), course_text="x")
        assert "French" in prompt

    def test_includes_extra_instructions_when_present(self):
        spec = make_spec(extra_instructions="Focus on chapter 3")
        assert "Focus on chapter 3" in build_user_prompt(spec=spec, course_text="x")

    def test_truncates_long_course_text(self):
        prompt = build_user_prompt(spec=make_spec(), course_text="a" * 20000)
        assert "[... content truncated ...]" in prompt

    def test_maps_question_type_labels(self):
        prompt = build_user_prompt(
            spec=make_spec(question_types=["mcq"]), course_text="x"
        )
        assert "MCQ" in prompt
