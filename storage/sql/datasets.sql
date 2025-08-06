CREATE TABLE IF NOT EXISTS datasets (
    id VARCHAR PRIMARY KEY,
    rel_link VARCHAR,
    abs_link VARCHAR,
    title VARCHAR,
    description TEXT,
    tags VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);