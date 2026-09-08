"""
RL Debate Engine Service
Implements a DQN-based debate agent that learns to improve logical discourse.
Supports offline training from PostgreSQL debate logs.
"""

import logging
import random
import uuid
from collections import deque

import torch
import torch.nn as nn
import torch.nn.functional as F

from backend.app.config import settings
from backend.app.pipeline.orchestrator import pipeline_orchestrator
from backend.app.schemas.debate import (
    DebateAction,
    DebateSession,
    DebateState,
    DebateTurn,
)

logger = logging.getLogger(__name__)

# Action definitions
ACTION_MAP = {
    0: "ASK_SOCRATIC",
    1: "POINT_OUT_FALLACY",
    2: "COUNTER_ARGUMENT",
    3: "AGREE_AND_PIVOT",
}

ACTION_TO_INDEX = {v: k for k, v in ACTION_MAP.items()}

# Intent detection
GREETINGS = {
    "hello", "hi", "hey", "greetings", "good morning", "good afternoon",
    "good evening", "whats up", "what's up", "sup", "yo", "hiya", "howdy",
}
QUESTION_LEADS = (
    "what", "why", "how", "can", "could", "does", "do", "is", "are",
    "would", "should", "who", "where", "when", "which", "did", "will",
)
ACK_PHRASES = {
    "maybe", "ok", "okay", "yes", "no", "yep", "nope", "idk", "i see",
    "sure", "alright", "fine", "hmm", "interesting", "got it",
    "makes sense", "right", "exactly", "true",
}


class DQN(nn.Module):
    """
    Deep Q-Network with dueling architecture for debate action selection.

    Input: State vector [fallacy_density, argument_depth, user_sentiment, logic_score]
    Output: Q-values for 4 possible debate actions
    """

    def __init__(self, state_dim: int = 4, action_dim: int = 4, hidden_dim: int = 128):
        super().__init__()

        # Shared feature extractor
        self.feature_layer = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Dueling architecture: separate value and advantage streams
        self.value_stream = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        features = self.feature_layer(state)

        value = self.value_stream(features)
        advantages = self.advantage_stream(features)

        # Q(s, a) = V(s) + (A(s, a) - mean(A(s, a)))
        q_values = value + (advantages - advantages.mean(dim=1, keepdim=True))

        return q_values


class ReplayBuffer:
    """Fixed-size replay buffer for experience replay."""

    def __init__(self, capacity: int = 10000):
        self.buffer: deque = deque(maxlen=capacity)

    def push(
        self,
        state: torch.Tensor,
        action: int,
        reward: float,
        next_state: torch.Tensor,
        done: bool,
    ) -> None:
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> list:
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        return batch

    def __len__(self) -> int:
        return len(self.buffer)


