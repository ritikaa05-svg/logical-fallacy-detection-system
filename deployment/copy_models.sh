#!/bin/bash
# Run this BEFORE building Docker to ensure models are in context
mkdir -p ../models_docker

# Copy only the config + tokenizer files (weights will download on first run if needed)
for model in stage1_v12 stage3_v13_classifier; do
    if [ -d "../models/$model" ]; then
        echo "Copying $model..."
        mkdir -p "../models_docker/$model"
        cp ../models/$model/config.json ../models_docker/$model/ 2>/dev/null || true
        cp ../models/$model/tokenizer* ../models_docker/$model/ 2>/dev/null || true
        cp ../models/$model/vocab* ../models_docker/$model/ 2>/dev/null || true
        cp ../models/$model/special_tokens* ../models_docker/$model/ 2>/dev/null || true
    fi
done

echo "Models prepared in models_docker/"
