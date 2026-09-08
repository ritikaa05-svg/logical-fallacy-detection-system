from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import torch

from backend.app.schemas.debate import DebateState
from backend.app.services.debate_service import DQN, DQNAgent, DebateService, ReplayBuffer


class TestDQN:
    def test_forward_shape(self):
        model = DQN(state_dim=4, action_dim=4, hidden_dim=32)
        batch = torch.randn(2, 4)
        output = model(batch)
        assert output.shape == (2, 4)

    def test_forward_different_batch_sizes(self):
        model = DQN(state_dim=4, action_dim=4, hidden_dim=32)
        for batch_size in [1, 8, 16]:
            batch = torch.randn(batch_size, 4)
            output = model(batch)
            assert output.shape == (batch_size, 4)

    def test_dueling_architecture(self):
        model = DQN(state_dim=4, action_dim=4, hidden_dim=32)
        batch = torch.randn(1, 4)
        q_vals = model(batch)
        assert q_vals.requires_grad


class TestReplayBuffer:
    def test_push_and_sample(self):
        buf = ReplayBuffer(capacity=100)
        state = torch.randn(4)
        action = 1
        reward = 0.5
        next_state = torch.randn(4)
        buf.push(state, action, reward, next_state, done=False)
        assert len(buf) == 1
        batch = buf.sample(1)
        assert len(batch) == 1

    def test_sample_returns_all_when_buffer_smaller(self):
        buf = ReplayBuffer(capacity=100)
        for i in range(5):
            buf.push(torch.randn(4), i % 4, float(i), torch.randn(4), False)
        batch = buf.sample(64)
        assert len(batch) == 5

    def test_capacity_limit(self):
        buf = ReplayBuffer(capacity=3)
        for i in range(10):
            buf.push(torch.randn(4), 0, 1.0, torch.randn(4), False)
        assert len(buf) == 3

    def test_sample_returns_tuples(self):
        buf = ReplayBuffer(capacity=10)
        buf.push(torch.randn(4), 2, 1.0, torch.randn(4), True)
        batch = buf.sample(1)
        state, action, reward, next_state, done = batch[0]
        assert isinstance(state, torch.Tensor)
        assert isinstance(action, int)
        assert isinstance(reward, float)
        assert isinstance(next_state, torch.Tensor)
        assert isinstance(done, bool)