class DQNAgent:
    """
    DQN agent with epsilon-greedy exploration for debate action selection.
    """

    def __init__(
        self,
        state_dim: int = 4,
        action_dim: int = 4,
        gamma: float | None = None,
        epsilon_start: float | None = None,
        epsilon_end: float | None = None,
        epsilon_decay: float | None = None,
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Hyperparameters
        self.gamma = gamma or settings.RL_GAMMA
        self.epsilon = epsilon_start or settings.RL_EPSILON_START
        self.epsilon_end = epsilon_end or settings.RL_EPSILON_END
        self.epsilon_decay = epsilon_decay or settings.RL_EPSILON_DECAY

        # Networks
        self.policy_net = DQN(state_dim, action_dim)
        self.target_net = DQN(state_dim, action_dim)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        # Optimizer
        self.optimizer = torch.optim.Adam(self.policy_net.parameters(), lr=1e-4)

        # Replay buffer
        self.replay_buffer = ReplayBuffer(capacity=settings.RL_REPLAY_BUFFER_SIZE)

        # Training tracking
        self.training_steps = 0
        self.batch_size = 64
        self.model_loaded = False

        logger.info(
            f"DQNAgent initialized: gamma={self.gamma}, "
            f"epsilon={self.epsilon:.3f}, buffer_size={settings.RL_REPLAY_BUFFER_SIZE}"
        )

    @staticmethod
    def _rule_based_action(state: DebateState) -> tuple[int, float]:
        """
        Heuristic action selection when no trained DQN model is available.
        Uses state features to pick sensible debate actions.
        """
        fd = state.fallacy_density
        ls = state.logic_score
        us = state.user_sentiment

        if fd > 0.5 or ls < 0.3:
            return 1, 0.8  # POINT_OUT_FALLACY
        if us < -0.2:
            return 0, 0.7  # ASK_SOCRATIC (de-escalate)
        if ls > 0.7 and fd < 0.2:
            return 3, 0.7  # AGREE_AND_PIVOT
        return 0, 0.6  # ASK_SOCRATIC (default: probe deeper)

    def select_action(self, state: DebateState, training: bool = False) -> tuple[int, float]:
        """
        Select action using epsilon-greedy policy.

        Args:
            state: Current debate state
            training: If True, use epsilon-greedy. If False, always greedy.

        Returns:
            Tuple of (action_index, confidence_score)
        """
        if not self.model_loaded:
            return self._rule_based_action(state)

        state_tensor = torch.FloatTensor(state.to_tensor()).unsqueeze(0)

        with torch.no_grad():
            q_values = self.policy_net(state_tensor)
            probs = F.softmax(q_values, dim=1)

            if training and random.random() < self.epsilon:
                action = random.randrange(self.action_dim)
                confidence = probs[0, action].item()
            else:
                action = q_values.argmax(dim=1).item()
                confidence = probs[0, action].item()

        return action, confidence

    def update_epsilon(self) -> None:
        """Decay epsilon after each episode."""
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

    def train_step(self) -> float | None:
        """Perform one training step from replay buffer."""
        if len(self.replay_buffer) < self.batch_size:
            return None

        batch = self.replay_buffer.sample(self.batch_size)

        states, actions, rewards, next_states, dones = zip(*batch)

        states = torch.stack(states)
        actions = torch.tensor(actions).unsqueeze(1)
        rewards = torch.tensor(rewards).unsqueeze(1)
        next_states = torch.stack(next_states)
        dones = torch.tensor(dones).unsqueeze(1).float()

        # Current Q values
        current_q = self.policy_net(states).gather(1, actions)

        # Target Q values (Double DQN)
        with torch.no_grad():
            next_actions = self.policy_net(next_states).argmax(dim=1, keepdim=True)
            next_q = self.target_net(next_states).gather(1, next_actions)
            target_q = rewards + self.gamma * next_q * (1 - dones)

        # Loss
        loss = F.smooth_l1_loss(current_q, target_q)

        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 10.0)
        self.optimizer.step()

        # Update target network periodically
        self.training_steps += 1
        if self.training_steps % 100 == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        return loss.item()

    def save(self, path: str) -> None:
        """Save model checkpoint."""
        torch.save(
            {
                "policy_net": self.policy_net.state_dict(),
                "target_net": self.target_net.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "epsilon": self.epsilon,
                "training_steps": self.training_steps,
            },
            path,
        )
        logger.info(f"DQN model saved to {path}")

    def load(self, path: str) -> bool:
        """Load model checkpoint."""
        try:
            checkpoint = torch.load(path, map_location="cpu")
            self.policy_net.load_state_dict(checkpoint["policy_net"])
            self.target_net.load_state_dict(checkpoint["target_net"])
            self.optimizer.load_state_dict(checkpoint["optimizer"])
            self.epsilon = checkpoint["epsilon"]
            self.training_steps = checkpoint["training_steps"]
            self.model_loaded = True
            logger.info(f"DQN model loaded from {path}")
            return True
        except FileNotFoundError:
            logger.warning(f"No saved model found at {path}. Using untrained agent.")
            return False
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False


