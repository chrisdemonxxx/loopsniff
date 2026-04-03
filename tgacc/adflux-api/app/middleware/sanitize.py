"""
Input sanitization utilities to prevent XSS and injection attacks.
"""

import re
import unicodedata

import bleach


def strip_html_tags(value: str) -> str:
    """Remove all HTML tags from a string, allowing no markup."""
    return bleach.clean(value, tags=[], attributes={}, strip=True)


def sanitize_string(value: str) -> str:
    """Strip HTML, collapse whitespace, and trim the result."""
    cleaned = strip_html_tags(value)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def validate_email(email: str) -> bool:
    """Return True if *email* looks like a valid email address."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a file name for safe filesystem storage.

    - Normalise unicode
    - Strip directory separators and null bytes
    - Replace unsafe characters with underscores
    - Reject hidden-file names (leading dot)
    """
    filename = unicodedata.normalize("NFKD", filename)
    # Remove path separators and null bytes
    filename = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")
    # Allow only alphanumerics, hyphens, underscores, and a single dot for extension
    filename = re.sub(r"[^\w.\-]", "_", filename)
    # Prevent hidden files
    filename = filename.lstrip(".")
    # Collapse consecutive underscores
    filename = re.sub(r"_+", "_", filename)
    return filename or "unnamed"
