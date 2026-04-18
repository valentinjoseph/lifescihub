CREATE SCHEMA IF NOT EXISTS dwh;

DROP VIEW IF EXISTS dwh.v_news_week;
DROP VIEW IF EXISTS dwh.v_news_month;
DROP VIEW IF EXISTS dwh.v_news_6_months;
DROP VIEW IF EXISTS dwh.v_news_all;

CREATE OR REPLACE VIEW dwh.v_news_all AS
WITH src AS (
    SELECT 'ALLIANCE HEALTHCARE' AS company_name, id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_alliance_healthcare.stg_alliance_healthcare_ingest
    UNION ALL
    SELECT 'ASTERA', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_astera.stg_astera_ingest
    UNION ALL
    SELECT 'BIOCODEX', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_biocodex.stg_biocodex_ingest
    UNION ALL
    SELECT 'CEVA SANTE', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_ceva_sante.stg_ceva_sante_ingest
    UNION ALL
    SELECT 'DELPHARM', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_delpharm.stg_delpharm_ingest
    UNION ALL
    SELECT 'EUROFINS', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_eurofins.stg_eurofins_ingest
    UNION ALL
    SELECT 'FAREVA', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_fareva.stg_fareva_ingest
    UNION ALL
    SELECT 'GALDERMA', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_galderma.stg_galderma_ingest
    UNION ALL
    SELECT 'HAELON', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_haelon.stg_haelon_ingest
    UNION ALL
    SELECT 'IPSEN', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_ipsen.stg_ipsen_ingest
    UNION ALL
    SELECT 'LILLY', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_lilly.stg_lilly_ingest
    UNION ALL
    SELECT 'MODERNA', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_moderna.stg_moderna_ingest
    UNION ALL
    SELECT 'OPELLA', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_opella.stg_opella_ingest
    UNION ALL
    SELECT 'OXIPHARM', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_oxipharm.stg_oxipharm_ingest
    UNION ALL
    SELECT 'PFIZER', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_pfizer.stg_pfizer_ingest
    UNION ALL
    SELECT 'PIERRE FABRE', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_pierre_fabre.stg_pierre_fabre_ingest
    UNION ALL
    SELECT 'SANOFI', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_sanofi.stg_sanofi_ingest
    UNION ALL
    SELECT 'SEBIA', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_sebia.stg_sebia_ingest
    UNION ALL
    SELECT 'SERVIER', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_servier.stg_servier_ingest
    UNION ALL
    SELECT 'STAGO', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_stago.stg_stago_ingest
    UNION ALL
    SELECT 'VIATRIS', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_viatris.stg_viatris_ingest
    UNION ALL
    SELECT 'VIRBAC', id, url, title, article_content, published_date, s_created_ts
    FROM stg_ls_virbac.stg_virbac_ingest
)
SELECT
    src.company_name,
    src.id,
    src.url,
    src.title,
    src.article_content,
    summary.article_summary,
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
WHERE published_date >= date_trunc('week', now());

CREATE OR REPLACE VIEW dwh.v_news_month AS
SELECT *
FROM dwh.v_news_all
WHERE published_date >= now() - INTERVAL '1 month';

CREATE OR REPLACE VIEW dwh.v_news_6_months AS
SELECT *
FROM dwh.v_news_all
WHERE published_date >= now() - INTERVAL '6 months';
