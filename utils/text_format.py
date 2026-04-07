"""
Text formatting and cleaning utilities for VEGA AI Assistant.
"""

import re

# Common stop words for extracting meaningful query terms
DEFAULT_STOP_WORDS = frozenset([
    "search", "for", "the", "country", "in", "item", "on",
    "wikipedia", "about", "tell", "me", "who", "is", "what",
    "an", "a", "of", "can", "you", "please", "find",
])


def cmd_format(text: str) -> str:
    """
    Clean AI-generated text for console display and speech.

    Removes markdown bold markers and converts bullet points
    to plain dashes for readability.

    Args:
        text: Raw text from AI model response.

    Returns:
        Cleaned plain-text string.
    """
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # remove **bold**
    text = re.sub(r"\* ", "- ", text)               # convert * bullets to -
    text = re.sub(r"#{1,6}\s*", "", text)           # remove ### headings
    text = re.sub(r"`([^`]*)`", r"\1", text)        # remove `code` backticks
    return text.strip()


def clean_query_words(query: str, stop_words: frozenset = None) -> str:
    """
    Remove common stop words from a query to extract the core topic.

    Args:
        query: Raw user query string.
        stop_words: Set of words to remove. Defaults to DEFAULT_STOP_WORDS.

    Returns:
        Cleaned query with stop words removed.
    """
    if stop_words is None:
        stop_words = DEFAULT_STOP_WORDS
    words = query.split()
    clean = [w for w in words if w.lower() not in stop_words]
    return " ".join(clean)
