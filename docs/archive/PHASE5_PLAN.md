# Phase 5: Argument Intelligence — Implementation Plan

## Overview
Phase 5 shifts the focus from simple fallacy classification to deep structural analysis and reasoning validation. The goal is to move from "This is a Straw Man" to "This argument fails because Premise A does not support Conclusion B in the following way..."

## 1. Structural Extraction Engine
- **Premise Extraction**: Identify specific claims acting as premises.
- **Conclusion Extraction**: Identify the primary claim being supported.
- **Logic Mapping**: Determine the intended relationship (deductive, inductive, etc.).

## 2. Reasoning Validation
- **Symbolic Verification (Z3)**: Enhance the LLM-to-SMT translator to handle more complex argument structures.
- **Counter-Example Generation**: If an argument is invalid, generate a concrete counter-example where premises are true but conclusion is false.

## 3. Advanced Explanation Generation
- **Structure-Aware Explanations**: Use the extracted premises and conclusion to explain the logical gap.
- **Correction Strategies**: Suggest how the argument could be made valid or strengthened.

## 4. Evaluation & Benchmarking
- **Logic-F1**: A new metric for measuring the accuracy of premise/conclusion extraction.
- **Human-in-the-Loop Audit**: Expert review of the generated logical structures.

## 5. Technical Stack
- **Models**: Fine-tuned DeBERTa-v3 or Llama-3 (8B) for extraction.
- **Formalism**: SMT-LIBv2 / Z3.
- **Integration**: Async pipeline stage 5 (Synthesis).
