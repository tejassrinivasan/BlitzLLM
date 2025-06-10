-- Example schema for the partners database

-- Metadata about partners or users
CREATE TABLE IF NOT EXISTS metadata (
    partner_id SERIAL PRIMARY KEY,
    partner_name TEXT NOT NULL,
    contact_name TEXT, 
    contact_email TEXT, 
    api_expiration_date DATE,
    query_credits_remaining INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Log every API call
CREATE TABLE IF NOT EXISTS calls (
    call_id SERIAL PRIMARY KEY,
    partner_id INTEGER REFERENCES metadata(partner_id),
    partner_payload JSONB, 
    response_payload JSONB,
    endpoint TEXT NOT NULL,
    error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS conversations;
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id VARCHAR(64) PRIMARY KEY,
    partner_id INTEGER REFERENCES metadata(partner_id),
    user_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(), 
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

DROP TABLE IF EXISTS messages;
create table if not exists messages (
    conversation_id VARCHAR(64) REFERENCES conversations(conversation_id),
    message_id INTEGER,
    partner_id INTEGER REFERENCES metadata(partner_id),
    role TEXT,
    content TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)