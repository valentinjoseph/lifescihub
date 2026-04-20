"""Render LISCIHUB architecture diagrams as PNG and JPEG images."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


OUT_DIR = Path(__file__).resolve().parent
W, H = 2200, 1400

NAVY = "#08213d"
BLUE = "#2563eb"
MID = "#0f5fa8"
SKY = "#d8ecff"
PALE = "#f6fbff"
GREEN = "#25a68b"
ORANGE = "#f5963f"
PURPLE = "#5b5bd6"
GREY = "#6b7c93"
LINE = "#b8cbe3"
TEXT = "#12324d"
MUTED = "#536b84"
WHITE = "#ffffff"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE = font(48, True)
F_SUB = font(25)
F_H = font(27, True)
F_BODY = font(22)
F_SMALL = font(18)


def canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), PALE)
    draw = ImageDraw.Draw(img)
    draw.ellipse((W - 460, -180, W + 220, 500), fill="#e3f2ff")
    draw.ellipse((-260, H - 420, 420, H + 160), fill="#e9f4ff")
    draw.text((80, 58), title, fill=NAVY, font=F_TITLE)
    draw.text((83, 120), subtitle, fill=MUTED, font=F_SUB)
    draw.rounded_rectangle((80, 168, 250, 182), radius=7, fill=BLUE)
    draw.text((80, H - 58), "Life Science Watch | LISCIHUB technical architecture", fill=MUTED, font=F_SMALL)
    return img, draw


def wrapped_text(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], fill: str, fnt: ImageFont.FreeTypeFont, line_gap: int = 6) -> None:
    x1, y1, x2, _ = box
    max_width = x2 - x1
    words_per_line = max(12, max_width // 15)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        for line in wrap(paragraph, width=words_per_line):
            while draw.textlength(line, font=fnt) > max_width and len(line) > 10:
                words_per_line = max(8, words_per_line - 3)
                line = wrap(paragraph, width=words_per_line)[0]
                break
            lines.append(line)
    y = y1
    for line in lines:
        draw.text((x1, y), line, fill=fill, font=fnt)
        y += fnt.size + line_gap


def box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str, body: str, accent: str = BLUE) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=24, fill=WHITE, outline=LINE, width=2)
    draw.rounded_rectangle((x1, y1, x2, y1 + 12), radius=6, fill=accent)
    draw.text((x1 + 26, y1 + 28), title, fill=NAVY, font=F_H)
    wrapped_text(draw, body, (x1 + 26, y1 + 72, x2 - 26, y2 - 22), MUTED, F_BODY)


def lane(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=28, fill="#eef7ff", outline="#c9dff5", width=2)
    draw.text((x1 + 24, y1 + 18), title, fill=MID, font=F_H)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = BLUE, width: int = 5) -> None:
    draw.line((start, end), fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    if abs(x2 - x1) >= abs(y2 - y1):
        direction = 1 if x2 >= x1 else -1
        pts = [(x2, y2), (x2 - direction * 22, y2 - 12), (x2 - direction * 22, y2 + 12)]
    else:
        direction = 1 if y2 >= y1 else -1
        pts = [(x2, y2), (x2 - 12, y2 - direction * 22), (x2 + 12, y2 - direction * 22)]
    draw.polygon(pts, fill=color)


def save(img: Image.Image, stem: str) -> None:
    png = OUT_DIR / f"{stem}.png"
    jpg = OUT_DIR / f"{stem}.jpg"
    img.save(png)
    img.save(jpg, quality=92, optimize=True)
    print(png)
    print(jpg)


def render_end_to_end() -> None:
    img, draw = canvas("LISCIHUB End-To-End Technical Architecture", "Runtime components, data layers, AI enrichment, and public delivery")
    lane(draw, (70, 230, 440, 1210), "Admin station")
    lane(draw, (500, 230, 1230, 1210), "Lenovo Ubuntu Server")
    lane(draw, (1290, 230, 1630, 1210), "Data + AI")
    lane(draw, (1690, 230, 2130, 1210), "Delivery")

    box(draw, (110, 320, 400, 490), "Mac", "VS Code over SSH\nBrowser access\nDBeaver SSH tunnel", MID)
    box(draw, (110, 600, 400, 770), "Admin actions", "Remote development\nManual runs\nDatabase inspection", MID)

    box(draw, (545, 300, 825, 470), "Host cron", "Runs daily at 08:00 UTC\nCalls run_daily_pipeline.sh\nUses flock lock", BLUE)
    box(draw, (890, 300, 1185, 470), "FastAPI app", "lifescience_watch container\nDashboard, chat, API\nLocal bind only", NAVY)
    box(draw, (545, 560, 825, 760), "Python code", "Scraper\nSummaries\nExcel export\nGoogle Drive sync", GREEN)
    box(draw, (890, 560, 1185, 760), "Postgres", "liscihub-postgres\nPostgreSQL 16\nDedicated DB", GREEN)
    box(draw, (545, 850, 1185, 1050), "Local outputs", "outputs/*.log, latest_results.csv\nexports/lifescience_watch_news_latest.xlsx\nTimestamped workbook archives", ORANGE)

    box(draw, (1330, 310, 1590, 500), "DB schemas", "tech config + monitoring\nstg_ls_* company staging\ndwh reporting views", GREEN)
    box(draw, (1330, 610, 1590, 800), "OpenAI", "Summary\nTopic\nBusiness impact\nGeography\nSignal type", PURPLE)

    box(draw, (1730, 300, 2090, 475), "Caddy + Hostinger", "Hostinger DNS\nCaddy HTTPS reverse proxy\nlife-science-news.com", NAVY)
    box(draw, (1730, 590, 2090, 765), "Dashboard", "Viewer login\nFilters\nNews cards\nSource-backed chat", BLUE)
    box(draw, (1730, 880, 2090, 1055), "Google Drive", "Latest Excel workbook\nShared with business users\nUpdated daily", ORANGE)

    arrow(draw, (400, 405), (545, 385))
    arrow(draw, (825, 385), (890, 385))
    arrow(draw, (825, 660), (890, 660))
    arrow(draw, (1185, 660), (1330, 405))
    arrow(draw, (1185, 660), (1330, 705), GREEN)
    arrow(draw, (1590, 405), (1730, 675), BLUE)
    arrow(draw, (1590, 705), (1730, 675), PURPLE)
    arrow(draw, (1185, 950), (1730, 967), ORANGE)
    arrow(draw, (1730, 390), (1185, 385), NAVY)
    save(img, "01_end_to_end_architecture")


def render_pipeline() -> None:
    img, draw = canvas("Daily Pipeline Process", "Scheduled scrape, AI enrichment, workbook export, and Google Drive sync")
    steps = [
        ("Host cron", "Starts at 08:00 UTC\nLenovo host crontab"),
        ("Runner", "run_daily_pipeline.sh\nacquires lock"),
        ("Scrape", "Reads tech config\nfetches listings/articles"),
        ("Stage", "Merges records into\nstg_ls_* tables"),
        ("Summarize", "OpenAI summaries and\nstructured fields"),
        ("DWH", "Views and priority scoring\nlast 7 days/month/all"),
        ("Export", "Builds styled Excel\nlatest + archive"),
        ("Sync", "rclone upload to\nGoogle Drive"),
    ]
    x, y, bw, bh, gap = 90, 360, 230, 210, 35
    for i, (title, body) in enumerate(steps):
        left = x + i * (bw + gap)
        box(draw, (left, y, left + bw, y + bh), title, body, [BLUE, MID, GREEN, GREEN, PURPLE, NAVY, ORANGE, ORANGE][i])
        if i < len(steps) - 1:
            arrow(draw, (left + bw, y + bh // 2), (left + bw + gap, y + bh // 2), SKY, 4)
    box(draw, (170, 720, 650, 935), "Inputs", "tech.ls_load_sources\ntech.ls_load_config\ntech.ls_scraping_config\nCorporate news URLs", MID)
    box(draw, (860, 720, 1340, 935), "Database writes", "tech.ls_load_monitoring\nstg_ls_* article rows\ntech.ls_article_summary", GREEN)
    box(draw, (1550, 720, 2030, 935), "Outputs", "Dashboard views\nExcel workbook\nGoogle Drive shared file", ORANGE)
    save(img, "02_daily_pipeline_flow")


def render_database() -> None:
    img, draw = canvas("PostgreSQL Logical Architecture", "Configuration, staging, summaries, and DWH reporting layers")
    lane(draw, (100, 260, 670, 1130), "tech schema")
    lane(draw, (820, 260, 1380, 1130), "stg_ls_* schemas")
    lane(draw, (1530, 260, 2100, 1130), "dwh schema")

    tech_boxes = [
        ("ls_load_sources", "Company source URLs"),
        ("ls_load_config", "FULL/DELTA mode and active flag"),
        ("ls_scraping_config", "Scrape runtime parameters"),
        ("ls_article_summary", "AI summaries + structured fields"),
        ("ls_load_monitoring", "Run metrics and timestamps"),
        ("ls_title_exclusion", "Excluded article IDs"),
    ]
    for i, (title, body) in enumerate(tech_boxes):
        col = i % 2
        row = i // 2
        box(draw, (130 + col * 265, 350 + row * 220, 370 + col * 265, 510 + row * 220), title, body, MID)

    box(draw, (880, 390, 1320, 560), "Company staging tables", "stg_ls_sanofi\nstg_ls_servier\nstg_ls_viatris\nstg_ls_*", GREEN)
    box(draw, (880, 680, 1320, 850), "Article records", "id, url, title, article_content,\npublished_date, s_created_ts", GREEN)

    dwh_boxes = [
        ("v_news_all", "Union of all staging tables + summaries"),
        ("v_news_week", "Rolling last 7 days"),
        ("v_news_month", "Last month"),
        ("v_top_news_*", "Priority-filtered news"),
        ("*_export views", "Dashboard and workbook columns"),
    ]
    for i, (title, body) in enumerate(dwh_boxes):
        box(draw, (1570, 340 + i * 145, 2045, 455 + i * 145), title, body, NAVY if i == 0 else BLUE)

    arrow(draw, (670, 560), (820, 475), GREEN)
    arrow(draw, (670, 735), (820, 765), GREEN)
    arrow(draw, (1380, 475), (1530, 397), GREEN)
    arrow(draw, (1380, 765), (1530, 397), GREEN)
    save(img, "03_database_layers")


def render_security() -> None:
    img, draw = canvas("Web, Network, And Security Path", "Public HTTPS access with isolated app runtime and protected operations")
    box(draw, (100, 330, 420, 520), "Business user", "Browser access to\nlife-science-news.com", MID)
    box(draw, (100, 730, 420, 920), "Admin", "Mac SSH\nX-Api-Key token\nDBeaver tunnel", NAVY)
    box(draw, (600, 330, 930, 520), "Hostinger DNS", "Domain points to Lenovo\nlife-science-news.com", ORANGE)
    box(draw, (1080, 330, 1430, 520), "Caddy", "HTTPS termination\nHSTS\nReverse proxy", NAVY)
    box(draw, (1580, 330, 2020, 520), "FastAPI app", "Dashboard + chat + API\nViewer login\nAdmin endpoints", BLUE)
    box(draw, (1580, 730, 2020, 920), "PostgreSQL", "liscihub-postgres\nlocalhost-bound DB port\nDedicated project DB", GREEN)

    box(draw, (600, 700, 930, 980), "Security controls", "Trusted hosts\nRate limits\nCSP and security headers\nDocs disabled in production", PURPLE)
    box(draw, (1080, 700, 1430, 980), "Container hardening", "no-new-privileges\nDropped capabilities\ntmpfs /tmp\nDedicated compose stack", GREEN)

    arrow(draw, (420, 425), (600, 425))
    arrow(draw, (930, 425), (1080, 425))
    arrow(draw, (1430, 425), (1580, 425))
    arrow(draw, (1800, 520), (1800, 730), GREEN)
    arrow(draw, (420, 825), (1580, 455), NAVY)
    save(img, "04_web_security_path")


def main() -> None:
    render_end_to_end()
    render_pipeline()
    render_database()
    render_security()


if __name__ == "__main__":
    main()
