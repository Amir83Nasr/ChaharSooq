"""Unit tests for the shared catalog-section classifier."""

import pytest

from app.core.top_groups import (
    DIGITAL_NAME_PATTERNS,
    is_digital_group,
    normalize_group_name,
    top_group_of,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("گوشی و تبلت", True),
        ("لپتاپ گیمینگ", True),
        ("لب تاپ و PC", True),
        ("گوشي و تبلت", True),  # Arabic yeh in a Parsina export
        ("کنسول XBOX", True),
        ("آيپد", True),
        ("لوازم خانگی بلانتون", False),
        ("فرش آدینا", False),
        (None, False),
    ],
)
def test_digital_keywords_match_new_group_names(name: str | None, expected: bool) -> None:
    assert is_digital_group(name) is expected


def test_group_name_wins_over_drifting_id() -> None:
    assert is_digital_group(None, 27) is True  # id fallback for nameless rows
    assert is_digital_group("لوازم خانگی بلانتون", 7) is False
    assert top_group_of("لپتاپ گیمینگ") == "کالای دیجیتال"
    assert top_group_of("لوازم خانگی سونی") == "لوازم خانگی"


def test_sql_patterns_are_generated_from_the_same_keywords() -> None:
    assert normalize_group_name("  گوشي  و  تبلت  ") == "گوشی و تبلت"
    assert "آيپد" in DIGITAL_NAME_PATTERNS  # Persian → Arabic letter form
    assert "نوتبوک" in DIGITAL_NAME_PATTERNS  # dropped-space form
