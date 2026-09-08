import logging

from transformers import AutoModelForSequenceClassification, AutoTokenizer

from backend.app.services.explainability import compute_attributions

# Setup logging
logging.basicConfig(level=logging.INFO)


def test_xai_offsets():
    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)

    text = "Scientists say scientists should trust scientists."
    # "scientists" appears at indices 0, 14, 39

    # Mock model and target_class
    target_class = 0

    print(f"Testing text: {text}")
    attributions = compute_attributions(model, tokenizer, text, target_class)

    scientists_indices = []
    for attr in attributions:
        if attr["token"].lower() == "scientists":
            scientists_indices.append(attr["start"])
            print(f"Found token '{attr['token']}' at index {attr['start']}")

    # We expect 3 distinct indices: 0, 14, 39 (approximately)
    unique_indices = set(scientists_indices)
    print(f"Unique indices found: {unique_indices}")

    if len(unique_indices) < 3:
        print("FAIL: Duplicate tokens mapped to the same index.")
    else:
        print("PASS: Duplicate tokens mapped to distinct indices.")


if __name__ == "__main__":
    test_xai_offsets()
