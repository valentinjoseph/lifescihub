-- PostgreSQL DDL for tech.tech_load_sources
CREATE TABLE tech.tech_load_sources (
    company_name VARCHAR(100) PRIMARY KEY,
    industry_sector VARCHAR(50) NOT NULL DEFAULT 'LIFESCIENCE',
    source_1 TEXT,
    source_2 TEXT,
    source_3 TEXT,
    source_4 TEXT,
    source_5 TEXT,
    comment TEXT,
    s_created_ts TIMESTAMPTZ DEFAULT now() NOT NULL,
    s_modified_ts TIMESTAMPTZ DEFAULT now() NOT NULL
);


-- PostgreSQL DML for tech_load_sources table
INSERT INTO tech.tech_load_sources (company_name, industry_sector, source_1, source_2, source_3, source_4, source_5, comment) VALUES
('ALLIANCE HEALTHCARE', 'LIFESCIENCE', 'https://www.alliance-healthcare.com/newsroom', NULL, NULL, NULL, NULL, 'latest news: august 2023'),
('ASTERA', 'LIFESCIENCE', 'https://www.asteralabs.com/newsroom/', NULL, NULL, NULL, NULL, NULL),
('BIOCODEX', 'LIFESCIENCE', 'https://www.biocodex.com/en/press/', NULL, NULL, NULL, NULL, NULL),
('CEVA SANTE', 'LIFESCIENCE', 'https://www.ceva.com/news/', 'https://www.ceva.com/press-releases/', NULL, NULL, NULL, NULL),
('DELPHARM', 'LIFESCIENCE', 'https://www.delpharm.com/en/the-group/news/', NULL, NULL, NULL, NULL, NULL),
('EUROFINS', 'LIFESCIENCE', 'https://www.eurofins.com/media-centre/press-releases', NULL, NULL, NULL, NULL, NULL),
('FAREVA', 'LIFESCIENCE', 'https://www.fareva.com/en/news', NULL, NULL, NULL, NULL, NULL),
('GALDERMA', 'LIFESCIENCE', 'https://www.galderma.com/newsroom', NULL, NULL, NULL, NULL, NULL),
('HAELON', 'LIFESCIENCE', 'https://www.haleon.com/news/press-releases', NULL, NULL, NULL, NULL, NULL),
('IPSEN', 'LIFESCIENCE', 'https://www.ipsen.com/press-releases/', NULL, NULL, NULL, NULL, NULL),
('LILLY', 'LIFESCIENCE', 'https://www.lilly.com/news/press-releases', NULL, NULL, NULL, NULL, NULL),
('OPELLA', 'LIFESCIENCE', 'https://www.opella.com/en/making-headlines/breaking-news', NULL, NULL, NULL, NULL, NULL),
('OXIPHARM', 'LIFESCIENCE', 'https://www.oxypharm.net/en/news/', 'https://www.oxypharm.net/en/nos-actualites/press-releases/', NULL, NULL, NULL, NULL),
('PIERRE FABRE', 'LIFESCIENCE', 'https://www.pierre-fabre.com/en-us/newsroom', NULL, NULL, NULL, NULL, NULL),
('SANOFI', 'LIFESCIENCE', 'https://www.sanofi.com/en/media-room/press-releases', NULL, NULL, NULL, NULL, NULL),
('SEBIA', 'LIFESCIENCE', 'https://www.sebia.com/fr-fr/nos-ressources', NULL, NULL, NULL, NULL, NULL),
('SERVIER', 'LIFESCIENCE', 'https://servier.com/en/newsroom/news/', 'https://servier.mediaroom.com/news-releases', NULL, NULL, NULL, NULL),
('STAGO', 'LIFESCIENCE', 'https://www.stago.com/news/stago-group-news/', NULL, NULL, NULL, NULL, NULL),
('VIATRIS', 'LIFESCIENCE', 'https://newsroom.viatris.com/press-releases', NULL, NULL, NULL, NULL, NULL),
('VIRBAC', 'LIFESCIENCE', 'https://corporate.virbac.com/home/news-media/news.html', 'https://fr.virbac.com/home/actualites.html', NULL, NULL, NULL, NULL);
