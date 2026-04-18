-- PostgreSQL DDL for tech.ls_load_sources
CREATE TABLE tech.ls_load_sources (
    company_name VARCHAR(100) PRIMARY KEY,
    source_1 TEXT,
    source_2 TEXT,
    source_3 TEXT,
    source_4 TEXT,
    source_5 TEXT,
    comment TEXT,
    s_created_ts TIMESTAMPTZ DEFAULT now() NOT NULL,
    s_modified_ts TIMESTAMPTZ DEFAULT now() NOT NULL
);


-- PostgreSQL DML for ls_load_sources table
INSERT INTO tech.ls_load_sources (company_name, source_1, source_2, source_3, source_4, source_5, comment) VALUES
('ALLIANCE HEALTHCARE', 'https://www.alliance-healthcare.com/newsroom', NULL, NULL, NULL, NULL, 'latest news: august 2023'),
('ASTERA', 'https://www.asteralabs.com/newsroom/', NULL, NULL, NULL, NULL, NULL),
('BIOCODEX', 'https://www.biocodex.com/en/press/', NULL, NULL, NULL, NULL, NULL),
('CEVA SANTE', 'https://www.ceva.com/news/', 'https://www.ceva.com/press-releases/', NULL, NULL, NULL, NULL),
('DELPHARM', 'https://www.delpharm.com/en/the-group/news/', NULL, NULL, NULL, NULL, NULL),
('EUROFINS', 'https://www.eurofins.com/media-centre/press-releases', NULL, NULL, NULL, NULL, NULL),
('FAREVA', 'https://www.fareva.com/en/news', NULL, NULL, NULL, NULL, NULL),
('GALDERMA', 'https://www.galderma.com/newsroom', NULL, NULL, NULL, NULL, NULL),
('HAELON', 'https://www.haleon.com/news/press-releases', NULL, NULL, NULL, NULL, NULL),
('IPSEN', 'https://www.ipsen.com/press-releases/', NULL, NULL, NULL, NULL, NULL),
('LILLY', 'https://www.lilly.com/news/press-releases', NULL, NULL, NULL, NULL, NULL),
('OPELLA', 'https://www.opella.com/en/making-headlines/breaking-news', NULL, NULL, NULL, NULL, NULL),
('OXIPHARM', 'https://www.oxypharm.net/en/news/', 'https://www.oxypharm.net/en/nos-actualites/press-releases/', NULL, NULL, NULL, NULL),
('PIERRE FABRE', 'https://www.pierre-fabre.com/en-us/newsroom', NULL, NULL, NULL, NULL, NULL),
('SANOFI', 'https://www.sanofi.com/en/media-room/press-releases', NULL, NULL, NULL, NULL, NULL),
('SEBIA', 'https://www.sebia.com/fr-fr/nos-ressources', NULL, NULL, NULL, NULL, NULL),
('SERVIER', 'https://servier.com/en/newsroom/news/', 'https://servier.mediaroom.com/news-releases', NULL, NULL, NULL, NULL),
('STAGO', 'https://www.stago.com/news/stago-group-news/', NULL, NULL, NULL, NULL, NULL),
('VIATRIS', 'https://newsroom.viatris.com/press-releases', NULL, NULL, NULL, NULL, NULL),
('VIRBAC', 'https://corporate.virbac.com/home/news-media/news.html', 'https://fr.virbac.com/home/actualites.html', NULL, NULL, NULL, NULL);
