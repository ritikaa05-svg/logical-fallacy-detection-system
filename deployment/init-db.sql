-- LogiScan Database Initialization
-- Creates tables for debate logging and offline RL training.

-- Debate sessions table
CREATE TABLE IF NOT EXISTS debate_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    total_turns INTEGER DEFAULT 0,
    average_logic_score FLOAT DEFAULT 1.0,
    cumulative_reward FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Debate turns table
CREATE TABLE IF NOT EXISTS debate_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL REFERENCES debate_sessions(session_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,

    -- User input
    user_input TEXT NOT NULL,
    detected_fallacies JSONB DEFAULT '[]',
    logic_score FLOAT DEFAULT 1.0,

    -- Agent response
    agent_action VARCHAR(50) NOT NULL,
    agent_response TEXT NOT NULL,

    -- POMDP state (preserved as JSONB)
    state_before JSONB NOT NULL,
    state_after JSONB NOT NULL,

    -- Reward
    reward FLOAT DEFAULT 0.0,

    -- Metadata
    latency_ms FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_debate_turns_session ON debate_turns(session_id);
CREATE INDEX IF NOT EXISTS idx_debate_turns_created ON debate_turns(created_at);
CREATE INDEX IF NOT EXISTS idx_debate_sessions_created ON debate_sessions(created_at);

-- Create view for training data extraction
CREATE OR REPLACE VIEW rl_training_data AS
SELECT
    state_before->>'fallacy_density' AS fallacy_density,
    state_before->>'argument_depth' AS argument_depth,
    state_before->>'user_sentiment' AS user_sentiment,
    state_before->>'logic_score' AS logic_score,
    agent_action,
    reward,
    state_after->>'fallacy_density' AS next_fallacy_density,
    state_after->>'argument_depth' AS next_argument_depth,
    state_after->>'user_sentiment' AS next_user_sentiment,
    state_after->>'logic_score' AS next_logic_score
FROM debate_turns
ORDER BY created_at DESC;

-- Insert test data (optional)
-- INSERT INTO debate_sessions (session_id) VALUES ('test-session-001');
