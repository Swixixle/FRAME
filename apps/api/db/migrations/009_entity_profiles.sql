-- Persistent entity profiles + evidence accumulation (PUBLIC EYE dossier upgrade)
-- Applied via receipt_store.ensure_entity_profiles_tables()

CREATE TABLE IF NOT EXISTS entity_profiles (
    entity_slug         TEXT PRIMARY KEY,
    entity_name         TEXT NOT NULL,
    entity_type         TEXT NOT NULL CHECK (entity_type IN (
                            'journalist', 'commentator', 'anchor',
                            'outlet', 'think_tank', 'podcast', 'wire_service'
                        )),
    current_affiliation TEXT,

    integrity_json      JSONB,
    contradiction_json  JSONB,
    funding_json        JSONB,
    factcheck_json      JSONB,

    generated_headline  TEXT,
    executive_summary   TEXT,
    the_gap             TEXT,
    verdict_tags        JSONB,

    overall_integrity   TEXT CHECK (overall_integrity IN (
                            'compromised', 'questionable', 'acceptable',
                            'strong', 'insufficient_data'
                        )),

    signature           TEXT,
    public_key          TEXT,
    content_hash        TEXT,

    is_static           BOOLEAN DEFAULT FALSE,
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evidence_count      INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_entity_profiles_type
    ON entity_profiles (entity_type);

CREATE INDEX IF NOT EXISTS idx_entity_profiles_affiliation
    ON entity_profiles (current_affiliation);

CREATE TABLE IF NOT EXISTS entity_evidence_log (
    id              BIGSERIAL PRIMARY KEY,
    entity_slug     TEXT NOT NULL REFERENCES entity_profiles(entity_slug) ON DELETE CASCADE,
    evidence_type   TEXT NOT NULL CHECK (evidence_type IN (
                        'statement', 'fec_donation', 'court_case',
                        'fact_check_verdict', 'retraction', 'correction',
                        'advertiser_relationship', 'beat_coverage', 'quote'
                    )),
    evidence_json   JSONB NOT NULL,
    source_url      TEXT,
    article_url     TEXT,
    found_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    receipt_id      TEXT
);

CREATE INDEX IF NOT EXISTS idx_evidence_entity_type
    ON entity_evidence_log (entity_slug, evidence_type);

CREATE INDEX IF NOT EXISTS idx_evidence_found_at
    ON entity_evidence_log (found_at DESC);