class DebateService:
    """
    RL-powered debate engine that engages users in logical discourse.

    Maintains debate sessions, selects strategic actions via DQN,
    and generates responses using the LogiScan pipeline analysis.
    """

    # Reward function weights
    REWARD_W_CLARITY = 5.0
    REWARD_W_LOGIC = 3.0
    REWARD_W_REPETITION = -2.0

    def __init__(self):
        self.agent = DQNAgent()
        self.sessions: dict[str, DebateSession] = {}
        self._last_actions: dict[str, str] = {}  # Track for repetition penalty
        self._used_templates: dict[str, set[str]] = {}  # Per-session template de-dup
        self._logger = None  # Lazy best-effort debate logger

        # Try to load pre-trained model
        self.agent.load(settings.DQN_MODEL_PATH)

        logger.info("DebateService initialized.")

    # --- Intent detection ---------------------------------------------------

    @staticmethod
    def _detect_intent(user_input: str) -> str | None:
        """
        Classify the user's message before running the full fallacy pipeline.

        Returns "greeting", "question", "ack", or None (a real argument).
        """
        cleaned = user_input.lower().strip().rstrip("!?.")
        tokens = cleaned.split()

        if cleaned in GREETINGS:
            return "greeting"
        if cleaned.endswith("?") or any(cleaned.startswith(w) for w in QUESTION_LEADS):
            return "question"
        if len(tokens) <= 3 and cleaned in ACK_PHRASES:
            return "ack"
        return None

    # --- Core turn flow -----------------------------------------------------

    async def start_or_continue(
        self,
        user_input: str,
        session_id: str | None = None,
    ) -> DebateTurn:
        """
        Process a debate turn: analyze input, select action, generate response.

        Args:
            user_input: User's argument text
            session_id: Existing session to continue, or None for new session

        Returns:
            DebateTurn with analysis, action, and response
        """
        # Create or retrieve session
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
        else:
            session_id = str(uuid.uuid4())[:12]
            session = DebateSession(session_id=session_id)
            self.sessions[session_id] = session

        # Handle simple greetings/social cues first
        intent = self._detect_intent(user_input)
        if intent == "greeting":
            return self._create_social_turn(
                session,
                user_input,
                "Hello! I'm LogiScan, your logical debate partner. What's on your mind today? Are there any arguments you'd like to analyze or debate?",
            )
        if intent == "question":
            return self._create_intent_turn(session, user_input, intent)
        if intent == "ack":
            return self._create_intent_turn(session, user_input, intent)

        # Analyze user input through LogiScan pipeline
        analysis = await pipeline_orchestrator.analyze(text=user_input)

        # Calculate current state
        state_before = self._calculate_state(session, analysis)

        # Select action using DQN
        is_training = settings.LOGISCAN_ENV == "training"
        action_idx, confidence = self.agent.select_action(state_before, training=is_training)
        action_type = ACTION_MAP[action_idx]

        # Confidence gating: never assert a fallacy below the floor
        top_label, top_conf = self._top_label_confidence(analysis)
        if action_type == "POINT_OUT_FALLACY" and top_conf < settings.RL_POINT_CONF_FLOOR:
            logger.info(
                f"Downgrading POINT_OUT_FALLACY -> ASK_SOCRATIC "
                f"(top conf {top_conf:.2f} < floor {settings.RL_POINT_CONF_FLOOR:.2f})"
            )
            action_idx = ACTION_TO_INDEX["ASK_SOCRATIC"]
            action_type = "ASK_SOCRATIC"

        # Generate response based on action
        agent_response = self._generate_response(
            action_type=action_type,
            analysis=analysis,
            state=state_before,
            session_id=session_id,
            user_input=user_input,
            top_label=top_label,
            top_confidence=top_conf,
        )

        # Build DebateAction
        action = DebateAction(
            action_type=action_type,
            action_index=action_idx,
            confidence=confidence,
            response_template=agent_response,
        )

        # Calculate reward
        reward = self._calculate_reward(
            state_before=state_before,
            action_type=action_type,
            analysis=analysis,
            session=session,
        )

        # Update state after action
        state_after = self._project_state(state_before, action_type)

        # Create debate turn
        turn = DebateTurn(
            session_id=session_id,
            turn_number=session.total_turns + 1,
            user_input=user_input,
            detected_fallacies=analysis.fine_labels
            if analysis.fine_labels and analysis.fine_labels[0] != "factual_statement"
            else [],
            logic_score=analysis.logic_score,
            agent_action=action,
            agent_response=agent_response,
            state_before=state_before,
            state_after=state_after,
            reward=reward,
        )

        # Store in session
        session.turns.append(turn)

        # Store transition in replay buffer for offline training
        self._store_experience(state_before, action_idx, reward, state_after)

        # Persist the turn for future offline RL training (best-effort)
        await self._log_turn(turn)

        # Update last action for repetition detection
        self._last_actions[session_id] = action_type

        # Decay epsilon
        self.agent.update_epsilon()

        logger.info(
            f"Debate turn {turn.turn_number}: action={action_type}, "
            f"reward={reward:.3f}, logic_score={analysis.logic_score:.2f}"
        )

        return turn

    # --- Intent-specific turns ---------------------------------------------

    def _create_social_turn(self, session: DebateSession, user_input: str, response: str) -> DebateTurn:
        """Create a non-RL turn for simple social interactions."""
        state = DebateState(logic_score=1.0)
        action = DebateAction(action_type="AGREE_AND_PIVOT", action_index=3, confidence=1.0, response_template=response)
        turn = DebateTurn(
            session_id=session.session_id,
            turn_number=session.total_turns + 1,
            user_input=user_input,
            detected_fallacies=[],
            logic_score=1.0,
            agent_action=action,
            agent_response=response,
            state_before=state,
            state_after=state,
            reward=0.0,
        )
        session.turns.append(turn)
        return turn

    def _create_intent_turn(self, session: DebateSession, user_input: str, intent: str) -> DebateTurn:
        """Create a non-RL turn for questions and short acknowledgments."""
        state = DebateState(logic_score=1.0)
        if intent == "question":
            response = self._pick_template(
                session.session_id,
                [
                    "That's an interesting question. Could you frame it as a claim or argument so I can test its logical structure?",
                    "Good question. If we turn it into a statement, what conclusion would you want to defend — and what premises would support it?",
                    "Before I can analyze that, try stating it as an argument: what do you believe, and why?",
                    "Let's make it testable. Restate your question as a premise-conclusion argument and I'll evaluate the reasoning.",
                ],
            )
        else:
            response = self._pick_template(
                session.session_id,
                [
                    "I follow you. Could you expand on that reasoning a bit more?",
                    "Got it — take your time and lay out the full argument when you're ready.",
                    "Understood. What's the key claim behind that, and what evidence supports it?",
                ],
            )
        action = DebateAction(action_type="ASK_SOCRATIC", action_index=0, confidence=1.0, response_template=response)
        turn = DebateTurn(
            session_id=session.session_id,
            turn_number=session.total_turns + 1,
            user_input=user_input,
            detected_fallacies=[],
            logic_score=1.0,
            agent_action=action,
            agent_response=response,
            state_before=state,
            state_after=state,
            reward=0.0,
        )
        session.turns.append(turn)
        return turn

    # --- State estimation ----------------------------------------------------

    def _calculate_state(
        self,
        session: DebateSession,
        analysis,
    ) -> DebateState:
        """Calculate the current POMDP state from session history and new analysis."""

        # Fallacy density from recent turns (last 5)
        recent_turns = session.turns[-5:]
        if recent_turns:
            fallacy_count = sum(1 for t in recent_turns if t.detected_fallacies)
            fallacy_density = fallacy_count / len(recent_turns)
        else:
            fallacy_density = 0.0

        # Argument depth: crude estimate based on input length and complexity
        word_count = len(analysis.input_text.split())
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

        # User sentiment: very simple heuristic based on fallacy types
        if any(f in analysis.fine_labels for f in ["ad_hominem", "appeal_to_emotion"]):
            sentiment = -0.5  # Hostile/emotional
        elif analysis.logic_score > 0.7:
            sentiment = 0.5  # Receptive/rational
        else:
            sentiment = 0.0  # Neutral

        return DebateState(
            fallacy_density=fallacy_density,
            argument_depth=depth,
            user_sentiment=sentiment,
            logic_score=analysis.logic_score,
        )

    def _project_state(self, state: DebateState, action_type: str) -> DebateState:
        """Estimate state after taking action (for reward calculation)."""
        new_state = DebateState(
            fallacy_density=state.fallacy_density,
            argument_depth=state.argument_depth,
            user_sentiment=state.user_sentiment,
            logic_score=state.logic_score,
        )

        # Heuristic state transitions
        if action_type == "ASK_SOCRATIC":
            new_state.argument_depth = min(5, state.argument_depth + 1)
            new_state.user_sentiment = min(1.0, state.user_sentiment + 0.1)
        elif action_type == "POINT_OUT_FALLACY":
            new_state.fallacy_density = max(0.0, state.fallacy_density - 0.1)
            new_state.logic_score = min(1.0, state.logic_score + 0.1)
        elif action_type == "COUNTER_ARGUMENT":
            new_state.user_sentiment = max(-1.0, state.user_sentiment - 0.1)
        elif action_type == "AGREE_AND_PIVOT":
            new_state.user_sentiment = min(1.0, state.user_sentiment + 0.2)

        return new_state

    def _calculate_reward(
        self,
        state_before: DebateState,
        action_type: str,
        analysis,
        session: DebateSession,
    ) -> float:
        """
        Calculate reward using: R = w1(Δclarity) + w2(logic_retention) - w3(repetition)
        """
        # Δclarity: change in logic score
        if session.turns:
            prev_logic = session.turns[-1].logic_score
            delta_clarity = analysis.logic_score - prev_logic
        else:
            delta_clarity = 0.0

        # Logic retention: engagement with correction
        if action_type == "POINT_OUT_FALLACY":
            if analysis.logic_score > 0.5:
                logic_retention = 1.0  # User engaged positively
            elif analysis.logic_score > 0.2:
                logic_retention = 0.0  # Neutral
            else:
                logic_retention = -1.0  # User rejected or doubled down
        else:
            logic_retention = 0.5  # Moderate engagement value for non-explicit actions

        # Repetition penalty
        if session.session_id in self._last_actions:
            repetition = 1.0 if self._last_actions[session.session_id] == action_type else 0.0
        else:
            repetition = 0.0

        reward = (
            self.REWARD_W_CLARITY * delta_clarity
            + self.REWARD_W_LOGIC * logic_retention
            + self.REWARD_W_REPETITION * repetition
        )

        return reward

    # --- Response generation --------------------------------------------------

    @staticmethod
    def _top_label_confidence(analysis) -> tuple[str | None, float]:
        """Return (top fine label, its confidence) defensively."""
        labels = getattr(analysis, "fine_labels", None) or []
        scores = getattr(analysis, "confidence_scores", None) or []
        if not labels:
            return None, 0.0
        try:
            conf = float(scores[0]) if scores else 0.0
        except (TypeError, ValueError, IndexError):
            conf = 0.0
        return labels[0], conf

    @staticmethod
    def _key_phrase(user_input: str | None, max_words: int = 12) -> str:
        """Extract a short quotable phrase from the user's input for grounded responses."""
        if not user_input:
            return "your claim"
        words = user_input.split()
        if not words:
            return "your claim"
        phrase = " ".join(words[:max_words])
        if len(words) > max_words:
            phrase += "..."
        return f'"{phrase}"'

    def _pick_template(self, session_id: str | None, templates: list[str]) -> str:
        """Pick an unused template for this session; cycle when exhausted."""
        if not templates:
            return ""
        if not session_id:
            return random.choice(templates)
        used = self._used_templates.setdefault(session_id, set())
        available = [t for t in templates if t not in used]
        if not available:
            available = templates
            used.clear()
        chosen = random.choice(available)
        used.add(chosen)
        return chosen

    def _generate_response(
        self,
        action_type: str,
        analysis,
        state: DebateState,
        session_id: str | None = None,
        user_input: str | None = None,
        top_label: str | None = None,
        top_confidence: float | None = None,
    ) -> str:
        """Generate a debate response based on the selected action and analysis."""

        correction = analysis.correction_strategy or ""
        # Filter out factual_statement from display
        fallacy_list = [f for f in analysis.fine_labels if f != "factual_statement"]
        fallacies = ", ".join(f.replace("_", " ") for f in fallacy_list) if fallacy_list else "the reasoning"
        phrase = self._key_phrase(user_input)

        if action_type == "ASK_SOCRATIC":
            templates = [
                f"That's an interesting point regarding {fallacies}. You said {phrase} — if we accept your premise, what would happen if we applied the same reasoning in a completely different context?",
                f"I'm curious about the underlying assumption here. You said {phrase}. If the logic behind it were applied universally, would it still hold up, or could we find a clear counterexample?",
                f"You've raised a specific claim: {phrase}. To explore it deeper: if someone used this exact same reasoning to argue for the opposite conclusion, how would you respond?",
                f"Let's look at the structure of this argument. You said {phrase}. Does the conclusion follow necessarily from the premises, or is there a gap we're filling with {fallacies}?",
            ]
            return self._pick_template(session_id, templates)

        elif action_type == "POINT_OUT_FALLACY":
            if correction and len(correction) > 20:
                return correction

            label_text = top_label.replace("_", " ") if top_label else fallacies
            confidence_suffix = f" (confidence {top_confidence:.0%})" if top_confidence is not None else ""
            templates = [
                f"I notice a potential issue with the reasoning here. The argument appears to involve {label_text}{confidence_suffix}. {self._get_fallback_explanation(analysis)}",
                f"If we look closely at the structure, we might be seeing a {label_text}{confidence_suffix}. {self._get_fallback_explanation(analysis)}",
                f"Wait, let's pause on the logic for a second. This seems like a case of {label_text}{confidence_suffix}. {self._get_fallback_explanation(analysis)}",
            ]
            return self._pick_template(session_id, templates)

        elif action_type == "COUNTER_ARGUMENT":
            templates = [
                f"I understand your perspective, but let me offer a different view. Even if we accept the premises, there are alternative explanations that don't rely on the same logical leap. Could it be that {fallacies} is overshadowing other possibilities?",
                f"While that's one way to look at it, consider this: even if your points are true, do they lead exclusively to your conclusion? There might be a more robust explanation that avoids {fallacies}.",
                f"That's a common way to frame this, but let's test a counter-hypothesis. What if the evidence actually suggests the opposite, and the current reasoning is just {fallacies}?",
            ]
            return self._pick_template(session_id, templates)

        elif action_type == "AGREE_AND_PIVOT":
            templates = [
                f"You make a valid point here. I appreciate the reasoning. However, let's also consider the broader context. Does this logic remain sound if we remove the element of {fallacies}?",
                f"I see where you're coming from. It's a compelling angle. You said {phrase}. But to keep our discourse rigorous, let's pivot to the core assumption: is it possible we're relying too much on {fallacies} here?",
                f"I follow your logic. It's an important part of the discussion. However, let's refocus on the evidence. If we set aside {fallacies} for a moment, what does the data actually show?",
            ]
            return self._pick_template(session_id, templates)

        return "Let me think about that and consider the logical structure more carefully."

    def _get_fallback_explanation(self, analysis) -> str:
        """Generate a fallback explanation when LLM correction is unavailable."""
        if analysis.coarse_category == "Formal":
            return (
                "The logical structure doesn't guarantee the conclusion. "
                "Even if all premises are true, the conclusion could still be false."
            )
        elif analysis.coarse_category:
            return (
                f"This falls under {analysis.coarse_category} fallacies. "
                "Consider whether the reasoning directly supports the conclusion."
            )
        return "Review the connection between your premises and conclusion."

    # --- Experience & persistence ---------------------------------------------

    def _store_experience(
        self,
        state: DebateState,
        action: int,
        reward: float,
        next_state: DebateState,
    ) -> None:
        """Store transition in replay buffer for training."""
        self.agent.replay_buffer.push(
            state=torch.FloatTensor(state.to_tensor()),
            action=action,
            reward=reward,
            next_state=torch.FloatTensor(next_state.to_tensor()),
            done=False,
        )

    async def _log_turn(self, turn: DebateTurn) -> None:
        """Best-effort persistence of a debate turn for future offline RL training."""
        try:
            if self._logger is None:
                from backend.app.services.debate_logger import debate_logger

                self._logger = debate_logger
            await self._logger.log_turn(turn)
        except Exception as e:
            logger.warning(f"Debate turn logging failed (non-fatal): {e}")

    def train_offline(self, num_steps: int = 100) -> list[float]:
        """Perform offline training from replay buffer."""
        losses = []
        for _ in range(num_steps):
            loss = self.agent.train_step()
            if loss is not None:
                losses.append(loss)

        if losses:
            logger.info(f"Offline training: {len(losses)} steps, avg_loss={sum(losses) / len(losses):.4f}")

        return losses

    def save_model(self) -> None:
        """Save the current DQN model."""
        self.agent.save(settings.DQN_MODEL_PATH)

    def get_session(self, session_id: str) -> DebateSession | None:
        """Retrieve a debate session by ID."""
        return self.sessions.get(session_id)

    def get_session_summary(self, session_id: str) -> dict | None:
        """Get a summary of a debate session."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "total_turns": session.total_turns,
            "average_logic_score": session.average_logic_score,
            "cumulative_reward": session.cumulative_reward,
            "actions_used": [t.agent_action.action_type for t in session.turns],
            "fallacies_detected": [f for t in session.turns for f in t.detected_fallacies],
        }


# Global singleton
debate_service = DebateService()
