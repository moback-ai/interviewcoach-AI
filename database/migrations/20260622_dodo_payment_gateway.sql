-- Dodo payment gateway: checkout intents, webhook events, payments extensions

CREATE TABLE IF NOT EXISTS checkout_intents (
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
    CONSTRAINT checkout_intents_status_check CHECK (
        status IN ('pending', 'failed', 'fulfilled', 'paid_needs_review')
    )
);

CREATE INDEX IF NOT EXISTS idx_checkout_intents_user_created ON checkout_intents(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkout_intents_status ON checkout_intents(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_checkout_intents_dodo_session
    ON checkout_intents(dodo_session_id) WHERE dodo_session_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS webhook_events (
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

CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status);

ALTER TABLE payments
    ALTER COLUMN interview_id DROP NOT NULL;

ALTER TABLE payments
    ALTER COLUMN provider SET DEFAULT 'dodo';

ALTER TABLE payments
    ALTER COLUMN payment_status SET DEFAULT 'pending';

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS checkout_intent_id UUID REFERENCES checkout_intents(id) ON DELETE SET NULL;

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Store amounts in paise (49900 = INR 499.00)
ALTER TABLE payments
    ALTER COLUMN amount TYPE BIGINT USING (
        CASE
            WHEN amount IS NULL THEN 0
            WHEN amount < 10000 THEN (amount * 100)::bigint
            ELSE amount::bigint
        END
    );

CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_transaction_id ON payments(transaction_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_checkout_intent_id
    ON payments(checkout_intent_id) WHERE checkout_intent_id IS NOT NULL;
