import json
import logging
import random

# Mocking app context for script execution
import sys
from datetime import datetime
from pathlib import Path

project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MULTITURN_TEMPLATES = {
    "moving_goalposts": [
        "user: Prove that this engine is efficient. [TURN] assistant: It has 40% thermal efficiency. [TURN] user: That's not enough, prove it can run for 100 hours without maintenance.",
        "user: Show me evidence of climate change. [TURN] assistant: Here are the global temperature records for 100 years. [TURN] user: Those are just averages, show me specific data for my backyard only.",
        "user: Can you prove you are a human? [TURN] assistant: I can pass a Turing test. [TURN] user: A machine could do that, prove you have a soul.",
        "user: Evidence for evolution? [TURN] assistant: The fossil record shows clear transitions. [TURN] user: Those are just 'gaps', show me a video of a species changing instantly.",
        "user: Is this supplement safe? [TURN] assistant: It passed all FDA safety trials. [TURN] user: Trials can be biased, show me a person who has taken it for 50 years with zero issues.",
    ],
    "no_true_scotsman": [
        "user: No scientist would believe in ghosts. [TURN] assistant: Dr. Smith is a scientist and he does. [TURN] user: Well, no TRUE scientist would believe in ghosts.",
        "user: Vegetarians don't eat meat. [TURN] assistant: My cousin is a vegetarian but eats chicken. [TURN] user: Then he's not a TRUE vegetarian.",
        "user: A good programmer always writes tests. [TURN] assistant: John is a great programmer but he rarely writes tests. [TURN] user: Well, no TRUE programmer would skip tests.",
        "user: No honest person would lie. [TURN] assistant: Even honest people tell white lies sometimes. [TURN] user: Then they aren't TRUE honest people.",
        "user: Citizens of this country love their flag. [TURN] assistant: I know many who are indifferent. [TURN] user: Those aren't TRUE citizens then.",
    ],
    "tu_quoque_contextual": [
        "assistant: Your argument uses anecdotal evidence. [TURN] user: Well, your last argument about the economy used an anecdote about your grandfather!",
        "assistant: You shouldn't interrupt when I'm speaking. [TURN] user: You interrupted me three times during lunch!",
        "assistant: It's important to cite your sources. [TURN] user: You didn't cite any sources in your previous presentation.",
        "assistant: Using logical fallacies weakens your point. [TURN] user: You used a straw man argument against me just five minutes ago!",
        "assistant: You are being quite emotional right now. [TURN] user: You were shouting during our meeting yesterday!",
    ],
}

VARIANTS = [
    "{text}",
    "user: Actually... [TURN] {text}",
    "assistant: I see. [TURN] {text}",
    "user: Wait a minute. [TURN] {text}",
    "assistant: Let's consider this. [TURN] {text}",
]


async def generate_multiturn_examples(fallacy_type: str, count: int = 20) -> list[str]:
    """Generate multi-turn examples using templates to bypass API issues."""
    base_examples = MULTITURN_TEMPLATES.get(fallacy_type, [])
    if not base_examples:
        return []

    results = []
    for _ in range(count):
        base = random.choice(base_examples)
        variant = random.choice(VARIANTS)
        results.append(variant.format(text=base))

    return list(set(results))


async def process_multiturn(fallacy_type: str, target_count: int = 500):
    """Generate examples for a single multi-turn fallacy type."""
    logger.info(f"🚀 Starting OFFLINE multi-turn generation for: {fallacy_type}")

    batch = await generate_multiturn_examples(fallacy_type, count=target_count)

    examples = []
    for text in batch:
        examples.append(
            {
                "text": text,
                "fallacy": fallacy_type,
                "source": "template_multiturn_v1",
                "metadata": {
                    "generation_date": datetime.now().isoformat(),
                    "is_multiturn": True,
                    "verification_status": "template_verified",
                },
            }
        )

    # Save results
    output_dir = Path("data/synthetic_multiturn")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{fallacy_type}.json"

    with open(output_path, "w") as f:
        json.dump(examples, f, indent=2)

    logger.info(f"✅ Saved {len(examples)} multi-turn examples to {output_path}")


async def main():
    for fallacy in MULTITURN_TEMPLATES.keys():
        await process_multiturn(fallacy, target_count=100)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
