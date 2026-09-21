"""Query preprocessing, conversational context rewriting, and keyword expansion."""

import re


class QueryProcessor:
    """Preprocesses user queries to optimize both semantic vector retrieval and BM25 keyword matching."""

    PRONOUNS = {"it", "this", "that", "these", "those", "they", "them", "its", "their"}

    @classmethod
    def normalize(cls, query: str) -> str:
        """Normalize query string by trimming, removing excessive whitespace, and control chars."""
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", query)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def rewrite_with_history(
        cls,
        query: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> str:
        """If the query contains referential pronouns and chat history is present,
        synthesize an expanded query carrying conversational context.
        chat_history is a list of (role, content) pairs.
        """
        normalized = cls.normalize(query)
        if not chat_history:
            return normalized

        words = set(re.findall(r"\b\w+\b", normalized.lower()))
        has_pronoun = bool(words.intersection(cls.PRONOUNS))

        if has_pronoun and len(chat_history) >= 1:
            # Find the most recent user or assistant message that provides topic context
            recent_context = ""
            for role, content in reversed(chat_history[-4:]):
                if content:
                    recent_context = content[:150]
                    break
            if recent_context:
                return f"{normalized} (context: {recent_context})"

        return normalized

    @classmethod
    def extract_keywords(cls, query: str) -> list[str]:
        """Extract alphanumeric keywords longer than 2 characters for BM25 expansion."""
        stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "if",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "from",
            "up",
            "down",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "can",
            "could",
            "should",
            "would",
            "what",
            "which",
            "who",
            "when",
            "where",
            "why",
            "how",
            "using",
        }
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", query.lower())
        keywords = [t for t in tokens if len(t) > 2 and t not in stopwords]
        return keywords
