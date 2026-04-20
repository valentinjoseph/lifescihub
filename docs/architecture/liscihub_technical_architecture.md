# LISCIHUB Technical Architecture

This document describes the technical architecture behind Life Science Watch / LISCIHUB. It is intended for engineering reviews, corporate presentations, and handover documentation.

## End-To-End System Schema

```mermaid
flowchart LR
    subgraph Admin["Admin workstation: Mac"]
        VSCode["VS Code over SSH"]
        Browser["Browser dashboard access"]
        DBeaver["DBeaver via SSH tunnel"]
        Terminal["Terminal / SSH"]
    end

    subgraph Sources["External company sources"]
        Newsrooms["Corporate newsroom pages"]
        Articles["Article / press-release pages"]
        Robots["robots.txt / source constraints"]
    end

    subgraph Lenovo["Lenovo Ubuntu Server"]
        Cron["Host cron<br/>08:00 UTC daily"]
        Runner["scripts/run_daily_pipeline.sh<br/>flock-protected runner"]

        subgraph Compose["lifescience_watch Docker Compose stack"]
            App["lifescience_watch<br/>FastAPI + Python pipeline"]
            Postgres["liscihub-postgres<br/>PostgreSQL 16"]
        end

        subgraph Repo["Application code"]
            Orchestrator["orchestration/LS_MAIN_REFACTORED.py"]
            Scraper["core/scraper.py<br/>utils/url_extractor.py<br/>utils/robots_compliance.py"]
            Summaries["scripts/generate_article_summaries.py"]
            Exporter["scripts/export_dwh_views.py"]
            DriveSync["scripts/upload_export_to_gdrive.sh"]
            ViewsSQL["config/scripts/dwh_views.sql"]
        end

        subgraph Files["Local file outputs"]
            Logs["outputs/*.log<br/>outputs/latest_results.csv"]
            Workbook["exports/lifescience_watch_news_latest.xlsx"]
            Archive["exports/lifescience_watch_news_*.xlsx"]
        end
    end

    subgraph DB["PostgreSQL logical layers"]
        Tech["tech schema<br/>config, monitoring, summaries"]
        Staging["stg_ls_* schemas<br/>company staging tables"]
        DWH["dwh schema<br/>reporting/export views"]
    end

    subgraph AI["AI enrichment"]
        OpenAI["OpenAI API<br/>summary + topic + impact + signal"]
    end

    subgraph Delivery["Delivery layer"]
        Caddy["Caddy reverse proxy<br/>HTTPS termination"]
        Hostinger["Hostinger DNS<br/>life-science-news.com"]
        Dashboard["Web dashboard<br/>filters + news cards + chat"]
        Viewer["Viewer login<br/>secure read-only cookie"]
        GDrive["Google Drive<br/>shared Excel workbook"]
        ExcelUsers["Business users<br/>Excel consumption"]
    end

    VSCode --> Terminal
    Terminal --> Lenovo
    DBeaver -->|SSH tunnel 5434| Postgres
    Browser --> Dashboard

    Cron --> Runner
    Runner --> Orchestrator
    Orchestrator --> Scraper
    Scraper --> Robots
    Scraper --> Newsrooms
    Newsrooms --> Articles
    Scraper --> Staging

    Orchestrator --> Tech
    Summaries --> OpenAI
    Summaries --> Tech
    Staging --> DWH
    Tech --> DWH
    ViewsSQL --> DWH
    DWH --> Exporter
    Exporter --> Workbook
    Exporter --> Archive
    DriveSync --> GDrive
    Workbook --> DriveSync
    GDrive --> ExcelUsers

    App --> Postgres
    Postgres --> Tech
    Postgres --> Staging
    Postgres --> DWH
    App --> Dashboard
    App --> Viewer

    Hostinger --> Caddy
    Caddy -->|edge_proxy Docker network| App
    Dashboard --> DWH
```

## Daily Pipeline Flow