class TestDQNAgent:
    @pytest.fixture
    def agent(self):
        with patch("backend.app.services.debate_service.settings") as mock_settings:
            mock_settings.RL_GAMMA = 0.99
            mock_settings.RL_EPSILON_START = 1.0
            mock_settings.RL_EPSILON_END = 0.01
            mock_settings.RL_EPSILON_DECAY = 0.995
            mock_settings.RL_REPLAY_BUFFER_SIZE = 10000
            return DQNAgent()
    def test_select_action_greedy_when_not_training(self, agent):
        state = DebateState(logic_score=0.8)
        action, confidence = agent.select_action(state, training=False)
        assert 0 <= action < 4
        assert 0.0 <= confidence <= 1.0

    def test_select_action_returns_valid_range(self, agent):
        state = DebateState()
        for _ in range(20):
            action, confidence = agent.select_action(state, training=True)
            assert 0 <= action < 4

    def test_update_epsilon(self, agent):
        initial = agent.epsilon
        agent.update_epsilon()
        assert agent.epsilon < initial

    def test_update_epsilon_floor(self, agent):
        agent.epsilon = 0.001
        agent.update_epsilon()
        assert agent.epsilon >= agent.epsilon_end

    def test_train_step_requires_buffer(self, agent):
        loss = agent.train_step()
        assert loss is None

    def test_train_step_with_data(self, agent):
        for _ in range(128):
            agent.replay_buffer.push(torch.randn(4), 1, 0.5, torch.randn(4), False)
        loss = agent.train_step()
        assert loss is not None
        assert loss > 0

    def test_target_network_update(self, agent):
        for _ in range(200):
            agent.replay_buffer.push(torch.randn(4), 1, 0.5, torch.randn(4), False)
        for _ in range(100):
            agent.train_step()
        assert agent.training_steps == 100
        policy_state = dict(agent.policy_net.state_dict())
        target_state = dict(agent.target_net.state_dict())
        synced = all(torch.all(policy_state[k] == target_state[k]) for k in policy_state)
        assert synced

    def test_save_and_load(self, agent, tmp_path):
        model_path = str(tmp_path / "dqn_test.pt")
        agent.save(model_path)

        action_before, _ = agent.select_action(DebateState(), training=False)

        new_agent = DQNAgent()
        new_agent.epsilon = 0.5
        loaded = new_agent.load(model_path)
        assert loaded is True

        action_after, _ = new_agent.select_action(DebateState(), training=False)
        assert new_agent.epsilon == 1.0

    def test_load_nonexistent_file(self, agent):
        loaded = agent.load("/nonexistent/path.pt")
        assert loaded is False

    def test_rule_based_action_high_fallacy_density(self, agent):
        state = DebateState(fallacy_density=0.9, logic_score=0.2, user_sentiment=0.0)
        assert agent._rule_based_action(state) == (1, 0.8)

    def test_rule_based_action_hostile_user(self, agent):
        state = DebateState(fallacy_density=0.2, logic_score=0.6, user_sentiment=-0.5)
        assert agent._rule_based_action(state) == (0, 0.7)

    def test_rule_based_action_agree_when_strong(self, agent):
        state = DebateState(fallacy_density=0.1, logic_score=0.8, user_sentiment=0.0)
        assert agent._rule_based_action(state) == (3, 0.7)

    def test_rule_based_action_default(self, agent):
        state = DebateState(fallacy_density=0.3, logic_score=0.5, user_sentiment=0.0)
        assert agent._rule_based_action(state) == (0, 0.6)

    def test_agent_load_generic_error(self, agent):
        with (
            patch("backend.app.services.debate_service.settings") as mock_settings,
            patch("backend.app.services.debate_service.torch.load", side_effect=OSError("corrupt file")),
        ):
            assert agent.load("/whatever.pt") is False

    def test_select_action_rules_when_model_not_loaded(self):
        with patch("backend.app.services.debate_service.settings") as mock_settings:
            mock_settings.RL_GAMMA = 0.99
            mock_settings.RL_EPSILON_START = 1.0
            mock_settings.RL_EPSILON_END = 0.01
            mock_settings.RL_EPSILON_DECAY = 0.995
            mock_settings.RL_REPLAY_BUFFER_SIZE = 10000
            a = DQNAgent()
            a.model_loaded = False
            state = DebateState(fallacy_density=0.9, logic_score=0.1, user_sentiment=0.0)
            assert a.select_action(state, training=True) == (1, 0.8)


class TestIntentDetection:
    @pytest.mark.parametrize(
        "text",
        ["hello", "Hi", "hey!", "what's up", "sup", "greetings", "Good morning."],
    )
    def test_greeting_intents(self, text):
        assert DebateService._detect_intent(text) == "greeting"

    @pytest.mark.parametrize(
        "text",
        ["What does it mean?", "Can you learn without learning?", "Why is that the case?", "How would that work?"],
    )
    def test_question_intents(self, text):
        assert DebateService._detect_intent(text) == "question"

    @pytest.mark.parametrize("text", ["maybe", "ok", "I see", "yes", "no", "interesting", "idk"],)
    def test_ack_intents(self, text):
        assert DebateService._detect_intent(text) == "ack"

    @pytest.mark.parametrize(
        "text",
        ["You are a bird hence you must fly", "The sky is blue and the grass is green.", "All men are mortal."],
    )
    def test_argument_intents(self, text):
        assert DebateService._detect_intent(text) is None


