from unittest.mock import MagicMock, patch

import torch

from backend.app.services.explainability import compute_attributions


def test_compute_attributions_mapping_logic():
    """Verify the sequential character mapping logic directly."""
    from backend.app.services.explainability import compute_attributions

    tokenizer = MagicMock()
    tokens = ["[CLS]", "scientists", "say", "scientists", "should", "trust", "scientists", ".", "[SEP]"]
    tokenizer.convert_ids_to_tokens.return_value = tokens
    tokenizer.all_special_tokens = ["[CLS]", "[SEP]", "[PAD]"]

    # Mock inputs to trigger fallback (no offset_mapping)
    inputs = {
        "input_ids": torch.zeros((1, len(tokens)), dtype=torch.long),
        "attention_mask": torch.ones((1, len(tokens))),
    }
    tokenizer.return_value = inputs

    model = MagicMock(spec=torch.nn.Module)
    embedding_layer = MagicMock()
    model.named_modules.return_value = [("embeddings.word_embeddings", embedding_layer)]
    embedding_layer.return_value = torch.zeros((1, len(tokens), 768))

    # Mock device
    device = torch.device("cpu")
    model.parameters.return_value = iter([torch.tensor([0.0]).to(device)])

    # We patch the components that do the math to return what we want
    # so we can test the loop at the end of compute_attributions.
    with (
        patch("torch.linspace") as mock_linspace,
        patch("torch.stack") as mock_stack,
        patch("torch.nn.functional.softmax") as mock_softmax,
    ):
        mock_linspace.return_value = torch.zeros((2, 1, 1, 1))
        mock_stack.return_value = torch.zeros((2, len(tokens), 768))

        # Softmax returns score for target_class
        mock_softmax.return_value = torch.ones((1, 2))

        # We also need to mock the interpolation and backward behavior or just the final attributions
        # It's easier to mock the whole compute_attributions and just call the mapping logic if it were separate,
        # but it's not. Let's try to mock the specific problematic score.backward()

        with patch("torch.Tensor.backward"):
            text = "Scientists say scientists should trust scientists."
            target_class = 0

            result = compute_attributions(model, tokenizer, text, target_class, n_steps=2)

    # Extract indices for "scientists"
    scientists_indices = [r["start"] for r in result if r["token"] == "scientists"]

    # We expect 3 distinct indices if the sequential search works
    assert len(scientists_indices) == 3
    assert len(set(scientists_indices)) == 3
    assert scientists_indices[0] == 0
    assert 10 < scientists_indices[1] < 20
    assert 35 < scientists_indices[2] < 45


def test_compute_attributions_with_offsets():
    """Verify that offset_mapping is used correctly when available."""
    tokenizer = MagicMock()
    tokens = ["[CLS]", "hello", "[SEP]"]
    tokenizer.convert_ids_to_tokens.return_value = tokens
    tokenizer.all_special_tokens = ["[CLS]", "[SEP]"]

    # Mock offset_mapping
    offsets = torch.tensor([[[0, 0], [0, 5], [0, 0]]])
    inputs = {
        "input_ids": torch.zeros((1, 3), dtype=torch.long),
        "attention_mask": torch.ones((1, 3)),
        "offset_mapping": offsets,
    }
    tokenizer.return_value = inputs

    model = MagicMock(spec=torch.nn.Module)
    embedding_layer = MagicMock()
    model.named_modules.return_value = [("embeddings.word_embeddings", embedding_layer)]
    embedding_layer.return_value = torch.zeros((1, 3, 768))

    mock_output = MagicMock()
    mock_output.logits = torch.zeros((1, 2))
    model.return_value = mock_output

    # Mock device
    device = torch.device("cpu")
    model.parameters.return_value = iter([torch.tensor([0.0]).to(device)])

    with (
        patch("torch.linspace") as mock_linspace,
        patch("torch.stack") as mock_stack,
        patch("torch.nn.functional.softmax") as mock_softmax,
        patch("torch.Tensor.backward"),
    ):
        mock_linspace.return_value = torch.zeros((2, 1, 1, 1)).to(device)
        mock_stack.return_value = torch.zeros((2, 3, 768)).to(device)
        mock_softmax.return_value = torch.ones((1, 2)).to(device)

        text = "hello"
        result = compute_attributions(model, tokenizer, text, 0, n_steps=2)

    assert len(result) == 1
    assert result[0]["token"] == "hello"
    assert result[0]["start"] == 0
    assert result[0]["end"] == 5
