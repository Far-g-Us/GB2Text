from typing import Any, cast

import pytest

from core.diff_text import ChangedPair, DiffReport, text_segments_compare


def test_added_removed_changed():
    report = text_segments_compare(
        {"a": "hello", "b": "same", "c": "old"},
        {"b": "same", "c": "new", "d": "fresh"},
    )
    assert report.added == ["d"]
    assert report.removed == ["a"]
    assert report.changed == [ChangedPair("c", "old", "new")]


def test_empty_both():
    assert text_segments_compare({}, {}) == DiffReport([], [], [])


def test_identical_empty_report():
    texts = {"a": "x", "b": "y"}
    assert text_segments_compare(texts, dict(texts)) == DiffReport([], [], [])


def test_added_sorted_deterministic():
    report = text_segments_compare({}, {"z": "1", "a": "2", "m": "3"})
    assert report.added == ["a", "m", "z"]
    again = text_segments_compare({"z": "1", "m": "3", "a": "2"}, {})
    assert again.removed == ["a", "m", "z"]


def test_changed_sorted_by_key():
    report = text_segments_compare({"b": "1", "a": "1"}, {"b": "2", "a": "2"})
    assert [p.key for p in report.changed] == ["a", "b"]


def test_empty_segment_key_logic():
    report = text_segments_compare({"a": ""}, {})
    assert report.removed == ["a"]
    report = text_segments_compare({}, {"a": ""})
    assert report.added == ["a"]


def test_input_not_mutated():
    first = {"b": "x", "a": "y"}
    second = {"a": "y", "c": "z"}
    snapshot = (dict(first), dict(second))
    text_segments_compare(first, second)
    assert (first, second) == snapshot


def test_non_mapping_raises():
    with pytest.raises(TypeError):
        text_segments_compare(cast(Any, ["a"]), {})
    with pytest.raises(TypeError):
        text_segments_compare({}, cast(Any, ["a"]))
    with pytest.raises(TypeError):
        text_segments_compare(cast(Any, None), {})


def test_non_str_key_raises():
    with pytest.raises(TypeError):
        text_segments_compare(cast(Any, {1: "x"}), {})
    with pytest.raises(TypeError):
        text_segments_compare({}, cast(Any, {(1,): "x"}))


def test_non_str_value_raises():
    with pytest.raises(TypeError):
        text_segments_compare({"a": cast(Any, ["x"])}, {})
    with pytest.raises(TypeError):
        text_segments_compare({}, {"a": cast(Any, 5)})
