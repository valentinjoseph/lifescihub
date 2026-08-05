CREATE SCHEMA IF NOT EXISTS dwh;
CREATE SCHEMA IF NOT EXISTS dea;

DROP VIEW IF EXISTS dea.v_executive_news_feed;
DROP VIEW IF EXISTS dea.v_topic_signal_heatmap;
DROP VIEW IF EXISTS dea.v_company_intelligence;
DROP VIEW IF EXISTS dea.v_kpi_overview;
DROP VIEW IF EXISTS dwh.v_top_news_month_export;
DROP VIEW IF EXISTS dwh.v_top_news_week_export;
DROP VIEW IF EXISTS dwh.v_top_news_month;
DROP VIEW IF EXISTS dwh.v_top_news_week;
DROP VIEW IF EXISTS dwh.v_news_week_export;
DROP VIEW IF EXISTS dwh.v_news_month_export;
DROP VIEW IF EXISTS dwh.v_news_6_months_export;
DROP VIEW IF EXISTS dwh.v_news_all_export;
DROP VIEW IF EXISTS dwh.v_news_week;
DROP VIEW IF EXISTS dwh.v_news_month;
DROP VIEW IF EXISTS dwh.v_news_6_months;
DROP VIEW IF EXISTS dwh.v_news_all;
DROP FUNCTION IF EXISTS dwh.f_news_staging_articles();

