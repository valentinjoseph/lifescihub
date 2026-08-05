# GTM Advisor Technical Architecture

This document describes the technical architecture behind GTM Advisor. It is intended for engineering reviews, corporate presentations, and handover documentation.

## End-To-End System Schema

```mermaid
flowchart LR
    subgraph Admin["Developer workstation"]
        VSCode["Editor or terminal"]
        Browser["Browser dashboard access"]
        DBeaver["DBeaver<br/>local or SSH tunnel"]
        Terminal["Terminal / optional SSH"]
    end

    subgraph Sources["External company sources"]
        Newsrooms["Corporate newsroom pages"]
        Articles["Article / press-release pages"]
        Robots["robots.txt / source constraints"]
    end

    subgraph Host["Local or deployment host"]
        Cron["Host cron<br/>08:00 UTC daily"]
        Runner["scripts/run_daily_pipeline.sh<br/>flock-protected runner"]

        subgraph Compose["gtm_advisor Docker Compose stack"]
            App["gtm_advisor<br/>FastAPI + Python pipeline"]
            Postgres["gtm_advisor-postgres<br/>PostgreSQL 16"]
            OllamaSvc["gtm_advisor-ollama<br/>local Ollama model server"]
        end

        subgraph Repo["Application code"]
            Orchestrator["orchestration/LS_MAIN_REFACTORED.py"]
            Scraper["core/scraper.py<br/>utils/url_extractor.py<br/>utils/robots_compliance.py"]
            Summaries["scripts/generate_article_summaries.py"]
            Exporter["scripts/export_dwh_views.py"]
            ViewsSQL["config/scripts/dwh_views.sql"]
        end

        subgraph Files["Local file outputs"]
            Logs["outputs/*.log<br/>outputs/latest_results.csv"]
            Workbook["exports/gtm_advisor_news_latest.xlsx"]
            Archive["exports/gtm_advisor_news_*.xlsx"]
        end
    end

    subgraph DB["PostgreSQL logical layers"]
        Tech["tech schema<br/>config, monitoring, summaries"]
        Staging["stg_<industry_sector> schemas<br/>company staging tables"]
        DWH["dwh schema<br/>reporting/export views"]
        DEA["dea schema<br/>decision-ready consumption marts"]
    end

    subgraph AI["AI enrichment"]
        LocalModel["Ollama llama3.2:3b<br/>summary + topic + impact + chat"]
        OpenAI["Optional OpenAI provider<br/>disabled unless configured"]
    end

    subgraph Delivery["Delivery layer"]
        Caddy["Caddy reverse proxy<br/>HTTPS termination"]
        DNS["DNS provider<br/>your-domain.example"]
        Dashboard["Web dashboard<br/>filters + news cards + chat"]
        Viewer["Viewer login<br/>secure read-only cookie"]
        ExcelUsers["Business users<br/>Excel consumption"]
    end

    VSCode --> Terminal
    Terminal --> Host
    DBeaver -->|local port or SSH tunnel| Postgres
    Browser --> Dashboard

    Cron --> Runner
    Runner --> Orchestrator
    Orchestrator --> Scraper
    Scraper --> Robots
    Scraper --> Newsrooms
    Newsrooms --> Articles
    Scraper --> Staging

    Orchestrator --> Tech
    Summaries --> LocalModel
    App --> LocalModel
    LocalModel --> OllamaSvc
    Summaries --> Tech
    Staging --> DWH
    Tech --> DWH
    ViewsSQL --> DWH
    DWH --> DEA
    ViewsSQL --> DEA
    DWH --> Exporter
    DEA --> Exporter
    Exporter --> Workbook
    Exporter --> Archive
    Workbook --> ExcelUsers

    App --> Postgres
    Postgres --> Tech
    Postgres --> Staging
    Postgres --> DWH
    Postgres --> DEA
    App --> Dashboard
    App --> Viewer

    DNS --> Caddy
    Caddy -->|edge_proxy Docker network| App
    Dashboard --> DWH
    Dashboard --> DEA
```

## Daily Pipeline Flow

```mermaid
sequenceDiagram
    participant Cron as Host cron
    participant Runner as run_daily_pipeline.sh
    participant Scrape as Scraper pipeline
    participant PG as gtm_advisor Postgres
    participant AI as Local Ollama
    participant Export as Excel exporter

    Cron->>Runner: Start daily job at 08:00 UTC
    Runner->>Runner: Acquire flock lock
    Runner->>Scrape: python -m orchestration.LS_MAIN_REFACTORED
    Scrape->>PG: Read tech.ls_load_sources
    Scrape->>PG: Read tech.ls_load_config FULL/DELTA mode
    Scrape->>Scrape: Fetch listing URLs and article URLs
    Scrape->>PG: Merge articles into sector staging schemas
    Scrape->>PG: Write run metrics to tech.ls_load_monitoring
    Runner->>AI: python scripts/generate_article_summaries.py
    AI->>PG: Read staged articles needing summaries
    AI->>AI: Generate summary, topic, impact, geography, signal
    AI->>PG: Upsert tech.ls_article_summary
    Runner->>Export: python scripts/export_dwh_views.py
    Export->>PG: Read dwh and dea export views
    Export->>Export: Build styled Excel workbook
    Runner->>Runner: Release lock and write logs
```

