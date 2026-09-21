"""Text cleaning and normalization for extracted document text."""

import re
import unicodedata


class TextCleaner:
    """Provides modular, robust text cleaning pipelines."""

    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize unicode characters (NFKC) and replace weird quotation marks/dashes."""
        if not text:
            return ""
        # NFKC converts ligatures (fi -> f i) and compatible glyphs
        normalized = unicodedata.normalize("NFKC", text)

        # Replace smart quotes and dashes
        replacements = {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u2026": "...",
            "\u00a0": " ",  # Non-breaking space
            "\ufeff": "",  # Byte order mark
            "\u200b": "",  # Zero-width space
            "\u200c": "",  # Zero-width non-joiner
            "\u200d": "",  # Zero-width joiner
        }
        for orig, repl in replacements.items():
            normalized = normalized.replace(orig, repl)
        return normalized

    @staticmethod
    def remove_control_characters(text: str) -> str:
        """Remove unprintable ASCII/control characters except standard newlines and tabs."""
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    @staticmethod
    def clean_whitespace(text: str) -> str:
        """Normalize consecutive horizontal spaces and excessive empty lines."""
        # Replace multiple horizontal spaces/tabs with a single space
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse 3 or more newlines into double newlines (preserving paragraphs)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip trailing whitespace on each line
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(lines).strip()

    @classmethod
    def clean(cls, text: str) -> str:
        """Run complete text cleaning pipeline."""
        if not text:
            return ""
        step1 = cls.normalize_unicode(text)
        step2 = cls.remove_control_characters(step1)
        step3 = cls.clean_whitespace(step2)
        return step3