class TestDebateService:
    @pytest.fixture
    def service(self):
        with patch("backend.app.services.debate_service.settings") as mock_settings:
            mock_settings.RL_GAMMA = 0.99
            mock_settings.RL_EPSILON_START = 1.0
            mock_settings.RL_EPSILON_END = 0.01
            mock_settings.RL_EPSILON_DECAY = 0.995
            mock_settings.RL_REPLAY_BUFFER_SIZE = 10000
            mock_settings.RL_POINT_CONF_FLOOR = 0.60
            mock_settings.DQN_MODEL_PATH = "/nonexistent/model.pt"
            with patch("backend.app.services.debate_service.DQNAgent"):
                from backend.app.services.debate_service import DebateService

                svc = DebateService()
                svc.sessions = {}
                svc._last_actions = {}
                svc._used_templates = {}
                svc._logger = None
                return svc

    @pytest.mark.asyncio
    async def test_social_turn_greeting(self, service):
        analysis = MagicMock()
        analysis.fine_labels = []
        analysis.logic_score = 1.0
        analysis.input_text = "hello"

        with patch("backend.app.services.debate_service.pipeline_orchestrator") as mock_pipe:
            mock_pipe.analyze = MagicMock(return_value=analysis)
            turn = await service.start_or_continue("hello")
            assert turn.agent_action.action_index == 3
            assert turn.agent_action.action_type == "AGREE_AND_PIVOT"

    def test_calculate_state_empty_session(self, service):
        session = MagicMock()
        session.turns = []
        analysis = MagicMock()
        analysis.input_text = "Short text."
        analysis.fine_labels = ["valid_reasoning"]
        analysis.logic_score = 0.9

        state = service._calculate_state(session, analysis)
        assert state.fallacy_density == 0.0
        assert state.argument_depth == 1
        assert state.user_sentiment == 0.5

    def test_calculate_state_with_fallacies(self, service):
        session = MagicMock()
        session.turns = []
        analysis = MagicMock()
        analysis.input_text = "word " * 250
        analysis.fine_labels = ["ad_hominem"]
        analysis.logic_score = 0.3

        state = service._calculate_state(session, analysis)
        assert state.user_sentiment == -0.5
        assert state.argument_depth == 5

    def test_project_state_socratic(self, service):
        state = DebateState(fallacy_density=0.5, argument_depth=2, user_sentiment=0.0, logic_score=0.5)
        projected = service._project_state(state, "ASK_SOCRATIC")
        assert projected.argument_depth == 3
        assert projected.user_sentiment == 0.1

    def test_project_state_point_out(self, service):
        state = DebateState(fallacy_density=0.8, argument_depth=2, user_sentiment=0.0, logic_score=0.3)
        projected = service._project_state(state, "POINT_OUT_FALLACY")
        assert projected.fallacy_density == pytest.approx(0.7)
        assert projected.logic_score == 0.4

    def test_calculate_reward_first_turn(self, service):
        session = MagicMock()
        session.turns = []
        session.session_id = "test-123"
        state_before = DebateState()
        analysis = MagicMock()
        analysis.logic_score = 0.8
        analysis.coarse_category = "Formal"

        reward = service._calculate_reward(state_before, "POINT_OUT_FALLACY", analysis, session)
        assert isinstance(reward, float)

    def test_calculate_reward_repetition_penalty(self, service):
        session = MagicMock()
        session.turns = [MagicMock(logic_score=0.5)]
        session.session_id = "test-123"
        service._last_actions["test-123"] = "POINT_OUT_FALLACY"
        analysis = MagicMock()
        analysis.logic_score = 0.5
        analysis.coarse_category = "Formal"

        reward = service._calculate_reward(DebateState(), "POINT_OUT_FALLACY", analysis, session)
        assert reward == pytest.approx(-2.0)

    def test_create_social_turn(self, service):
        session = MagicMock()
        session.session_id = "test-123"
        session.total_turns = 0
        turn = service._create_social_turn(session, "hello", "Hi there!")
        assert turn.agent_action.action_type == "AGREE_AND_PIVOT"
        assert turn.reward == 0.0
        assert turn.logic_score == 1.0

    def test_get_session_summary_nonexistent(self, service):
        summary = service.get_session_summary("nonexistent")
        assert summary is None

    def test_get_session_summary_exists(self, service):
        session = MagicMock()
        session.session_id = "test-123"
        session.total_turns = 3
        session.average_logic_score = 0.75
        session.cumulative_reward = 2.5
        session.turns = [MagicMock() for _ in range(3)]
        for t in session.turns:
            t.agent_action.action_type = "ASK_SOCRATIC"
            t.detected_fallacies = ["ad_hominem"]
        service.sessions["test-123"] = session

        summary = service.get_session_summary("test-123")
        assert summary is not None
        assert summary["total_turns"] == 3
        assert len(summary["actions_used"]) == 3

    @pytest.mark.asyncio
    async def test_start_or_continue_full_flow(self, service):
        analysis = MagicMock()
        analysis.input_text = "The weather is nice today"
        analysis.fine_labels = ["false_dilemma"]
        analysis.logic_score = 0.4
        analysis.correction_strategy = "A clearly written correction strategy that exceeds twenty characters."
        analysis.coarse_category = "Informal (Presumption)"

        service.agent.select_action.return_value = (2, 0.65)

        with (
            patch("backend.app.services.debate_service.pipeline_orchestrator") as mock_pipe,
            patch("backend.app.services.debate_service.settings.LOGISCAN_ENV", "production"),
        ):
            mock_pipe.analyze = AsyncMock(return_value=analysis)

            turn = await service.start_or_continue("The world is flat and round at the same time.")
            assert turn.logic_score == 0.4
            assert turn.agent_action.action_index == 2
            assert 0 <= turn.turn_number

            continue_turn = await service.start_or_continue(
                "Or maybe it is neither flat nor round.",
                session_id=turn.session_id,
            )
            assert continue_turn.session_id == turn.session_id
            assert continue_turn.turn_number == 2

    def test_start_or_continue_existing_session_path(self, service):
        session = MagicMock()
        session.session_id = "existing-1"
        session.turns = []
        session.total_turns = 0
        service.sessions["existing-1"] = session
        assert service.get_session("existing-1") is session
        assert service.get_session("missing") is None

    def test_calculate_state_depth_branches(self, service):
        session = MagicMock()
        session.turns = [
            MagicMock(detected_fallacies=["ad_hominem"]),
            MagicMock(detected_fallacies=[]),
        ]
        analysis = MagicMock()
        analysis.input_text = "word " * 25
        analysis.fine_labels = ["valid_reasoning"]
        analysis.logic_score = 0.3
        state = service._calculate_state(session, analysis)
        assert state.fallacy_density == 0.5
        assert state.argument_depth == 2
        assert state.user_sentiment == 0.0

        for count, expected in [(60, 3), (150, 4)]:
            analysis.input_text = "word " * count
            assert service._calculate_state(session, analysis).argument_depth == expected

    def test_project_state_counter_and_agree(self, service):
        state = DebateState(fallacy_density=0.5, argument_depth=2, user_sentiment=0.0, logic_score=0.5)
        counter = service._project_state(state, "COUNTER_ARGUMENT")
        assert counter.user_sentiment == pytest.approx(-0.1)
        agree = service._project_state(state, "AGREE_AND_PIVOT")
        assert agree.user_sentiment == pytest.approx(0.2)

    def test_generate_response_actions(self, service):
        analysis = MagicMock()
        analysis.correction_strategy = None
        analysis.fine_labels = ["ad_hominem", "factual_statement"]
        analysis.coarse_category = "Formal"

        for action in ["ASK_SOCRATIC", "POINT_OUT_FALLACY", "COUNTER_ARGUMENT", "AGREE_AND_PIVOT", "UNKNOWN_ACTION"]:
            response = service._generate_response(action, analysis, DebateState())
            assert isinstance(response, str)
            assert len(response) > 0

    def test_generate_response_returns_long_correction(self, service):
        analysis = MagicMock()
        analysis.correction_strategy = "This is a sufficiently long correction strategy."
        analysis.fine_labels = []
        response = service._generate_response("POINT_OUT_FALLACY", analysis, DebateState())
        assert response == analysis.correction_strategy

    def test_fallback_explanations(self, service):
        formal = MagicMock(coarse_category="Formal")
        assert "logical structure" in service._get_fallback_explanation(formal)
        informal = MagicMock(coarse_category="Informal (Presumption)")
        assert "Presumption" in service._get_fallback_explanation(informal)
        none = MagicMock(coarse_category=None)
        assert "connection" in service._get_fallback_explanation(none)

    def test_calculate_reward_more_branches(self, service):
        session = MagicMock()
        session.turns = [MagicMock(logic_score=0.9)]
        session.session_id = "r-1"
        service._last_actions = {}

        low = MagicMock()
        low.logic_score = 0.1
        low.coarse_category = None
        effect = service._calculate_reward(DebateState(), "POINT_OUT_FALLACY", low, session)
        assert effect <= 0.0

        neutral = MagicMock()
        neutral.logic_score = 0.5
        neutral.coarse_category = None
        other = service._calculate_reward(DebateState(), "ASK_SOCRATIC", neutral, session)
        assert isinstance(other, float)

    def test_train_offline_and_save(self, service, tmp_path):
        service.agent.replay_buffer.push(
            state=torch.FloatTensor([0.2, 0.3, 0.1, 0.5]),
            action=2,
            reward=1.0,
            next_state=torch.FloatTensor([0.25, 0.3, 0.1, 0.5]),
            done=False,
        )
        service.agent.train_step.return_value = 0.03125
        losses = service.train_offline(num_steps=4)
        assert isinstance(losses, list)
        assert len(losses) == 4
        assert service.agent.train_step.call_count >= 4

        with patch("backend.app.services.debate_service.settings.DQN_MODEL_PATH", str(tmp_path / "dqn.pt")):
            service.save_model()
            service.agent.save.assert_called_once_with(str(tmp_path / "dqn.pt"))

    def test_store_experience_direct(self, service):
        service._store_experience(
            DebateState(fallacy_density=0.1, argument_depth=2, user_sentiment=0.0, logic_score=0.5),
            1,
            0.75,
            DebateState(fallacy_density=0.0, argument_depth=3, user_sentiment=0.1, logic_score=0.6),
        )
        service.agent.replay_buffer.push.assert_called_once()


