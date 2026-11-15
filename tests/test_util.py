import pytest

from fleetcom import util


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-11-02T09:00:00-08:00", "2026-11-02T17:00:00Z"),
        ("2026-11-02T23:30:00-08:00", "2026-11-03T07:30:00Z"),
        ("2026-11-02T09:00:00+05:30", "2026-11-02T03:30:00Z"),
        ("2026-11-02T09:00:00Z", "2026-11-02T09:00:00Z"),
        ("2026-11-02T09:00:00", "2026-11-02T09:00:00Z"),
        ("2026-11-02 09:00", "2026-11-02T09:00:00Z"),
        ("2026-11-02", "2026-11-02T00:00:00Z"),
        ("2026-11-02T09:00:00.999+00:00", "2026-11-02T09:00:00Z"),
        (None, None),
    ],
)
def test_to_utc(value, expected):
    assert util.to_utc(value) == expected


def test_to_utc_clears_on_empty_string():
    assert util.to_utc("") is None


@pytest.mark.parametrize("value", ["next tuesday", "0001-01-01T00:00:00+05:00"])
def test_to_utc_rejects_a_value_it_cannot_convert(value):
    with pytest.raises(ValueError, match="ISO-8601"):
        util.to_utc(value)


def test_normalize_times_touches_only_named_fields():
    fields = {
        "due": "2026-11-02T09:00:00-08:00",
        "summary": "2026-11-02T09:00:00-08:00",
    }
    assert util.normalize_times(fields, ("due", "remind_at")) == {
        "due": "2026-11-02T17:00:00Z",
        "summary": "2026-11-02T09:00:00-08:00",
    }


def test_normalize_times_names_the_field_in_errors():
    with pytest.raises(ValueError, match="remind_at"):
        util.normalize_times({"remind_at": "soon"}, ("due", "remind_at"))
