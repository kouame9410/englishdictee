"""Découpage d'un texte en segments de dictée (phrases, puis groupes de souffle pour les longues phrases)."""
import re

LONG_SENTENCE_WORDS = 12
MIN_CHUNK_WORDS = 3


def split_segments(text):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    segments = []
    for sentence in sentences:
        if len(sentence.split()) <= LONG_SENTENCE_WORDS:
            segments.append(sentence)
            continue
        chunks = []
        for part in re.split(r"(?<=[,;:])\s+", sentence):
            if chunks and len(part.split()) < MIN_CHUNK_WORDS:
                chunks[-1] += " " + part  # un fragment trop court est rattaché au précédent
            else:
                chunks.append(part)
        if len(chunks) > 1 and len(chunks[0].split()) < MIN_CHUNK_WORDS:
            chunks[1] = chunks[0] + " " + chunks[1]
            chunks = chunks[1:]
        segments.extend(chunks)
    return segments
