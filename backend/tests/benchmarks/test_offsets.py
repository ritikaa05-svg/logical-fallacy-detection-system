import os
import sys

import pytest

# Add project root and backend to path
sys.path.append(os.getcwd())

from backend.app.pipeline.orchestrator import PipelineOrchestrator


@pytest.fixture
def orchestrator():
    return PipelineOrchestrator()


@pytest.mark.asyncio
async def test_single_sentence_offsets(orchestrator):
    text = "This is a straw man argument because you are misrepresenting my position."
    res = await orchestrator.analyze(text, skip_cache=True, include_explanations=True)

    # Verify highlighting offsets
    for ann in res.annotations:
        for span in ann.spans:
            actual = text[span.start : span.end]
            assert span.text.lower() in actual.lower()


@pytest.mark.asyncio
async def test_multiline_offsets(orchestrator):
    text = """Line one is factual.
    Line two contains a fallacy.
    Therefore, the whole thing is wrong."""
    res = await orchestrator.analyze(text, skip_cache=True, include_explanations=True)

    for ann in res.annotations:
        for span in ann.spans:
            actual = text[span.start : span.end]
            assert span.text.lower() in actual.lower()


@pytest.mark.asyncio
async def test_history_prefix_offsets(orchestrator):
    history = [{"role": "user", "content": "I like cats."}, {"role": "assistant", "content": "Cats are okay."}]
    current_text = "But you hate dogs, which means you are a bad person."

    res = await orchestrator.analyze(current_text, history=history, skip_cache=True, include_explanations=True)

    print("\nDebug History Prefix:")
    print(f"  Current Text: '{current_text}'")

    # Verify that offsets in 'res' correctly map to 'current_text', NOT the full history-prefixed text
    for ann in res.annotations:
        print(f"  Annotation: '{ann.sentence}' ({ann.sentence_start}:{ann.sentence_end})")
        for span in ann.spans:
            actual = current_text[span.start : span.end]
            print(f"    Span: '{span.text}' ({span.start}:{span.end}) -> Actual from text: '{actual}'")
            assert span.text.lower() in actual.lower()

    # Verify salient tokens also map correctly
    for token in res.salient_tokens:
        actual = current_text[token["start"] : token["end"]]
        # Some tokens might be subwords, so we check if clean version matches
        clean_token = token["token"].replace("##", "").replace("Ġ", "").lower()
        assert clean_token in actual.lower()


@pytest.mark.asyncio
async def test_long_conversation_offsets(orchestrator):
    history = [{"role": "user", "content": "Word " * 50}] * 5  # Very long history
    current_text = "This is a fallacy because everyone knows it."

    res = await orchestrator.analyze(current_text, history=history, skip_cache=True, include_explanations=True)

    for ann in res.annotations:
        for span in ann.spans:
            actual = current_text[span.start : span.end]
            assert span.text.lower() in actual.lower()


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        orch = PipelineOrchestrator()
        print("Testing Single Sentence...")
        await test_single_sentence_offsets(orch)
        print("Testing Multiline...")
        await test_multiline_offsets(orch)
        print("Testing History Prefix...")
        await test_history_prefix_offsets(orch)
        print("Testing Long Conversation...")
        await test_long_conversation_offsets(orch)
        print("✅ All Offset Validation Tests PASSED.")

    asyncio.run(run_tests())
