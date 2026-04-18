-- PostgreSQL DDL for tech.ls_scraping_config
CREATE TABLE tech.ls_scraping_config (
    param_name VARCHAR(100) PRIMARY KEY,
    param_value TEXT NOT NULL,
    description TEXT,
    s_created_ts TIMESTAMPTZ DEFAULT now() NOT NULL,
    s_modified_ts TIMESTAMPTZ DEFAULT now() NOT NULL
);


-- PostgreSQL DML for ls_scraping_config table
INSERT INTO tech.ls_scraping_config (param_name, param_value, description, s_created_ts, s_modified_ts) VALUES
('ARTICLE_SLEEP_SEC', '0.15', 'Sleep time between article requests', '2026-04-13 12:42:35.435', '2026-04-13 12:42:35.435'),
('LISTING_SLEEP_SEC', '0.2', 'Sleep time between listing page requests', '2026-04-13 12:42:35.435', '2026-04-13 12:42:35.435'),
('MAX_ITEMS_PER_SOURCE', '50', 'Maximum articles to fetch per source', '2026-04-13 12:42:35.435', '2026-04-13 12:42:35.435'),
('MAX_PARTITIONS', '100', 'Maximum number of partitions for parallel processing', '2026-04-13 12:42:35.435', '2026-04-13 12:42:35.435'),
('MIN_PARTITIONS', '10', 'Minimum number of partitions for parallel processing', '2026-04-13 12:42:35.435', '2026-04-13 12:42:35.435'),
('MIN_TITLE_LENGTH', '10', 'Minimum acceptable title length', '2026-04-13 12:42:35.435', '2026-04-13 12:42:35.435'),
('REQUEST_TIMEOUT_SEC', '25', 'HTTP request timeout in seconds', '2026-04-13 12:42:35.435', '2026-04-13 12:42:35.435');
