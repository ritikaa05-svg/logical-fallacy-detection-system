import argparse
import asyncio
import json

from backend.app.services.llm_service import llm_synthesis_service


async def generate_structured_hard_negative(target_class, batch_size):
    samples = []
    # Prompt for structured reasoning
    prompt = (
        f"Generate a logically valid argument that avoids fallacy, specifically in the domain of {target_class}.\n"
        "Output ONLY in this JSON format:\n"
        "{\n"
        '  "reasoning_type": "[e.g., causal, statistical, policy, scientific, practical]",\n'
        '  "premise_1": "...",\n'
        '  "premise_2": "...",\n'
        '  "conclusion": "...",\n'
        '  "validity_explanation": "..."\n'
        "}"
    )

    for _ in range(batch_size):
        try:
            # Use generation service
            resp = await llm_synthesis_service._generate_with_fallback(prompt, max_new_tokens=250)
            # Basic cleanup if model echoes prompt
            json_str = resp.replace("```json", "").replace("```", "").strip()
            data = json.loads(json_str)

            # Combine to natural language text
            text = f"{data['premise_1']} {data['premise_2']} Therefore, {data['conclusion']}"

            samples.append({"text": text, "fallacy": "none", "source": "structured_hard_negative", "metadata": data})
        except Exception as e:
            print(f"Generation failed: {e}")

    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-class", default="everyday")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--output-file", default="data/expansion_batch.json")
    args = parser.parse_args()

    data = asyncio.run(generate_structured_hard_negative(args.target_class, args.batch_size))

    with open(args.output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generated {len(data)} structured samples to {args.output_file}")


if __name__ == "__main__":
    main()
