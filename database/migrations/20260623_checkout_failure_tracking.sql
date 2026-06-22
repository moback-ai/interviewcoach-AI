-- Checkout failure tracking: lifecycle statuses, metadata, payments.recorded_at

-- 1) checkout_intents: expand status CHECK
ALTER TABLE checkout_intents DROP CONSTRAINT IF EXISTS checkout_intents_status_check;
ALTER TABLE checkout_intents ADD CONSTRAINT checkout_intents_status_check CHECK (
    status IN (
        'pending', 'failed', 'fulfilled', 'paid_needs_review',
        'expired', 'checkout_creation_failed'
    )
);

-- 2) checkout_intents: failure metadata
ALTER TABLE checkout_intents
    ADD COLUMN IF NOT EXISTS failure_reason TEXT,
    ADD COLUMN IF NOT EXISTS error_metadata JSONB;

-- 3) checkout_intents: index for expiry sweeps
CREATE INDEX IF NOT EXISTS idx_checkout_intents_pending_expires
    ON checkout_intents (expires_at)
    WHERE status = 'pending';

-- 4) payments: event timestamp (not paid time for failures)
ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS recorded_at TIMESTAMPTZ;

UPDATE payments
SET recorded_at = COALESCE(paid_at, now())
WHERE recorded_at IS NULL;

ALTER TABLE payments
    ALTER COLUMN recorded_at SET DEFAULT now(),
    ALTER COLUMN recorded_at SET NOT NULL;
