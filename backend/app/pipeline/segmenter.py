import re
from typing import Any

import tiktoken

SECTION_DELIMITERS = [
    r"(?:^|(?<=[.!?:\s]))Definition:\s*",
    r"(?:^|(?<=[.!?:\s]))Explanation:\s*",
    r"(?:^|(?<=[.!?:\s]))Demo Scenario:\s*",
    r"(?:^|(?<=[.!?:\s]))Example:\s*",
    r"(?:^|(?<=[.!?:\s]))Scenario:\s*",
    r"(?:^|(?<=[.!?:\s]))Fallacious Response:\s*",
    r"(?:^|(?<=[.!?:\s]))Why it'?s flawed:\s*",
    r"(?:^|(?<=[.!?:\s]))Analysis:\s*",
    r"(?:^|(?<=[.!?:\s]))What is\s+",
    r"(?:^|(?<=[.!?:\s]))\d+\.\s+(Definition|Example|Scenario)",
]

MAX_SEGMENTS = 10
MAX_QUOTE_CHARS = 200


def _normalize_boundaries(text: str) -> tuple[str, list[int]]:
    """
    Return the text unchanged with an identity offset map.

    Splitting is deliberately NOT performed at sentence boundaries: a
    multi-sentence argument must stay in one segment so its premise and
    conclusion are classified together (per-sentence splitting produced
    false positives on isolated conclusion fragments such as
    "Therefore it rained."). Segmentation only happens on explicit line
    breaks, structured section delimiters, or token overflow windows.
    """
    return text, list(range(len(text)))


def _map_to_original(norm_idx: int, offset_map: list[int]) -> int:
    if not offset_map:
        return 0
    if norm_idx <= 0:
        return offset_map[0]
    if norm_idx >= len(offset_map):
        return offset_map[-1] + 1
    return offset_map[norm_idx]


def segment_text(text: str) -> list[dict[str, Any]]:
    normalized, offset_map = _normalize_boundaries(text)

    combined_pattern = "|".join(SECTION_DELIMITERS)
    matches = list(re.finditer(combined_pattern, normalized, re.MULTILINE | re.IGNORECASE))

    segments: list[dict[str, str | int | None]] = []

    if matches:
        for i in range(len(matches)):
            start = matches[i].start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(normalized)
            segment_content = normalized[start:end].strip()
            if segment_content:
                orig_start = _map_to_original(start, offset_map)
                orig_end = _map_to_original(end, offset_map)
                segments.append(
                    {
                        "text": segment_content,
                        "start_offset": orig_start,
                        "end_offset": orig_end,
                        "is_argumentative": None,
                    }
                )
        if segments:
            return segments

    # Line-based splitting: only explicit line breaks in the original text
    # create segments (e.g. multi-paragraph input). Sentences are NOT split
    # into separate segments so multi-sentence arguments keep their
    # premise-conclusion structure.
    lines = [l.strip() for l in normalized.split("\n") if l.strip()]
    if len(lines) > 1:
        curr_pos = 0
        for line in lines:
            # Find the line in normalized text to get offsets
            start_idx = normalized.find(line, curr_pos)
            if start_idx != -1:
                end_idx = start_idx + len(line)
                orig_start = _map_to_original(start_idx, offset_map)
                orig_end = _map_to_original(end_idx, offset_map)
                segments.append(
                    {
                        "text": line,
                        "start_offset": orig_start,
                        "end_offset": orig_end,
                        "is_argumentative": None,
                    }
                )
                curr_pos = end_idx
        if segments:
            if len(segments) > MAX_SEGMENTS:
                merged = []
                merge_batch = max(1, len(segments) // MAX_SEGMENTS)
                for i in range(0, len(segments), merge_batch):
                    batch = segments[i : i + merge_batch]
                    merged_text = text[batch[0]["start_offset"] : batch[-1]["end_offset"]]  # type: ignore[index]
                    merged.append(
                        {
                            "text": merged_text,
                            "start_offset": batch[0]["start_offset"],
                            "end_offset": batch[-1]["end_offset"],
                            "is_argumentative": None,
                        }
                    )
                return merged
            return segments

    try:
        enc = tiktoken.get_encoding("cl100k_base")
        token_count = len(enc.encode(text))
        if token_count > 448:
            return sliding_window_segments(text)
    except Exception:
        if len(text) > 2000:
            return sliding_window_segments(text)

    return [
        {
            "text": text,
            "start_offset": 0,
            "end_offset": len(text),
            "is_argumentative": None,
        }
    ]


def sliding_window_segments(text: str, window_size: int = 448, overlap: int = 128) -> list[dict[str, Any]]:
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(text)
        token_char_offsets = _get_token_char_offsets(enc, text, tokens)

        segments = []
        start_token = 0

        while start_token < len(tokens):
            end_token = min(start_token + window_size, len(tokens))
            window_tokens = tokens[start_token:end_token]
            window_text = enc.decode(window_tokens)

            actual_start = token_char_offsets[start_token]
            raw_end = (
                token_char_offsets[end_token - 1] + len(enc.decode([tokens[end_token - 1]]))
                if end_token > start_token
                else len(text)
            )

            if window_text:
                segments.append(
                    {
                        "text": window_text,
                        "start_offset": actual_start,
                        "end_offset": raw_end,
                        "is_argumentative": None,
                    }
                )

            if end_token >= len(tokens):
                break
            start_token += window_size - overlap

        return segments
    except Exception:
        chunk_size = 1800
        overlap_chars = 400
        return [
            {
                "text": text[i : i + chunk_size],
                "start_offset": i,
                "end_offset": min(i + chunk_size, len(text)),
                "is_argumentative": None,
            }
            for i in range(0, len(text), chunk_size - overlap_chars)
        ]


def _get_token_char_offsets(enc, text: str, tokens: list[int]) -> list[int]:
    offsets = []
    current_pos = 0
    for t in tokens:
        offsets.append(current_pos)
        token_str = enc.decode([t])
        found = text.find(token_str, current_pos)
        if found != -1:
            current_pos = found + len(token_str)
        else:
            current_pos += len(token_str)
    return offsets
