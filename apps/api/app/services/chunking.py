"""Paragraph/sentence-aware chunking with overlap. Handles Latin, Arabic-script and Devanagari punctuation."""
import re

SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟۔।])\s+")
PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def _split_long(paragraph: str, size: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for sentence in SENTENCE_SPLIT.split(paragraph):
        if len(sentence) > size:  # no sentence boundary: hard split
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(sentence[i : i + size] for i in range(0, len(sentence), size))
        elif current and len(current) + 1 + len(sentence) > size:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return ""
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :] if 0 <= space < len(tail) - 1 else tail


def chunk_sections(sections: list[tuple[int | None, str]], size: int, overlap: int) -> list[tuple[int | None, str]]:
    """sections: (page, text) pairs. Returns (page, chunk_text) pairs; chunks never span pages."""
    chunks: list[tuple[int | None, str]] = []
    for page, text in sections:
        units: list[str] = []
        for paragraph in (p.strip() for p in PARAGRAPH_SPLIT.split(text)):
            if not paragraph:
                continue
            units.extend([paragraph] if len(paragraph) <= size else _split_long(paragraph, size))

        current = ""
        for unit in units:
            if current and len(current) + 1 + len(unit) > size:
                chunks.append((page, current))
                tail = _tail(current, overlap)
                current = f"{tail}\n{unit}" if tail else unit
            else:
                current = f"{current}\n{unit}" if current else unit
        if current.strip():
            chunks.append((page, current))
    return chunks
