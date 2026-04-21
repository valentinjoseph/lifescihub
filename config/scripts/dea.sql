-- dea.v_company_intelligence source

CREATE OR REPLACE VIEW dea.v_company_intelligence
AS WITH base AS (
         SELECT v_news_all.company_name,
            v_news_all.id,
            v_news_all.url,
            v_news_all.title,
            v_news_all.article_content,
            v_news_all.article_summary,
            v_news_all.key_topic,
            v_news_all.business_impact,
            v_news_all.geography,
            v_news_all.signal_type,
            v_news_all.priority_score,
            v_news_all.summary_model,
            v_news_all.summary_status,
            v_news_all.published_date,
            v_news_all.s_created_ts
           FROM dwh.v_news_all
        ), company_rollup AS (
         SELECT base.company_name,
            count(*) AS articles_all,
            count(*) FILTER (WHERE base.published_date >= (now() - '7 days'::interval)) AS articles_last_7_days,
            count(*) FILTER (WHERE base.published_date >= (now() - '1 mon'::interval)) AS articles_last_30_days,
            count(*) FILTER (WHERE base.published_date >= (now() - '6 mons'::interval)) AS articles_last_6_months,
            count(*) FILTER (WHERE base.published_date >= (now() - '1 mon'::interval) AND base.priority_score >= 75) AS high_priority_last_30_days,
            round(avg(base.priority_score) FILTER (WHERE base.published_date >= (now() - '1 mon'::interval)), 1) AS avg_priority_last_30_days,
            max(base.priority_score) FILTER (WHERE base.published_date >= (now() - '1 mon'::interval)) AS top_priority_score_30_days,
            max(base.published_date) AS latest_published_date
           FROM base
          GROUP BY base.company_name
        ), topic_counts AS (
         SELECT base.company_name,
            COALESCE(NULLIF(base.key_topic, ''::text), 'uncategorized'::text) AS key_topic,
            count(*) AS article_count
           FROM base
          WHERE base.published_date >= (now() - '1 mon'::interval)
          GROUP BY base.company_name, (COALESCE(NULLIF(base.key_topic, ''::text), 'uncategorized'::text))
        ), topic_ranked AS (
         SELECT topic_counts.company_name,
            topic_counts.key_topic,
            row_number() OVER (PARTITION BY topic_counts.company_name ORDER BY topic_counts.article_count DESC, topic_counts.key_topic) AS topic_rank
           FROM topic_counts
        ), signal_counts AS (
         SELECT base.company_name,
            COALESCE(NULLIF(base.signal_type, ''::text), 'uncategorized'::text) AS signal_type,
            count(*) AS article_count
           FROM base
          WHERE base.published_date >= (now() - '1 mon'::interval)
          GROUP BY base.company_name, (COALESCE(NULLIF(base.signal_type, ''::text), 'uncategorized'::text))
        ), signal_ranked AS (
         SELECT signal_counts.company_name,
            signal_counts.signal_type,
            row_number() OVER (PARTITION BY signal_counts.company_name ORDER BY signal_counts.article_count DESC, signal_counts.signal_type) AS signal_rank
           FROM signal_counts
        )
 SELECT rollup.company_name,
    rollup.articles_last_7_days,
    rollup.articles_last_30_days,
    rollup.articles_last_6_months,
    rollup.articles_all,
    rollup.high_priority_last_30_days,
    rollup.avg_priority_last_30_days,
    rollup.top_priority_score_30_days,
    COALESCE(topic.key_topic, 'no recent topic'::text) AS leading_topic_last_30_days,
    COALESCE(signal.signal_type, 'no recent signal'::text) AS leading_signal_last_30_days,
    rollup.latest_published_date,
        CASE
            WHEN rollup.high_priority_last_30_days >= 3 THEN 'high'::text
            WHEN rollup.high_priority_last_30_days >= 1 THEN 'medium'::text
            ELSE 'watch'::text
        END AS attention_level
   FROM company_rollup rollup
     LEFT JOIN topic_ranked topic ON topic.company_name = rollup.company_name AND topic.topic_rank = 1
     LEFT JOIN signal_ranked signal ON signal.company_name = rollup.company_name AND signal.signal_rank = 1;



