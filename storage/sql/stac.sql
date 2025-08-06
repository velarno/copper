CREATE SEQUENCE IF NOT EXISTS seq_stac_catalogue_links START 1;
CREATE SEQUENCE IF NOT EXISTS seq_stac_collections START 1;
CREATE SEQUENCE IF NOT EXISTS seq_stac_keywords START 1;
CREATE SEQUENCE IF NOT EXISTS seq_stac_links START 1;

CREATE TABLE IF NOT EXISTS stac_catalogue_links (
    id INTEGER PRIMARY KEY DEFAULT NEXTVAL('seq_stac_catalogue_links'),
    rel VARCHAR,
    mimetype VARCHAR,
    collection_url VARCHAR,
    title VARCHAR,
    last_fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE IF NOT EXISTS stac_collections (
    id INTEGER PRIMARY KEY DEFAULT NEXTVAL('seq_stac_collections'),
    collection_id VARCHAR NOT NULL UNIQUE,
    title VARCHAR,
    description TEXT,
    published_at TIMESTAMP,
    modified_at TIMESTAMP,
    doi VARCHAR,
    last_fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE IF NOT EXISTS stac_keywords (
    id INTEGER PRIMARY KEY DEFAULT NEXTVAL('seq_stac_keywords'),
    keyword VARCHAR,
    collection_id INTEGER,
    FOREIGN KEY (collection_id) REFERENCES stac_collections(id)
);

CREATE TABLE IF NOT EXISTS stac_links (
    id INTEGER PRIMARY KEY DEFAULT NEXTVAL('seq_stac_links'),
    url VARCHAR NOT NULL,
    mimetype VARCHAR,
    title VARCHAR,
    last_fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    collection_id INTEGER,
    FOREIGN KEY (collection_id) REFERENCES stac_collections(id)
);