"""
LogiScan — Robust Attribution Engine
Handles Integrated Gradients with defensive fallbacks for missing offsets or gradients.
"""

import logging
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


def compute_attributions(
    model: torch.nn.Module, tokenizer: Any, text: str, target_class: int, n_steps: int = 20
) -> list[dict[str, Any]]:
    """
    Computes Integrated Gradients.
    Defensively handles DeBERTa/RoBERTa architectures and missing offset_mapping.
    """
    try:
        # Force gradients enabled
        with torch.enable_grad():
            device = next(model.parameters()).device

            # 1. Tokenize (Defensive about Fast Tokenizers)
            inputs = tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
                return_offsets_mapping=True,  # May be None if slow tokenizer
            )

            # Safely move to device
            if hasattr(inputs, "to"):
                inputs = inputs.to(device)
            else:
                inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}

            input_ids = inputs["input_ids"]
            attention_mask = inputs["attention_mask"]
            offset_mapping = inputs.get("offset_mapping")
            if offset_mapping is not None:
                if torch.is_tensor(offset_mapping):
                    offset_mapping = offset_mapping[0].cpu().numpy()
                else:
                    offset_mapping = np.array(offset_mapping[0])

            # 2. Find Embeddings Layer
            embedding_layer = None
            for name, module in model.named_modules():
                if any(term in name for term in ["word_embeddings", "wte", "embeddings.word_embeddings"]):
                    embedding_layer = module
                    break

            if embedding_layer is None:
                return []

            # 3. Baseline & Interpolation
            input_embeddings = embedding_layer(input_ids).detach()
            baseline_embeddings = torch.zeros_like(input_embeddings)

            alphas = torch.linspace(0, 1, n_steps).view(-1, 1, 1, 1).to(device)
            interpolated = baseline_embeddings + alphas * (input_embeddings - baseline_embeddings)
            interpolated.requires_grad_(True)

            # 4. Gradient Loop
            all_grads = []
            model.eval()  # Still need eval mode for batchnorm/dropout

            for i in range(n_steps):
                model.zero_grad()

                # Handle model forward paths
                if hasattr(model, "deberta"):
                    outputs = model.deberta(inputs_embeds=interpolated[i], attention_mask=attention_mask)
                    # Support LogiScan's MultiHead Pooler
                    cls_output = outputs.last_hidden_state[:, 0, :]
                    if hasattr(model, "pooler"):
                        pooled = model.pooler_activation(model.pooler(cls_output))
                        logits = model.fine_head(pooled) if hasattr(model, "fine_head") else model.classifier(pooled)
                    else:
                        logits = model.classifier(cls_output)
                elif hasattr(model, "roberta"):
                    outputs = model.roberta(inputs_embeds=interpolated[i], attention_mask=attention_mask)
                    logits = model.classifier(outputs[0])
                else:
                    outputs = model(inputs_embeds=interpolated[i], attention_mask=attention_mask)
                    logits = outputs.logits if hasattr(outputs, "logits") else outputs[0]

                probs = F.softmax(logits, dim=-1)

                # Boundary check for target_class
                if target_class >= probs.shape[1]:
                    target_class = probs.argmax().item()

                score = probs[0, target_class]
                score.backward(retain_graph=True)

                if interpolated.grad is not None:
                    all_grads.append(interpolated.grad[i].detach())
                    interpolated.grad.zero_()
                else:
                    all_grads.append(torch.zeros_like(input_embeddings[0]))

            if not all_grads:
                return []

            # 5. Integrate & Normalize
            avg_grads = torch.stack(all_grads).mean(dim=0)
            if avg_grads.dim() == 3:
                avg_grads = avg_grads[0]

            attributions = (input_embeddings[0] - baseline_embeddings[0]) * avg_grads
            token_scores = attributions.sum(dim=-1).detach().cpu().numpy()

            # Ensure token_scores is 1D
            if token_scores.ndim > 1:
                token_scores = token_scores.flatten()

            # Normalize to [0, 1]
            token_scores = np.abs(token_scores)
            if np.max(token_scores) > 0:
                token_scores = token_scores / np.max(token_scores)

            # 6. Map back to characters
            tokens = tokenizer.convert_ids_to_tokens(input_ids[0])
            result = []
            curr_char_pos = 0

            # DEFENSIVE: Only use offset_mapping if it contains non-zero data
            # Slow tokenizers might return a dummy mapping of all zeros
            use_offsets = False
            if offset_mapping is not None:
                if np.any(offset_mapping > 0):
                    use_offsets = True

            for idx, (token, score) in enumerate(zip(tokens, token_scores)):
                if token in tokenizer.all_special_tokens:
                    continue

                # Fix Bug: Handle missing or invalid offset_mapping via robust search
                if use_offsets:
                    start, end = offset_mapping[idx]
                    if start == end == 0:
                        continue
                else:
                    # ROBUST FALLBACK: Track character position to handle repeated tokens
                    # Normalize token for searching (remove subword markers and spaces)
                    clean_token = (
                        token.replace("##", "").replace("Ġ", " ").replace("\u2581", " ").replace(" ", " ").strip()
                    )
                    if not clean_token:
                        logger.debug("Skipping empty clean_token for: %s", token)
                        continue

                    # CASE-INSENSITIVE SEARCH: Find token starting from curr_char_pos
                    # We search in a case-insensitive way because uncased tokenizers
                    # will produce lowercase tokens for cased text.
                    text_lower = text.lower()
                    token_lower = clean_token.lower()

                    start = text_lower.find(token_lower, curr_char_pos)

                    if start == -1:
                        # If not found ahead, maybe it's slightly mis-tokenized or
                        # part of a word that was already partially matched.
                        # As a last resort, try from start, but this should be rare.
                        start = text_lower.find(token_lower)

                    if start != -1:
                        end = start + len(clean_token)
                        # Only update curr_char_pos if we actually moved forward
                        if end > curr_char_pos:
                            curr_char_pos = end
                    else:
                        continue

                result.append({"token": token, "score": float(score), "start": int(start), "end": int(end)})
            return result

    except Exception as e:
        logger.error(f"compute_attributions critical failure: {e}")
        return []


def get_top_spans(
    salient_tokens: list[dict[str, Any]], threshold: float = 0.15, max_spans: int = 10
) -> list[dict[str, Any]]:
    """Groups tokens into highlightable spans."""
    if not salient_tokens:
        return []

    candidates = sorted([t for t in salient_tokens if t["score"] >= threshold], key=lambda x: x["start"])
    if not candidates:
        return []

    spans = []
    curr = {
        "text": candidates[0]["token"],
        "start": candidates[0]["start"],
        "end": candidates[0]["end"],
        "saliency": candidates[0]["score"],
    }

    for i in range(1, len(candidates)):
        t = candidates[i]
        if t["start"] <= curr["end"] + 2:  # Merge close tokens
            curr["end"] = t["end"]
            curr["saliency"] = max(curr["saliency"], t["score"])
        else:
            spans.append(curr)
            curr = {"text": t["token"], "start": t["start"], "end": t["end"], "saliency": t["score"]}
    spans.append(curr)

    # Return top N by saliency
    return sorted(spans, key=lambda x: x["saliency"], reverse=True)[:max_spans]


def get_sentence_context(text: str, char_idx: int) -> tuple[str, int, int]:
    """Finds sentence boundaries."""
    import re

    sentences = list(re.finditer(r"[^.!?]+[.!?]*", text))
    for m in sentences:
        if m.start() <= char_idx < m.end():
            return m.group().strip(), m.start(), m.end()
    return text, 0, len(text)
