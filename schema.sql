-- Example schema for the partners database

-- Metadata about partners or users
CREATE TABLE IF NOT EXISTS metadata (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    query_credits_remaining INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Log every API call
CREATE TABLE IF NOT EXISTS calls (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER REFERENCES metadata(id),
    user_id INTEGER,
    conversation_id INTEGER,
    endpoint TEXT NOT NULL,
    question TEXT NOT NULL,
    custom_data JSONB,
    sql_query TEXT,
    response_text TEXT,
    error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
