-- PostgreSQL DDL for tech.ls_load_monitoring
CREATE TABLE tech.ls_load_monitoring (
    run_id TEXT NOT NULL,
    run_name VARCHAR(100) NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    target_schema VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    load_type VARCHAR(20) NOT NULL,
    run_status VARCHAR(20) NOT NULL,
    run_message TEXT,
    records_inserted BIGINT DEFAULT 0 NOT NULL,
    urls_attempted BIGINT DEFAULT 0 NOT NULL,
    urls_fetched BIGINT DEFAULT 0 NOT NULL,
    parse_success_count BIGINT DEFAULT 0 NOT NULL,
    avg_response_time_ms DOUBLE PRECISION DEFAULT 0 NOT NULL,
    error_count BIGINT DEFAULT 0 NOT NULL,
    run_start_ts TIMESTAMPTZ DEFAULT now() NOT NULL,
    run_end_ts TIMESTAMPTZ DEFAULT now() NOT NULL
);
