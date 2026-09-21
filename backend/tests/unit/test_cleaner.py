"""Unit tests for text cleaning and normalization."""

from app.documents.cleaner import TextCleaner


def test_cleaner_strips_excessive_whitespace():
    raw = "This   is   a    test \n\n\n  with  multiple   newlines   and  spaces."
    cleaned = TextCleaner.clean(raw)
    assert "   " not in cleaned
    import re

    assert "test with multiple newlines and spaces." in re.sub(r"\s+", " ", cleaned)


def test_cleaner_removes_zero_width_and_control_chars():
    raw = "Zero\u200bwidth\ufeffspace\x00and\x08control"
    cleaned = TextCleaner.clean(raw)
    assert "\u200b" not in cleaned
    assert "\ufeff" not in cleaned
    assert "\x00" not in cleaned
    assert "\x08" not in cleaned
    assert "Zero" in cleaned


def test_cleaner_normalizes_unicode_ligatures():
    raw = "The ﬁrst speciﬁc example of ligatures."
    cleaned = TextCleaner.clean(raw)
    assert "first" in cleaned
    assert "specific" in cleaned


def test_cleaner_empty_input():
    assert TextCleaner.clean("") == ""
    assert TextCleaner.clean("   \n\t  ") == ""
