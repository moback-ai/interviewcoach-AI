-- InterviewCoach PostgreSQL Schema
-- Run this on your database server

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table for application authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL DEFAULT '',
    nickname TEXT,
    avatar_url TEXT NOT NULL DEFAULT '',
    date_of_birth DATE,
    gender TEXT,
    plan TEXT NOT NULL DEFAULT 'basic',
    email_verified_at TIMESTAMPTZ,
    verification_sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Resumes
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    stored_path TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT now()
);

-- Job Descriptions
CREATE TABLE job_descriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    file_url TEXT,
    technical BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Interviews
CREATE TABLE interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    jd_id UUID REFERENCES job_descriptions(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    question_set INTEGER,
    retake_from UUID REFERENCES interviews(id),
    attempt_number INTEGER DEFAULT 1 CHECK (attempt_number > 0),
    scheduled_at TIMESTAMPTZ DEFAULT now(),
    active_seconds INTEGER NOT NULL DEFAULT 0,
    ended_at TIMESTAMPTZ,
    CONSTRAINT check_retake_not_self CHECK (retake_from != id)
);

CREATE INDEX idx_interviews_user_id ON interviews(user_id);
CREATE INDEX idx_interviews_retake_from ON interviews(retake_from);
CREATE INDEX idx_interviews_question_set ON interviews(question_set);

-- Questions
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    jd_id UUID REFERENCES job_descriptions(id) ON DELETE SET NULL,
    question_text TEXT NOT NULL,
    expected_answer TEXT,
    difficulty_level TEXT NOT NULL DEFAULT 'medium',
    difficulty_experience TEXT NOT NULL DEFAULT 'beginner',
    question_set INTEGER NOT NULL DEFAULT 1,
    requires_code BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_questions_interview_id ON questions(interview_id);

-- Transcripts
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
    full_transcript TEXT NOT NULL,
    evaluation_data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Interview Feedback
CREATE TABLE interview_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
    key_strengths TEXT,
    improvement_areas TEXT,
    summary TEXT,
    audio_url TEXT,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Overall Evaluation (performance trends)
CREATE TABLE overall_evaluation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_overall_eval_user ON overall_evaluation(user_id, created_at DESC);

-- Checkout intents (created before payment; fulfilled by webhook)
CREATE TABLE checkout_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    jd_id UUID NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    question_set INTEGER NOT NULL,
    retake_from UUID REFERENCES interviews(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    dodo_session_id TEXT,
    amount_paise BIGINT NOT NULL DEFAULT 49900,
    expires_at TIMESTAMPTZ NOT NULL,
    question_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    interview_id UUID REFERENCES interviews(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fulfilled_at TIMESTAMPTZ,
    failure_reason TEXT,
    error_metadata JSONB,
    CONSTRAINT checkout_intents_status_check CHECK (
        status IN (
            'pending', 'failed', 'fulfilled', 'paid_needs_review',
            'expired', 'checkout_creation_failed'
        )
    )
);

CREATE INDEX idx_checkout_intents_user_created ON checkout_intents(user_id, created_at DESC);
CREATE INDEX idx_checkout_intents_status ON checkout_intents(status);
CREATE INDEX idx_checkout_intents_pending_expires
    ON checkout_intents(expires_at) WHERE status = 'pending';
CREATE UNIQUE INDEX idx_checkout_intents_dodo_session
    ON checkout_intents(dodo_session_id) WHERE dodo_session_id IS NOT NULL;

-- Webhook idempotency and retry safety
CREATE TABLE webhook_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received',
    payload JSONB,
    error_message TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    CONSTRAINT webhook_events_status_check CHECK (
        status IN ('received', 'processing', 'processed', 'failed')
    )
);

CREATE INDEX idx_webhook_events_status ON webhook_events(status);

-- Payments (amount stored in paise)
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interview_id UUID REFERENCES interviews(id) ON DELETE SET NULL,
    checkout_intent_id UUID REFERENCES checkout_intents(id) ON DELETE SET NULL,
    amount BIGINT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'dodo',
    payment_status TEXT NOT NULL DEFAULT 'pending',
    transaction_id TEXT NOT NULL,
    metadata JSONB,
    paid_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_payments_transaction_id ON payments(transaction_id);
CREATE UNIQUE INDEX idx_payments_checkout_intent_id
    ON payments(checkout_intent_id) WHERE checkout_intent_id IS NOT NULL;

-- Chat history
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chat_history_interview ON chat_history(interview_id, created_at);

-- User files tracking
CREATE TABLE user_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_type TEXT,
    original_name TEXT,
    stored_path TEXT,
    public_url TEXT,
    file_size INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Password reset tokens
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pwd_reset_user ON password_reset_tokens(user_id, expires_at DESC);

-- Persistent interview sessions (replaces in-memory dict)
CREATE TABLE IF NOT EXISTS interview_sessions (
    session_key TEXT PRIMARY KEY,
    state_json  JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_interview_sessions_updated ON interview_sessions(updated_at);
