"""Test DCC numbers."""

import pytest
from dcc.records import DCCNumber


@pytest.mark.parametrize(
    "a,b,c,expected_category,expected_numeric,expected_version",
    (
        ## No version.
        ("T", "12345", None, "T", "12345", None),
        ## With version.
        # Version as string.
        ("T", "12345", 0, "T", "12345", 0),
        ("T", "12345", 1, "T", "12345", 1),
        ("T", "12345", 2, "T", "12345", 2),
        # Version as int.
        ("T", 12345, 0, "T", "12345", 0),
        ("T", 12345, 1, "T", "12345", 1),
        ("T", 12345, 2, "T", "12345", 2),
        ## With LIGO bit.
        ("LIGO-T12345", None, None, "T", "12345", None),
        ("LIGO-T12345-x0", None, None, "T", "12345", 0),
        ("LIGO-T12345-v2", None, None, "T", "12345", 2),
    ),
)
def test_parse(a, b, c, expected_category, expected_numeric, expected_version):
    """Test DCC number parsing."""
    number = DCCNumber(a, b, c)
    assert number.category == expected_category
    assert number.numeric == expected_numeric
    assert number.version == expected_version


@pytest.mark.parametrize(
    "a,b,c",
    (
        ## Invalid category.
        ("Y12345", None, None),
        ("Y", "12345", None),
        ## Invalid numeric.
        ("T", -12345, None),
        ("T", 12345.5, None),
        ("T", -12345.5, None),
        ("T", "-12345", None),
        ("T", "12345.5", None),
        ("T", "-12345.5", None),
        ## Invalid version.
        ("T", "12345", -1),
        ("T", "12345", 1.5),
        ("T", "12345", 1 + 2j),
        ("T", "12345", 3.1 + 2.6j),
    ),
)
def test_invalid_parse(a, b, c):
    """Test invalid DCC number parsing."""
    with pytest.raises(ValueError):
        DCCNumber(a, b, c)


@pytest.mark.parametrize(
    "lhs,rhs",
    (("T12345", "T12345"), ("T12345-v1", "T12345-v1"), ("T12345-v3", "T12345-v3")),
)
def test_equal(lhs, rhs):
    """Test equal numbers."""
    assert DCCNumber(lhs) == DCCNumber(rhs)


@pytest.mark.parametrize(
    "lhs,rhs",
    (
        # Same number, different (or no) version.
        ("T12345", "T12345-x0"),
        ("T12345", "T12345-v3"),
        ("T12345-x0", "T12345-v1"),
        ("T12345-v1", "T12345-v3"),
        # Different numbers.
        ("T54321", "T12345"),
        ("T54321", "T12345-v3"),
        ("T54321-x0", "T12345-x0"),
        ("T54321-v3", "T12345-v3"),
    ),
)
def test_not_equal(lhs, rhs):
    """Test unequal numbers."""
    assert DCCNumber(lhs) != DCCNumber(rhs)


@pytest.mark.parametrize(
    "lhs,rhs",
    (
        ("T12345-v1", "T12345-x0"),
        ("T12345-v2", "T12345-x0"),
        ("T12345-v2", "T12345-v1"),
    ),
)
def test_greater_than(lhs, rhs):
    """Test greater than numbers."""
    assert DCCNumber(lhs) > DCCNumber(rhs)


@pytest.mark.parametrize(
    "lhs,rhs",
    (
        ("T12345-x0", "T12345-v1"),
        ("T12345-x0", "T12345-v2"),
        ("T12345-v1", "T12345-v2"),
    ),
)
def test_less_than(lhs, rhs):
    """Test less than numbers."""
    assert DCCNumber(lhs) < DCCNumber(rhs)
