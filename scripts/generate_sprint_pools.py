#!/usr/bin/env python3
import json
import os

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from tqdm import tqdm


class FallacySample(BaseModel):
    text: str = Field(description="The realistic, nuanced natural language argument containing the fallacy.")
    fallacy: str = Field(description="The exact snake_case identifier of the fallacy category.")
    source: str = Field(default="synthetic_boost_sprint")


class FallacyBatch(BaseModel):
    samples: list[FallacySample]


OUTPUT_DIR = "data/raw_generation_pools/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

QUOTAS = {
    "straw_man": 482,
    "affirming_consequent": 461,
    "begging_the_question": 439,
    "false_cause": 301,
    "ad_hominem": 206,
    "appeal_to_emotion": 206,
}

DOMAINS = [
    "Corporate Tech & Workplace Decisions",
    "Healthcare, Medical Policy & Bioethics",
    "Climate Change, Energy & Environmental Debates",
    "Software Engineering, Code Reviews & Architecture",
    "E-commerce, Consumer Reviews & Marketing Claims",
    "Public Policy, Education & Municipal Governance",
]


def load_seed_examples(fallacy_type: str, limit: int = 3) -> str:
    try:
        with open("data/merged_fallacies.json", encoding="utf-8") as f:
            data = json.load(f)
        matches = [item["text"] for item in data if item.get("fallacy") == fallacy_type]
        seeds = matches[:limit]
        if not seeds:
            return "No baseline seed found."
        return "\n".join([f'- Seed Example: "{text}"' for text in seeds])
    except FileNotFoundError:
        return "Baseline file not found. Falling back to zero-shot."


def generate_fallacy_pools():
    client = genai.Client()
    print("🚀 Starting LogiScan Data Sourcing Session via Gemini...")

    for fallacy_type, total_needed in QUOTAS.items():
        print(f"\n🎯 Processing target: {fallacy_type} (Needs {total_needed} samples)")
        seed_context = load_seed_examples(fallacy_type, limit=3)
        chunk_size = 25
        chunks = (total_needed // chunk_size) + (1 if total_needed % chunk_size != 0 else 0)
        all_generated_for_class = []

        for i in tqdm(range(chunks), desc=f"Generating {fallacy_type}"):
            current_domain = DOMAINS[i % len(DOMAINS)]
            samples_to_request = min(chunk_size, total_needed - len(all_generated_for_class))

            prompt = f"Generate {samples_to_request} unique examples of {fallacy_type} for the domain: {current_domain}. Use these seeds as guides:\n{seed_context}"

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", response_schema=FallacyBatch, temperature=0.85
                    ),
                )
                batch_data = json.loads(response.text)
                all_generated_for_class.extend(batch_data.get("samples", []))
            except Exception as e:
                print(f"\n⚠️ Error generating batch {i}: {e}")
                continue

        output_file = os.path.join(OUTPUT_DIR, f"raw_{fallacy_type}_pool.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_generated_for_class, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved {len(all_generated_for_class)} records to {output_file}")


if __name__ == "__main__":
    generate_fallacy_pools()
