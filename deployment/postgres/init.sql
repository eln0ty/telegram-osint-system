-- PostgreSQL bootstrap schema for the Telegram OSINT system.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS collection_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT UNIQUE NOT NULL,
    channel_username TEXT NOT NULL,
    messages_collected INTEGER DEFAULT 0,
    inserted_messages INTEGER DEFAULT 0,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_collection_runs_channel ON collection_runs(channel_username);
CREATE INDEX IF NOT EXISTS idx_collection_runs_start_time ON collection_runs(start_time DESC);

CREATE TABLE IF NOT EXISTS messages (
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    date TIMESTAMPTZ NOT NULL,
    message_hash TEXT NOT NULL,
    channel_username TEXT NOT NULL,
    text TEXT,
    views INTEGER,
    forwards INTEGER,
    replies INTEGER,
    reply_to_message_id BIGINT,
    has_media BOOLEAN,
    media_type TEXT,
    run_id TEXT,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    inserted_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (channel_id, message_id, date)
) PARTITION BY RANGE (date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_hash ON messages (message_hash, date);
CREATE INDEX IF NOT EXISTS idx_messages_channel_date ON messages (channel_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_messages_run_id ON messages (run_id);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_messages_updated_at ON messages;
CREATE TRIGGER set_messages_updated_at
BEFORE UPDATE ON messages
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS ingestion_errors (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    payload JSONB,
    error TEXT
);
