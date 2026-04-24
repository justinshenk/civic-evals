"""Unit tests for the schema's anti-footgun guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from p3.schemas import Task


def test_missing_target_and_rubric_rejected() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": "x-1",
                "domain": "x",
                "subdomain": "y",
                "input": "whatever",
                "metadata": {"difficulty": "easy", "source": "src", "tags": ["t"]},
            }
        )


def test_persona_in_input_rejected() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": "x-2",
                "domain": "x",
                "subdomain": "y",
                "input": "As a first-time voter, where do I register?",
                "target": "see SoS",
                "metadata": {"difficulty": "easy", "source": "src", "tags": ["t"]},
            }
        )


def test_empty_source_rejected() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": "x-3",
                "domain": "x",
                "subdomain": "y",
                "input": "a fine question",
                "target": "answer",
                "metadata": {"difficulty": "easy", "source": "", "tags": ["t"]},
            }
        )


def test_persona_name_xor_attributes() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": "x-4",
                "domain": "x",
                "subdomain": "y",
                "input": "a fine question",
                "target": "answer",
                "persona": {"name": "journalist", "attributes": {"role": "journalist"}},
                "metadata": {"difficulty": "easy", "source": "src", "tags": ["t"]},
            }
        )


def test_valid_task_accepts() -> None:
    Task.model_validate(
        {
            "id": "x-5",
            "domain": "x",
            "subdomain": "y",
            "input": "a fine question",
            "target": "answer",
            "persona": {"name": "journalist"},
            "metadata": {"difficulty": "easy", "source": "src", "tags": ["t"]},
        }
    )