class TestDebateServicePartA:
    @pytest.fixture
    def service(self):
        with patch("backend.app.services.debate_service.settings") as mock_settings:
            mock_settings.RL_GAMMA = 0.99
            mock_settings.RL_EPSILON_START = 1.0
            mock_settings.RL_EPSILON_END = 0.01
            mock_settings.RL_EPSILON_DECAY = 0.995
            mock_settings.RL_REPLAY_BUFFER_SIZE = 10000
            mock_settings.RL_POINT_CONF_FLOOR = 0.60
            mock_settings.DQN_MODEL_PATH = "/nonexistent/model.pt"
            with patch("backend.app.services.debate_service.DQNAgent"):
                from backend.app.services.debate_service import DebateService

                svc = DebateService()
                svc.sessions = {}
                svc._last_actions = {}
                svc._used_templates = {}
                svc._logger = None
                return svc

    @pytest.mark.asyncio
    async def test_question_turn_skips_pipeline(self, service):
        with patch("backend.app.services.debate_service.pipeline_orchestrator") as mock_pipe:
            turn = await service.start_or_continue("Can you learn without learning?")
            mock_pipe.analyze.assert_not_called()
            assert turn.agent_action.action_type == "ASK_SOCRATIC"
            assert turn.detected_fallacies == []
            assert turn.turn_number == 1

    @pytest.mark.asyncio
    async def test_ack_turn_skips_pipeline(self, service):
        with patch("backend.app.services.debate_service.pipeline_orchestrator") as mock_pipe:
            turn = await service.start_or_continue("maybe")
            mock_pipe.analyze.assert_not_called()
            assert turn.agent_action.action_type == "ASK_SOCRATIC"

    @pytest.mark.asyncio
    async def test_point_out_downgraded_below_conf_floor(self, service):
        analysis = MagicMock()
        analysis.input_text = "You are a bird hence you must fly"
        analysis.fine_labels = ["affirming_consequent"]
        analysis.confidence_scores = [0.13]
        analysis.logic_score = 0.13
        analysis.correction_strategy = None
        analysis.coarse_category = "Formal"

        service.agent.select_action.return_value = (1, 0.8)  # rule-based wants POINT_OUT_FALLACY

        with (
            patch("backend.app.services.debate_service.pipeline_orchestrator") as mock_pipe,
            patch("backend.app.services.debate_service.settings.LOGISCAN_ENV", "production"),
        ):
            mock_pipe.analyze = AsyncMock(return_value=analysis)
            turn = await service.start_or_continue("You are a bird hence you must fly")
            assert turn.agent_action.action_type == "ASK_SOCRATIC"
            assert turn.agent_action.action_index == 0

    @pytest.mark.asyncio
    async def test_point_out_kept_above_conf_floor(self, service):
        analysis = MagicMock()
        analysis.input_text = "We either ban cars or accept pollution"
        analysis.fine_labels = ["false_dilemma"]
        analysis.confidence_scores = [0.71]
        analysis.logic_score = 0.2
        analysis.correction_strategy = None
        analysis.coarse_category = "Informal (Presumption)"

        service.agent.select_action.return_value = (1, 0.8)

        with (
            patch("backend.app.services.debate_service.pipeline_orchestrator") as mock_pipe,
            patch("backend.app.services.debate_service.settings.LOGISCAN_ENV", "production"),
        ):
            mock_pipe.analyze = AsyncMock(return_value=analysis)
            turn = await service.start_or_continue("We either ban cars or accept pollution")
            assert turn.agent_action.action_type == "POINT_OUT_FALLACY"

    def test_template_de_dup_cycles(self, service):
        templates = ["t1", "t2", "t3"]
        picked = {service._pick_template("s-1", templates) for _ in range(3)}
        assert picked == {"t1", "t2", "t3"}
        again = service._pick_template("s-1", templates)
        assert again in {"t1", "t2", "t3"}

    def test_template_de_dup_is_per_session(self, service):
        first = service._pick_template("s-1", ["t1", "t2"])
        assert service._used_templates["s-1"] == {first}
        # Session s-2 must have an empty used set; it may freely pick either
        picked = service._pick_template("s-2", ["t1", "t2"])
        assert picked in {"t1", "t2"}
        assert service._used_templates["s-2"] == {picked}
        assert service._used_templates["s-1"] == {first}

    def test_generate_response_grounds_user_phrase(self, service):
        analysis = MagicMock()
        analysis.correction_strategy = None
        analysis.fine_labels = ["false_dilemma"]
        analysis.coarse_category = "Informal (Presumption)"
        responses = set()
        for _ in range(10):
            responses.add(
                service._generate_response(
                    "ASK_SOCRATIC",
                    analysis,
                    DebateState(),
                    session_id="s-1",
                    user_input="We either ban cars or accept pollution",
                    top_label="false_dilemma",
                    top_confidence=0.71,
                )
            )
        # Every ASK_SOCRATIC template is grounded in the user's quoted phrase
        assert len(responses) == 4
        assert all("ban cars" in r for r in responses)

    def test_generate_response_includes_confidence_when_given(self, service):
        analysis = MagicMock()
        analysis.correction_strategy = None
        analysis.fine_labels = ["false_dilemma"]
        analysis.coarse_category = "Informal (Presumption)"
        response = service._generate_response(
            "POINT_OUT_FALLACY",
            analysis,
            DebateState(),
            session_id="s-1",
            top_label="false_dilemma",
            top_confidence=0.71,
        )
        assert "false dilemma" in response
        assert "71%" in response

    def test_top_label_confidence_defensive(self, service):
        empty = MagicMock()
        empty.fine_labels = []
        empty.confidence_scores = []
        assert service._top_label_confidence(empty) == (None, 0.0)

        missing = MagicMock(spec=[])
        assert service._top_label_confidence(missing) == (None, 0.0)

        good = MagicMock()
        good.fine_labels = ["ad_hominem"]
        good.confidence_scores = [0.83]
        assert service._top_label_confidence(good) == ("ad_hominem", 0.83)

    @pytest.mark.asyncio
    async def test_turn_logging_never_fails_debate(self, service):
        analysis = MagicMock()
        analysis.input_text = "The weather is nice today"
        analysis.fine_labels = []
        analysis.confidence_scores = []
        analysis.logic_score = 0.9
        analysis.correction_strategy = None
        analysis.coarse_category = None

        service.agent.select_action.return_value = (3, 0.7)

        with patch(
            "backend.app.services.debate_service.pipeline_orchestrator"
        ) as mock_pipe:
            mock_pipe.analyze = AsyncMock(return_value=analysis)

            async def boom(_turn):
                raise RuntimeError("db is down")

            service._logger = MagicMock()
            service._logger.log_turn.side_effect = boom

            turn = await service.start_or_continue("The weather is nice today")
            assert turn.turn_number == 1
            service._logger.log_turn.assert_called_once()


