import os
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def export_onnx(model_path, output_path):
    print(f"Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path,
        local_files_only=True,
        ignore_mismatched_sizes=True
    )
    model.eval()

    # Move to CPU for export
    model.to("cpu")

    dummy_input_text = "This is a sample text for ONNX export."
    inputs = tokenizer(
        dummy_input_text,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=512
    )

    input_names = ["input_ids", "attention_mask"]
    output_names = ["logits"]

    dynamic_axes = {
        "input_ids": {0: "batch_size", 1: "sequence_length"},
        "attention_mask": {0: "batch_size", 1: "sequence_length"},
        "logits": {0: "batch_size"}
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Exporting to {output_path}...")
    torch.onnx.export(
        model,
        (inputs["input_ids"], inputs["attention_mask"]),
        output_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes
    )
    print("Export complete.")

    # Verification
    print("Verifying ONNX model...")
    ort_session = ort.InferenceSession(output_path)

    onnx_inputs = {
        "input_ids": inputs["input_ids"].numpy(),
        "attention_mask": inputs["attention_mask"].numpy()
    }

    ort_outs = ort_session.run(None, onnx_inputs)

    with torch.no_grad():
        torch_outs = model(inputs["input_ids"], inputs["attention_mask"])

    np.testing.assert_allclose(torch_outs.logits.numpy(), ort_outs[0], rtol=1e-03, atol=1e-05)
    print("Verification successful!")

    # Copy config and labels
    config_src = Path(model_path) / "config.json"
    config_dst = Path(os.path.dirname(output_path)) / "config.json"
    if config_src.exists():
        import shutil
        if config_src.resolve() != config_dst.resolve():
            shutil.copy(config_src, config_dst)
            print(f"Copied config to {config_dst}")
        else:
            print("Config src and dst are the same file, skipping copy.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, default="models/stage1_v13_classifier")
    parser.add_argument("--output_path", type=str, default="models/phase4_onnx/model.onnx")
    args = parser.parse_args()

    export_onnx(args.model_path, args.output_path)
