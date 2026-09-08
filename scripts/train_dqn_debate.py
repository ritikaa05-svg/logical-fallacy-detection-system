#!/usr/bin/env python3
"""
Seed the debate DQN with behavior-cloning transitions derived from the
classification dataset.

IMPORTANT: This produces an *initialization* checkpoint, not a learned policy.
The v1.3 dataset is (text, fallacy_label) classification data — it contains no
real debate transitions. We synthesize (state, action, reward, next_state)
transitions by:
  1. deriving a DebateState from each sample (depth from word count,
     density/sentiment/logic from the fallacy label),
  2. labeling the action with the rule-based expert policy
     (`DQNAgent._rule_based_action`),
  3. using the expert's confidence as reward,
  4. projecting the next state with `_project_state`.

The resulting `models/dqn_debate_policy.pt` makes `model_loaded=True` so the
RL path is exercised, but it mostly clones the heuristic. Real learning
requires accumulated `debate_turns` rows (see `deployment/init-db.sql`) and a
training run over genuine interactions.

Usage (from repo root):
    PYTHONPATH=. venv/bin/python scripts/train_dqn_debate.py --steps 2000
"""

import argparse
import json
import logging
from pathlib import Path

import torch

from backend.app.config import settings
from backend.app.schemas.debate import DebateState
from backend.app.services.debate_service import DQNAgent, DebateService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Fallacious classes per the taxonomy used by the pipeline
NON_FALLACIOUS = {"valid_reasoning", "factual_statement"}


def derive_state(text: str, label: str) -> DebateState:
    """Derive a DebateState from a single classification sample."""
    word_count = len(text.split())
    if word_count < 20:
        depth = 1
    elif word_count < 50:
        depth = 2
    elif word_count < 100:
        depth = 3
    elif word_count < 200:
        depth = 4
    else:
        depth = 5

    if label in NON_FALLACIOUS:
        return DebateState(
            fallacy_density=0.0,
            argument_depth=depth,
            user_sentiment=0.5,
            logic_score=0.8,
        )

    sentiment = -0.5 if label in ("ad_hominem", "appeal_to_emotion") else 0.0
    return DebateState(
        fallacy_density=0.8,
        argument_depth=depth,
        user_sentiment=sentiment,
        logic_score=0.2,
    )


def build_transitions(agent: DQNAgent, service: DebateService, samples, limit: int) -> int:
    """Push behavior-cloned transitions into the replay buffer."""
    pushed = 0
    for sample in samples:
        if limit and pushed >= limit:
            break
        text = sample.get("text", "")
        label = sample.get("fallacy", "valid_reasoning")
        state = derive_state(text, label)
        action_idx, confidence = agent._rule_based_action(state)
        next_state = service._project_state(state, {0: "ASK_SOCRATIC", 1: "POINT_OUT_FALLACY", 2: "COUNTER_ARGUMENT", 3: "AGREE_AND_PIVOT"}[action_idx])
        service._store_experience(state, action_idx, confidence, next_state)
        pushed += 1
    return pushed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/unified_training_data_v1.3.json", help="Path to the classification dataset.")
    parser.add_argument("--steps", type=int, default=2000, help="Number of offline training steps.")
    parser.add_argument("--limit", type=int, default=0, help="Cap on samples used (0 = all).")
    parser.add_argument("--model-out", default=None, help="Output checkpoint path (default: settings.DQN_MODEL_PATH).")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"Dataset not found: {data_path}")

    with open(data_path) as f:
        samples = json.load(f)
    logger.info(f"Loaded {len(samples)} samples from {data_path}")

    # Fresh agent + service (service only used for _project_state/_store_experience)
    service = DebateService()
    agent = service.agent

    pushed = build_transitions(agent, service, samples, args.limit)
    logger.info(f"Pushed {pushed} transitions into replay buffer (size={len(agent.replay_buffer)})")

    losses = service.train_offline(args.steps)
    if not losses:
        logger.warning("No training steps executed (buffer below batch size?).")
        return

    model_out = args.model_out or settings.DQN_MODEL_PATH
    Path(model_out).parent.mkdir(parents=True, exist_ok=True)
    agent.save(model_out)
    logger.info(
        f"Seeded checkpoint saved to {model_out} — "
        f"avg_loss={sum(losses) / len(losses):.4f}, steps={len(losses)}, "
        f"epsilon={agent.epsilon:.3f}. NOTE: this is an initialization clone of "
        f"the rule-based policy, not a learned policy."
    )


if __name__ == "__main__":
    main()