## Database Layer

```mermaid
flowchart TB
    subgraph Tech["tech schema"]
        LoadSources["ls_load_sources<br/>company source URLs"]
        LoadConfig["ls_load_config<br/>active flag + FULL/DELTA"]
        ScrapingConfig["ls_scraping_config<br/>runtime scrape parameters"]
        TitleExclusion["ls_title_exclusion<br/>excluded article IDs"]
        Monitoring["ls_load_monitoring<br/>run metrics and success timestamps"]
        Summary["ls_article_summary<br/>AI summaries + structured fields"]
    end

    subgraph Staging["sector staging schemas"]
        Stg1["stg_lifescience.stg_sanofi"]
        Stg2["stg_lifescience.stg_servier"]
        Stg3["stg_energy.stg_example_energy"]
        StgN["stg_<industry_sector><br/>one schema per sector, one table per company"]
    end

    subgraph DWH["dwh schema"]
        All["v_news_all"]
        Week["v_news_week<br/>rolling last 7 days"]
        Month["v_news_month"]
        SixMonths["v_news_6_months"]
        TopWeek["v_top_news_week"]
        TopMonth["v_top_news_month"]
        ExportViews["*_export views<br/>dashboard + workbook columns"]
    end

    subgraph DEA["dea schema"]
        Kpis["v_kpi_overview"]
        CompanyIntel["v_company_intelligence"]
        TopicSignals["v_topic_signal_heatmap"]
        ExecFeed["v_executive_news_feed"]
    end

    LoadSources --> Staging
    LoadConfig --> Staging
    ScrapingConfig --> Staging
    Staging --> All
    Summary --> All
    TitleExclusion --> All
    All --> Week
    All --> Month
    All --> SixMonths
    Week --> TopWeek
    Month --> TopMonth
    All --> ExportViews
    Week --> ExportViews
    Month --> ExportViews
    SixMonths --> ExportViews
    All --> Kpis
    All --> CompanyIntel
    Month --> TopicSignals
    Month --> ExecFeed
    TopWeek --> ExportViews
    TopMonth --> ExportViews
```

## Web And Security Path

```mermaid
flowchart LR
    subgraph Public["Public internet"]
        User["Viewer / stakeholder browser"]
        Admin["Admin browser / SSH"]
        Domain["your-domain.example<br/>DNS provider"]
    end

    subgraph Edge["Reverse proxy host"]
        Caddy["Caddy or another proxy<br/>HTTPS, HSTS, reverse proxy"]
        EdgeNet["edge_proxy Docker network"]
    end

    subgraph AppStack["gtm_advisor stack"]
        App["FastAPI app<br/>dashboard, chat, API"]
        PG["gtm_advisor-postgres<br/>localhost-bound DB port"]
    end

    subgraph Auth["Application security"]
        ViewerLogin["/viewer login form"]
        ViewerCookie["HttpOnly viewer cookie"]
        AdminToken["Admin token<br/>X-Api-Key / Bearer"]
        RateLimit["Rate limiting<br/>dashboard + chat"]
        Headers["Security headers<br/>CSP, X-Frame-Options, HSTS"]
    end

    User --> Domain
    Domain --> Caddy
    Caddy --> EdgeNet
    EdgeNet --> App
    App --> ViewerLogin
    ViewerLogin --> ViewerCookie
    App --> RateLimit
    App --> Headers
    Admin --> AdminToken
    AdminToken --> App
    App --> PG
```

## Runtime Components

| Layer | Component | Responsibility |
| --- | --- | --- |
| Admin | Developer workstation | Local or remote development and operational control |
| Host | Local machine or deployment server | Runs Docker, Postgres, cron, exports, and optional proxy integration |
| App | `gtm_advisor` container | FastAPI dashboard, API, chat, and operational endpoints |
| Database | `gtm_advisor-postgres` | Dedicated PostgreSQL database for GTM Advisor |
| Ingestion | `orchestration/LS_MAIN_REFACTORED.py` | Main scrape pipeline and company-level loading |
| Scraping | `core/scraper.py`, `utils/*` | Source fetch, robots handling, URL extraction, article parsing |
| AI | `core/llm_client.py`, `scripts/generate_article_summaries.py` | Local Ollama summaries, dashboard chat, and optional OpenAI fallback |
| Reporting | `config/scripts/dwh_views.sql` | DWH views, priority score, top-news/export views, and DEA consumption marts |
| Export | `scripts/export_dwh_views.py` | Styled Excel workbook generation |
| Public site | Reverse proxy + DNS provider | Optional HTTPS reverse proxy and public domain |

## Operational Notes

- The scheduled job runs at `08:00 UTC` from the host crontab when cron is configured.
- `week` in the dashboard means a rolling last-7-days window, not a Monday-start calendar week.
- The app is bound locally and reached publicly only through the reverse proxy path.
- Ollama is also bound locally by Docker Compose and is reached by the app at `http://ollama:11434`.
- Viewer access uses a login form and secure cookie; admin operations require the admin token.
- Dashboard chat responses include the article summaries and URLs used as sources to help users verify the answer.