CREATE OR REPLACE FUNCTION dwh.f_news_staging_articles()
RETURNS TABLE (
    company_name TEXT,
    industry_sector TEXT,
    id TEXT,
    url TEXT,
    title TEXT,
    published_date TIMESTAMPTZ,
    s_created_ts TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    staging_table RECORD;
    company_label TEXT;
    industry_label TEXT;
BEGIN
    FOR staging_table IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname ILIKE 'stg%'
          AND tablename ILIKE 'stg%'
        ORDER BY schemaname, tablename
    LOOP
        company_label := upper(replace(regexp_replace(staging_table.tablename, '^stg_', '', 'i'), '_', ' '));
        industry_label := upper(replace(regexp_replace(staging_table.schemaname, '^stg_', '', 'i'), '_', ' '));

        RETURN QUERY EXECUTE format(
            'SELECT %L::text AS company_name,
                    %L::text AS industry_sector,
                    id::text,
                    url::text,
                    title::text,
                    published_date::timestamptz,
                    s_created_ts::timestamptz
             FROM %I.%I',
            company_label,
            industry_label,
            staging_table.schemaname,
            staging_table.tablename
        );
    END LOOP;
END;
$$;

CREATE OR REPLACE VIEW dwh.v_news_all AS
WITH src AS (
    SELECT *
    FROM dwh.f_news_staging_articles()
)
SELECT
    src.company_name,
    src.industry_sector,
    src.id,
    src.url,
    src.title,
    summary.article_summary,
    summary.key_topic,
    summary.business_impact,
    summary.geography,
    summary.signal_type,
    CASE
        WHEN COALESCE(summary.signal_type, '') IN ('approval', 'acquisition', 'merger', 'trial-readout', 'earnings') THEN 95
        WHEN COALESCE(summary.key_topic, '') IN ('regulatory', 'm&a', 'financial') THEN 88
        WHEN COALESCE(summary.signal_type, '') IN ('partnership', 'plant-expansion', 'launch') THEN 80
        WHEN COALESCE(summary.key_topic, '') IN ('clinical', 'partnership', 'manufacturing', 'product') THEN 72
        WHEN lower(COALESCE(src.title, '')) LIKE '%phase 3%' THEN 84
        WHEN lower(COALESCE(src.title, '')) LIKE '%fda%' THEN 90
        WHEN lower(COALESCE(src.title, '')) LIKE '%acquisition%' THEN 92
        WHEN lower(COALESCE(src.title, '')) LIKE '%earnings%' THEN 90
        ELSE 55
    END AS priority_score,
    summary.summary_model,
    summary.summary_status,
    src.published_date,
    src.s_created_ts
FROM src
LEFT JOIN tech.ls_article_summary AS summary
    ON summary.article_id = src.id
LEFT JOIN tech.ls_title_exclusion AS exclusion
    ON exclusion.id = src.id
WHERE exclusion.id IS NULL;

CREATE OR REPLACE VIEW dwh.v_news_week AS
SELECT *
FROM dwh.v_news_all
WHERE published_date >= now() - INTERVAL '7 days';

CREATE OR REPLACE VIEW dwh.v_news_month AS
SELECT *
FROM dwh.v_news_all
WHERE published_date >= now() - INTERVAL '1 month';

CREATE OR REPLACE VIEW dwh.v_news_6_months AS
SELECT *
FROM dwh.v_news_all
WHERE published_date >= now() - INTERVAL '6 months';

CREATE OR REPLACE VIEW dwh.v_top_news_week AS
SELECT *
FROM dwh.v_news_week
WHERE priority_score >= 72;

CREATE OR REPLACE VIEW dwh.v_top_news_month AS
SELECT *
FROM dwh.v_news_month
WHERE priority_score >= 75;

CREATE OR REPLACE VIEW dwh.v_news_all_export AS
SELECT
    company_name,
    industry_sector,
    published_date,
    priority_score,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url,
    summary_status
FROM dwh.v_news_all;

CREATE OR REPLACE VIEW dwh.v_news_week_export AS
SELECT
    company_name,
    industry_sector,
    published_date,
    priority_score,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url,
    summary_status
FROM dwh.v_news_week;

CREATE OR REPLACE VIEW dwh.v_news_month_export AS
SELECT
    company_name,
    industry_sector,
    published_date,
    priority_score,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url,
    summary_status
FROM dwh.v_news_month;

CREATE OR REPLACE VIEW dwh.v_news_6_months_export AS
SELECT
    company_name,
    industry_sector,
    published_date,
    priority_score,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url,
    summary_status
FROM dwh.v_news_6_months;

CREATE OR REPLACE VIEW dwh.v_top_news_week_export AS
SELECT
    company_name,
    industry_sector,
    published_date,
    priority_score,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url,
    summary_status
FROM dwh.v_top_news_week;

CREATE OR REPLACE VIEW dwh.v_top_news_month_export AS
SELECT
    company_name,
    industry_sector,
    published_date,
    priority_score,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url,
    summary_status
FROM dwh.v_top_news_month;

CREATE OR REPLACE VIEW dea.v_kpi_overview AS
WITH base AS (
    SELECT *
    FROM dwh.v_news_all
),
metrics AS (
    SELECT
        'total_articles' AS metric,
        COUNT(*)::NUMERIC AS numeric_value,
        'All articles in the reporting warehouse' AS metric_label
    FROM base
    UNION ALL
    SELECT
        'articles_last_7_days',
        COUNT(*) FILTER (WHERE published_date >= now() - INTERVAL '7 days')::NUMERIC,
        'Articles published in the rolling last 7 days'
    FROM base
    UNION ALL
    SELECT
        'articles_last_30_days',
        COUNT(*) FILTER (WHERE published_date >= now() - INTERVAL '1 month')::NUMERIC,
        'Articles published in the rolling last month'
    FROM base
    UNION ALL
    SELECT
        'high_priority_last_30_days',
        COUNT(*) FILTER (
            WHERE published_date >= now() - INTERVAL '1 month'
              AND priority_score >= 75
        )::NUMERIC,
        'High-priority articles in the rolling last month'
    FROM base
    UNION ALL
    SELECT
        'active_companies_last_30_days',
        COUNT(DISTINCT company_name) FILTER (
            WHERE published_date >= now() - INTERVAL '1 month'
        )::NUMERIC,
        'Companies with at least one article in the rolling last month'
    FROM base
    UNION ALL
    SELECT
        'articles_missing_summary',
        COUNT(*) FILTER (
            WHERE article_summary IS NULL
               OR summary_status NOT IN ('ai', 'fallback')
        )::NUMERIC,
        'Articles still missing a completed AI summary'
    FROM base
)
SELECT
    metric,
    numeric_value,
    numeric_value::TEXT AS metric_value,
    metric_label,
    now() AS generated_at
FROM metrics;

CREATE OR REPLACE VIEW dea.v_company_intelligence AS
WITH base AS (
    SELECT *
    FROM dwh.v_news_all
),
company_rollup AS (
    SELECT
        industry_sector,
        company_name,
        COUNT(*) AS articles_all,
        COUNT(*) FILTER (WHERE published_date >= now() - INTERVAL '7 days') AS articles_last_7_days,
        COUNT(*) FILTER (WHERE published_date >= now() - INTERVAL '1 month') AS articles_last_30_days,
        COUNT(*) FILTER (WHERE published_date >= now() - INTERVAL '6 months') AS articles_last_6_months,
        COUNT(*) FILTER (
            WHERE published_date >= now() - INTERVAL '1 month'
              AND priority_score >= 75
        ) AS high_priority_last_30_days,
        ROUND(AVG(priority_score) FILTER (
            WHERE published_date >= now() - INTERVAL '1 month'
        )::NUMERIC, 1) AS avg_priority_last_30_days,
        MAX(priority_score) FILTER (
            WHERE published_date >= now() - INTERVAL '1 month'
        ) AS top_priority_score_30_days,
        MAX(published_date) AS latest_published_date
    FROM base
    GROUP BY industry_sector, company_name
),
topic_counts AS (
    SELECT
        industry_sector,
        company_name,
        COALESCE(NULLIF(key_topic, ''), 'uncategorized') AS key_topic,
        COUNT(*) AS article_count
    FROM base
    WHERE published_date >= now() - INTERVAL '1 month'
    GROUP BY industry_sector, company_name, COALESCE(NULLIF(key_topic, ''), 'uncategorized')
),
topic_ranked AS (
    SELECT
        industry_sector,
        company_name,
        key_topic,
        ROW_NUMBER() OVER (
            PARTITION BY industry_sector, company_name
            ORDER BY article_count DESC, key_topic
        ) AS topic_rank
    FROM topic_counts
),
signal_counts AS (
    SELECT
        industry_sector,
        company_name,
        COALESCE(NULLIF(signal_type, ''), 'uncategorized') AS signal_type,
        COUNT(*) AS article_count
    FROM base
    WHERE published_date >= now() - INTERVAL '1 month'
    GROUP BY industry_sector, company_name, COALESCE(NULLIF(signal_type, ''), 'uncategorized')
),
signal_ranked AS (
    SELECT
        industry_sector,
        company_name,
        signal_type,
        ROW_NUMBER() OVER (
            PARTITION BY industry_sector, company_name
            ORDER BY article_count DESC, signal_type
        ) AS signal_rank
    FROM signal_counts
)
SELECT
    rollup.industry_sector,
    rollup.company_name,
    rollup.articles_last_7_days,
    rollup.articles_last_30_days,
    rollup.articles_last_6_months,
    rollup.articles_all,
    rollup.high_priority_last_30_days,
    rollup.avg_priority_last_30_days,
    rollup.top_priority_score_30_days,
    COALESCE(topic.key_topic, 'no recent topic') AS leading_topic_last_30_days,
    COALESCE(signal.signal_type, 'no recent signal') AS leading_signal_last_30_days,
    rollup.latest_published_date,
    CASE
        WHEN rollup.high_priority_last_30_days >= 3 THEN 'high'
        WHEN rollup.high_priority_last_30_days >= 1 THEN 'medium'
        ELSE 'watch'
    END AS attention_level
FROM company_rollup AS rollup
LEFT JOIN topic_ranked AS topic
    ON topic.industry_sector = rollup.industry_sector
   AND topic.company_name = rollup.company_name
   AND topic.topic_rank = 1
LEFT JOIN signal_ranked AS signal
    ON signal.industry_sector = rollup.industry_sector
   AND signal.company_name = rollup.company_name
   AND signal.signal_rank = 1;

CREATE OR REPLACE VIEW dea.v_topic_signal_heatmap AS
SELECT
    industry_sector,
    COALESCE(NULLIF(key_topic, ''), 'uncategorized') AS key_topic,
    COALESCE(NULLIF(signal_type, ''), 'uncategorized') AS signal_type,
    COUNT(*) AS articles_last_30_days,
    COUNT(*) FILTER (WHERE priority_score >= 75) AS high_priority_last_30_days,
    COUNT(DISTINCT company_name) AS companies_last_30_days,
    ROUND(AVG(priority_score)::NUMERIC, 1) AS avg_priority_score,
    MAX(published_date) AS latest_published_date
FROM dwh.v_news_month
GROUP BY
    industry_sector,
    COALESCE(NULLIF(key_topic, ''), 'uncategorized'),
    COALESCE(NULLIF(signal_type, ''), 'uncategorized');

CREATE OR REPLACE VIEW dea.v_executive_news_feed AS
SELECT
    industry_sector,
    company_name,
    published_date,
    priority_score,
    CASE
        WHEN priority_score >= 90 THEN 'critical'
        WHEN priority_score >= 75 THEN 'high'
        WHEN priority_score >= 60 THEN 'medium'
        ELSE 'standard'
    END AS priority_band,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url
FROM dwh.v_news_month
WHERE priority_score >= 75
   OR published_date >= now() - INTERVAL '7 days';