```mermaid
sequenceDiagram
    participant Cron as Host cron
    participant Runner as run_daily_pipeline.sh
    participant Scrape as Scraper pipeline
    participant PG as liscihub Postgres
    participant AI as OpenAI API
    participant Export as Excel exporter
    participant Drive as Google Drive

    Cron->>Runner: Start daily job at 08:00 UTC
    Runner->>Runner: Acquire flock lock
    Runner->>Scrape: python -m orchestration.LS_MAIN_REFACTORED
    Scrape->>PG: Read tech.ls_load_sources
    Scrape->>PG: Read tech.ls_load_config FULL/DELTA mode
    Scrape->>Scrape: Fetch listing URLs and article URLs
    Scrape->>PG: Merge articles into stg_ls_* tables
    Scrape->>PG: Write run metrics to tech.ls_load_monitoring
    Runner->>AI: python scripts/generate_article_summaries.py
    AI->>PG: Read staged articles needing summaries
    AI->>AI: Generate summary, topic, impact, geography, signal
    AI->>PG: Upsert tech.ls_article_summary
    Runner->>Export: python scripts/export_dwh_views.py
    Export->>PG: Read dwh export views
    Export->>Export: Build styled Excel workbook
    Export->>Drive: ./scripts/upload_export_to_gdrive.sh
    Drive-->>Runner: Upload complete
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

    subgraph Staging["company staging schemas"]
        Stg1["stg_ls_sanofi.stg_sanofi_ingest"]
        Stg2["stg_ls_servier.stg_servier_ingest"]
        Stg3["stg_ls_viatris.stg_viatris_ingest"]
        StgN["stg_ls_*<br/>one schema/table family per company"]
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
    TopWeek --> ExportViews
    TopMonth --> ExportViews
```

## Web And Security Path

```mermaid
flowchart LR
    subgraph Public["Public internet"]
        User["Viewer / stakeholder browser"]
        Admin["Admin browser / SSH"]
        Domain["life-science-news.com<br/>Hostinger DNS"]
    end

    subgraph Edge["Lenovo edge"]
        Caddy["nasahub-caddy<br/>HTTPS, HSTS, reverse proxy"]
        EdgeNet["edge_proxy Docker network"]
    end

    subgraph AppStack["lifescience_watch stack"]
        App["FastAPI app<br/>dashboard, chat, API"]
        PG["liscihub-postgres<br/>localhost-bound DB port"]
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
| Admin | Mac + VS Code SSH | Remote development and operational control |
| Host | Lenovo Ubuntu Server | Runs Docker, Postgres, cron, exports, and proxy integration |
| App | `lifescience_watch` container | FastAPI dashboard, API, chat, and operational endpoints |
| Database | `liscihub-postgres` | Dedicated PostgreSQL database for LISCIHUB |
| Ingestion | `orchestration/LS_MAIN_REFACTORED.py` | Main scrape pipeline and company-level loading |
| Scraping | `core/scraper.py`, `utils/*` | Source fetch, robots handling, URL extraction, article parsing |
| AI | `scripts/generate_article_summaries.py` | OpenAI-backed summaries and structured business-watch fields |
| Reporting | `config/scripts/dwh_views.sql` | DWH views, priority score, top-news/export views |
| Export | `scripts/export_dwh_views.py` | Styled Excel workbook generation |
| Distribution | `scripts/upload_export_to_gdrive.sh` | `rclone` upload to Google Drive |
| Public site | Caddy + Hostinger DNS | HTTPS reverse proxy and public domain |

## Operational Notes

- The scheduled job runs at `08:00 UTC` from the Lenovo host crontab.
- `week` in the dashboard means a rolling last-7-days window, not a Monday-start calendar week.
- The app is bound locally and reached publicly only through the reverse proxy path.
- Viewer access uses a login form and secure cookie; admin operations require the admin token.
- Dashboard chat responses include the article summaries and URLs used as sources to help users verify the answer.