-- dea.v_executive_news_feed source

CREATE OR REPLACE VIEW dea.v_executive_news_feed
AS SELECT company_name,
    published_date,
    priority_score,
        CASE
            WHEN priority_score >= 90 THEN 'critical'::text
            WHEN priority_score >= 75 THEN 'high'::text
            WHEN priority_score >= 60 THEN 'medium'::text
            ELSE 'standard'::text
        END AS priority_band,
    title,
    article_summary,
    key_topic,
    business_impact,
    geography,
    signal_type,
    url
   FROM dwh.v_news_month
  WHERE priority_score >= 75 OR published_date >= (now() - '7 days'::interval);


-- dea.v_kpi_overview source

CREATE OR REPLACE VIEW dea.v_kpi_overview
AS WITH base AS (
         SELECT v_news_all.company_name,
            v_news_all.id,
            v_news_all.url,
            v_news_all.title,
            v_news_all.article_content,
            v_news_all.article_summary,
            v_news_all.key_topic,
            v_news_all.business_impact,
            v_news_all.geography,
            v_news_all.signal_type,
            v_news_all.priority_score,
            v_news_all.summary_model,
            v_news_all.summary_status,
            v_news_all.published_date,
            v_news_all.s_created_ts
           FROM dwh.v_news_all
        ), metrics AS (
         SELECT 'total_articles'::text AS metric,
            count(*)::numeric AS numeric_value,
            'All articles in the reporting warehouse'::text AS metric_label
           FROM base
        UNION ALL
         SELECT 'articles_last_7_days'::text,
            count(*) FILTER (WHERE base.published_date >= (now() - '7 days'::interval))::numeric AS count,
            'Articles published in the rolling last 7 days'::text
           FROM base
        UNION ALL
         SELECT 'articles_last_30_days'::text,
            count(*) FILTER (WHERE base.published_date >= (now() - '1 mon'::interval))::numeric AS count,
            'Articles published in the rolling last month'::text
           FROM base
        UNION ALL
         SELECT 'high_priority_last_30_days'::text,
            count(*) FILTER (WHERE base.published_date >= (now() - '1 mon'::interval) AND base.priority_score >= 75)::numeric AS count,
            'High-priority articles in the rolling last month'::text
           FROM base
        UNION ALL
         SELECT 'active_companies_last_30_days'::text,
            count(DISTINCT base.company_name) FILTER (WHERE base.published_date >= (now() - '1 mon'::interval))::numeric AS count,
            'Companies with at least one article in the rolling last month'::text
           FROM base
        UNION ALL
         SELECT 'articles_missing_summary'::text,
            count(*) FILTER (WHERE base.article_summary IS NULL OR base.summary_status IS DISTINCT FROM 'completed'::text)::numeric AS count,
            'Articles still missing a completed AI summary'::text
           FROM base
        )
 SELECT metric,
    numeric_value,
    numeric_value::text AS metric_value,
    metric_label,
    now() AS generated_at
   FROM metrics;

-- dea.v_topic_signal_heatmap source

CREATE OR REPLACE VIEW dea.v_topic_signal_heatmap
AS SELECT COALESCE(NULLIF(key_topic, ''::text), 'uncategorized'::text) AS key_topic,
    COALESCE(NULLIF(signal_type, ''::text), 'uncategorized'::text) AS signal_type,
    count(*) AS articles_last_30_days,
    count(*) FILTER (WHERE priority_score >= 75) AS high_priority_last_30_days,
    count(DISTINCT company_name) AS companies_last_30_days,
    round(avg(priority_score), 1) AS avg_priority_score,
    max(published_date) AS latest_published_date
   FROM dwh.v_news_month
  GROUP BY (COALESCE(NULLIF(key_topic, ''::text), 'uncategorized'::text)), (COALESCE(NULLIF(signal_type, ''::text), 'uncategorized'::text));