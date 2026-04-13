import pytest

from app.stamping import resolve_pages


def test_resolve_pages_supports_common_rules():
    assert resolve_pages("all", 5) == [0, 1, 2, 3, 4]
    assert resolve_pages("first", 5) == [0]
    assert resolve_pages("last", 5) == [4]


def test_resolve_pages_supports_specific_pages_and_ranges():
    assert resolve_pages("1,3,5", 5) == [0, 2, 4]
    assert resolve_pages("2-4", 5) == [1, 2, 3]
    assert resolve_pages("1,3-4,99", 5) == [0, 2, 3]


def test_resolve_pages_rejects_invalid_rules():
    with pytest.raises(ValueError):
        resolve_pages("0", 5)
    with pytest.raises(ValueError):
        resolve_pages("4-2", 5)
    with pytest.raises(ValueError):
        resolve_pages("abc", 5)