class TestDebateLogger:
    def test_unavailable_with_placeholder_dsn(self):
        from backend.app.services.debate_logger import DebateLogger

        logger_ = DebateLogger(dsn="postgresql+asyncpg://logiscan:REPLACE_ME@localhost/logiscan")
        assert not logger_.available

    def test_unavailable_with_empty_dsn(self):
        from backend.app.services.debate_logger import DebateLogger

        assert not DebateLogger(dsn="").available

    def test_log_turn_handles_connect_failure(self):
        from backend.app.services.debate_logger import DebateLogger

        logger_ = DebateLogger(dsn="postgresql+asyncpg://user:pass@localhost/logiscan")
        assert logger_.available

        fake_asyncpg = MagicMock()

        async def connect_failure(*_args, **_kwargs):
            raise ConnectionRefusedError("no postgres")

        fake_asyncpg.connect = connect_failure
        logger_._warned = False
        turn = MagicMock(session_id="s-1")

        import asyncio

        asyncio.run(logger_.log_turn(turn))
        assert logger_._warned is True

    def test_unavailable_without_asyncpg(self):
        from backend.app.services.debate_logger import DebateLogger

        logger_ = DebateLogger(dsn="postgresql+asyncpg://user:pass@localhost/logiscan")
        assert logger_.available

        import asyncio

        turn = MagicMock(session_id="s-1")
        with patch("backend.app.services.debate_logger.asyncpg", None):
            logger_._warned = False
            asyncio.run(logger_.log_turn(turn))
        assert logger_._warned is True

    @pytest.mark.asyncio
    async def test_log_turn_noop_when_unavailable(self):
        from backend.app.services.debate_logger import DebateLogger

        logger_ = DebateLogger(dsn="")
        turn = MagicMock()
        await logger_.log_turn(turn)
