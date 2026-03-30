-- Coalition map secondary artifact (POST /v1/coalition-map, GET /v1/coalition-map/:receipt_id)
-- Applied automatically via receipt_store.ensure_coalition_maps_table() on API startup;
-- keep this file for manual DBA / review.

CREATE TABLE IF NOT EXISTS coalition_maps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id TEXT NOT NULL UNIQUE REFERENCES frame_receipts(id) ON DELETE CASCADE,
    coalition_id TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL,
    signed BOOLEAN DEFAULT FALSE,
    signature TEXT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coalition_receipt ON coalition_maps (receipt_id);
