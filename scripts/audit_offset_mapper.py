import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import OffsetMapper
from backend.app.schemas.inference import FallacyAnnotation, SpanAnnotation


def test_offset_mapper():
    print("🚀 Auditing OffsetMapper Integrity...")

    # Simulate multiturn history prefix
    history_prefix = "user: Hello. assistant: Hi. current: "
    prefix_len = len(history_prefix)
    mapper = OffsetMapper(prefix_len)

    original_text = "All humans are mortal."
    # The analyzer sees the prefixed text
    history_prefix + original_text

    # 1. Test Salient Token Mapping
    # 'humans' in 'analysis_text' starts at index prefix_len + 4
    # ends at prefix_len + 10
    raw_tokens = [{"token": "humans", "score": 0.9, "start": prefix_len + 4, "end": prefix_len + 10}]

    # Deep copy for print comparison
    import copy

    raw_copy = copy.deepcopy(raw_tokens)

    remapped_tokens = mapper.remap_salient(raw_tokens)

    print(f"\nSalient Token Mapping (Prefix len: {prefix_len}):")
    print(f"  Raw:      {raw_copy[0]['start']}:{raw_copy[0]['end']}")
    print(f"  Remapped: {remapped_tokens[0]['start']}:{remapped_tokens[0]['end']}")

    # Verify alignment in original text
    extracted = original_text[remapped_tokens[0]["start"] : remapped_tokens[0]["end"]]
    print(f"  Extracted from original: '{extracted}'")
    assert extracted == "humans"

    # 2. Test Annotation Mapping
    ann = FallacyAnnotation(
        type="ad_hominem",
        label="Ad Hominem",
        confidence=0.8,
        definition="...",
        explanation="...",
        sentence="All humans are mortal.",
        sentence_start=prefix_len,
        sentence_end=prefix_len + len(original_text),
        spans=[SpanAnnotation(text="humans", start=prefix_len + 4, end=prefix_len + 10, saliency=1.0)],
    )

    remapped_anns = mapper.remap_annotations([ann])
    ra = remapped_anns[0]

    print("\nAnnotation Mapping:")
    print(f"  Sentence: {ra.sentence_start}:{ra.sentence_end}")
    print(f"  Span:     {ra.spans[0].start}:{ra.spans[0].end}")

    # Verify alignment
    sent_text = original_text[ra.sentence_start : ra.sentence_end]
    span_text = original_text[ra.spans[0].start : ra.spans[0].end]
    print(f"  Sentence from original: '{sent_text}'")
    print(f"  Span from original:     '{span_text}'")

    assert sent_text == "All humans are mortal."
    assert span_text == "humans"

    print("\n✅ OffsetMapper Audit PASSED.")


if __name__ == "__main__":
    test_offset_mapper()
