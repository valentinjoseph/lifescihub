-- PostgreSQL DDL for tech.tech_title_exclusion table
CREATE TABLE tech.tech_title_exclusion (
    company_name VARCHAR(50),
    id VARCHAR(36),
    title TEXT
);

-- Add table comment
COMMENT ON TABLE tech.tech_title_exclusion IS 'Exclusion list for articles that should be filtered out from the data warehouse views. Contains article IDs and titles to exclude.';

-- Add column comments
COMMENT ON COLUMN tech.tech_title_exclusion.company_name IS 'Company name associated with the excluded article';
COMMENT ON COLUMN tech.tech_title_exclusion.id IS 'Article ID to exclude (typically UUID)';
COMMENT ON COLUMN tech.tech_title_exclusion.title IS 'Article title to exclude';

-- Create index for efficient lookups
CREATE INDEX idx_tech_title_exclusion_id ON tech.tech_title_exclusion(id);
CREATE INDEX idx_tech_title_exclusion_company ON tech.tech_title_exclusion(company_name);


-- PostgreSQL DML for tech_title_exclusion table (85 rows)
INSERT INTO tech.tech_title_exclusion (company_name, id, title) VALUES
('CEVA SANTÉ', '334496dc-74a0-4419-a438-a67ac7b16b70', 'Ceva Santé Animale | Discover our press releases'),
('CEVA SANTÉ', '6f695334-8eb3-4f1a-b050-5ba957773824', 'Ceva Santé Animale | Discover our latest news'),
('CEVA SANTÉ', 'a304c073-ea20-49cf-b2d7-d55b6a366c55', 'Ceva Santé Animale - Communiqués de presse'),
('CEVA SANTÉ', 'd304d319-9bfc-4164-8f5c-8bfd6711ca8e', 'Ceva Santé Animale | Mediaroom'),
('DELPHARM', '0019f698-b9f0-4790-9c63-bac730bbe5a7', 'Legal information - Delpharm'),
('DELPHARM', '451951ba-0691-4993-81f2-6b1610b9a643', 'General terms and conditions of purchase - Delpharm'),
('DELPHARM', '8a5d3938-75e8-4cb6-b251-c95d57f01286', 'Code of conduct Delpharm - Delpharm'),
('DELPHARM', 'a048458c-a275-4c97-85d4-1ecdb8946fe4', 'General terms and conditions of purchase (Delpharm POZNAŃ) - Delpharm'),
('DELPHARM', 'ceed608c-d57b-4716-a58b-8ccf362d2e84', 'Newsletter - Delpharm'),
('DELPHARM', 'df985c24-21f2-48f5-bb66-1e3eab800df7', 'Delpharm CDMO news'),
('EUROFINS', '01492a78-b5e0-4789-b63a-4b87239bfc6e', 'Eurofins Consumer Product Testing | News'),
('EUROFINS', '14ba1a60-0b2b-4464-9f28-9342a7e7c30f', E'Press Releases 2019\r\n- Eurofins Scientific'),
('EUROFINS', '1be44723-012a-4d0c-9081-4a90583a8842', 'Eurofins REACH Services'),
('EUROFINS', '2bc815ec-2ccf-4345-913a-1f54f9fff85c', E'Genomic Services\r\n- Eurofins Scientific'),
('EUROFINS', '31645b7e-86da-48df-8973-eb574658fda6', E'Press Releases 2020\r\n- Eurofins Scientific'),
('EUROFINS', '356cb5c9-6223-4870-bfd3-20d8332e2ed4', E'Press Releases 2025\r\n- Eurofins Scientific'),
('EUROFINS', '4250ffb5-ce83-449e-9058-17acf91e682a', E'Press Releases 2018\r\n- Eurofins Scientific'),
('EUROFINS', '5f0bda75-c0a9-401f-9eee-6190560f0b5d', E'Environment Testing News\r\n- Eurofins Scientific'),
('EUROFINS', '5f936a9e-8c0e-4b36-8d50-520f11a27fe5', E'Downloads\r\n- Eurofins Scientific'),
('EUROFINS', '67c1debc-ca15-43fe-b9db-25a508df4cb6', E'Media Centre\r\n- Eurofins Scientific'),
('EUROFINS', '728fc92c-a69d-4c1f-bc2f-34151c9e0efe', E'Press Releases 2024\r\n- Eurofins Scientific'),
('EUROFINS', '743202c1-00bd-4fb5-9265-2e89b73b53f6', E'Eurofins Scientific Press Release Archive\r\n- Eurofins Scientific'),
('EUROFINS', '756e6599-e86b-41ea-8bde-f3556f5babea', E'Press Releases 2023\r\n- Eurofins Scientific'),
('EUROFINS', '88d87e1f-a64d-4a38-9e59-e864133fc442', E'Press Releases 2021\r\n- Eurofins Scientific'),
('EUROFINS', 'a4a9ad47-0476-4538-aac0-1b7751435a0b', E'Eurofins Press Releases\r\n- Eurofins Scientific'),
('EUROFINS', 'c8220161-fb27-4ff5-befd-386cd37cac56', E'Eurofins Genotyping & Gene Expression\r\n- Eurofins Scientific'),
('EUROFINS', 'e3748cfe-58b5-4c6f-9b8d-a5e127a60f5c', E'Press Releases 2022\r\n- Eurofins Scientific'),
('EUROFINS', 'e4a97adf-6ea0-4fd5-8582-9eeced6e5876', E'Tackling the Big Problem of Tiny Particles\r\n- Eurofins Scientific'),
('EUROFINS', 'e50c499f-9795-4f07-9cb0-28f5b49dfe33', E'Eurofins Newsletters\r\n- Eurofins Scientific'),
('EUROFINS', 'f6de24e3-dfac-4584-89ed-964dafdaa841', E'Eurofins Press Releases 2014\r\n- Eurofins Scientific'),
('EUROFINS', 'fb308117-79aa-4af5-b309-485c9f603858', E'Press Releases\r\n- Eurofins Scientific'),
('FAREVA', '6e4feeac-6bfa-4ab3-8649-da51e5ea170c', 'News - Fareva'),
('FAREVA', '7eae571b-d202-454a-8c47-30085e439501', 'SKIN STORIES | Galderma'),
('FAREVA', '8a42a4e0-d73e-4156-9664-c59a36ed8961', 'Galderma | Newsroom'),
('FAREVA', 'b9040302-f42d-4cb8-b9a1-c158248b41d9', 'GALDERMA SKIN STORIES | Galderma'),
('FAREVA', 'cd147155-501c-443d-a0b1-6433b2bea4f4', 'NEWSROOM | Galderma'),
('IPSEN', '12caca8c-6004-4249-b9b6-92eaa834f875', 'Communiqués de presse Ipsen | Dernières actualités et mises à jour'),
('IPSEN', '2f523885-9d9f-4cb8-931f-73377216bc0f', 'Media Contacts - Global'),
('IPSEN', '31b337b5-074e-4606-99f9-e8c0e7d269a6', 'News Registration - Global'),
('IPSEN', '37d68f82-a881-47d3-9e14-e6e129070f13', 'Ipsen Media Updates | Official Announcements & Updates'),
('IPSEN', '6600e50a-4afb-4aa6-a5c6-ac435f6c0f56', 'Ipsen news | Ipsen Global'),
('IPSEN', '8d15dbdf-1b7c-429f-b875-bcd41a406feb', 'Corporate News for Investors | Ipsen''s Latest Financial Updates'),
('IPSEN', 'c8bb14f4-0cbe-487d-b6a9-46ade0f87d73', 'Ipsen Media Library | Ipsen Global'),
('OPELLA', '3c34cde4-aa06-4d34-afe2-3b586d2181b5', 'Press kits | Opella'),
('OXIPHARM', '023c17a0-7c1b-48dd-aeec-bcb6f4c3155d', 'Archives des evento in primo piano - Oxy''Pharm'),
('OXIPHARM', '039e89b8-fb0c-40d1-b1dd-9e8873500776', 'Archives des event - Oxy''Pharm'),
('OXIPHARM', '05471bc7-e6b6-4729-9a18-676e7cafa125', 'Archives des Events - Oxy''Pharm'),
('OXIPHARM', '0e628aad-9c40-49e5-ada9-ac304a4ca0b6', 'Archives des nocomax - Oxy''Pharm'),
('OXIPHARM', '10af7602-60ee-4f8e-ac39-042420020adc', 'Archives des Uncategorized - Oxy''Pharm'),
('OXIPHARM', '10ef641f-5274-4d3c-a557-3d9dac6a92b2', 'Archives des front page - Oxy''Pharm'),
('OXIPHARM', '13a10ad7-6392-410f-bd68-d4106b6e105a', 'Archives des à la une - Oxy''Pharm'),
('OXIPHARM', '2d609440-1c67-429d-9abf-ba556fc8bec1', 'Archives des health - Oxy''Pharm'),
('OXIPHARM', '31d4605a-31ff-495a-a69d-a406fb699d93', 'Archives des Oxy''Pharm - Oxy''Pharm'),
('OXIPHARM', '40a5d6ae-efbc-4181-a01c-97764a4ac291', 'Archives des Normes DSVA - Oxy''Pharm'),
('OXIPHARM', '482888d1-a785-4855-9c52-c4e3466f5cea', 'Archives des Communiqués de presse - Oxy''Pharm'),
('OXIPHARM', '54a8c202-4c47-48f6-b818-65ffb625b0e0', 'Archives des NF T 72-110 désinfection vapeur - Oxy''Pharm'),
('OXIPHARM', '555117ee-e345-450f-90a5-df2407a7c0e3', 'Archives des Articles - Oxy''Pharm'),
('OXIPHARM', '56cb295a-a5a8-4f55-ae86-8371e4da555a', 'Archives des front page sub event - Oxy''Pharm'),
('OXIPHARM', '7a3e9658-7f86-4f19-96fe-57e194c3e358', 'Archives des sanivap - Oxy''Pharm'),
('OXIPHARM', '8bff3633-1031-456a-bdbb-76232f0ef241', 'Archives des Take the floor! - Oxy''Pharm'),
('OXIPHARM', '8d08a3e5-9f8e-4c74-b2e1-ec9a01420068', 'Archives des Désinfection - Oxy''Pharm'),
('OXIPHARM', '8d1ca132-f332-4ac3-ac8e-fc83180e6be8', 'Archives des environmentally friendly - Oxy''Pharm'),
('OXIPHARM', '9002f274-37e5-46d6-9567-ab3c47c0210d', 'Archives des hospital - Oxy''Pharm'),
('OXIPHARM', '9b678910-0cc2-4e5e-adac-01bea2978b26', 'Archives des Métiers - Oxy''Pharm'),
('OXIPHARM', 'be3fc487-74d0-43c2-ad59-ef0564e7fa47', 'Archives des Oxy''Pharm front page - Oxy''Pharm'),
('OXIPHARM', 'd3fda110-1671-40c7-abbe-d923cf635864', 'Archives des Santé - Oxy''Pharm'),
('OXIPHARM', 'e2b63ac6-475d-49f6-bd5e-074667ed36ce', 'Archives des front page event - Oxy''Pharm'),
('OXIPHARM', 'e5706cfc-9c61-49ca-9ddf-0f4b99238036', 'Archives des Press releases - Oxy''Pharm'),
('OXIPHARM', 'f4328bd1-e81e-44ff-99f8-ac2ac3e76d13', 'Archives des kit - Oxy''Pharm'),
('OXIPHARM', 'f72db869-07ea-4f18-a6b5-a10a2a5d31ae', 'Archives des nocotech - Oxy''Pharm'),
('OXIPHARM', 'fc759444-e613-4e14-b654-e3c931c77a15', 'Archives des nocospray - Oxy''Pharm'),
('OXIPHARM', 'fd331e9a-9e5d-471f-a4e1-1955762bc9c5', 'Archives des nocolyse - Oxy''Pharm'),
('OXIPHARM', 'ff7b3960-ca84-4e77-8c3e-2a7eed5b8b4f', 'News - Oxy''Pharm'),
('PIERRE FABRE', 'efa2f019-b9c4-4b98-a564-c0cc21a78958', 'Pierre Fabre Pharmaceutical Group : all the latest news'),
('SANOFI', '1c2c5dc4-51ac-4e62-9a05-3cf0eac9212a', 'Media Contacts'),
('SANOFI', '843c5e9b-d369-4196-8310-990e15e6ad92', 'Press Statements'),
('SERVIER', '0913df2c-b0ff-4633-a8f5-359e4141f2d6', 'Newsroom | Servier - News Releases'),
('SERVIER', '43d696a7-0663-4104-843b-d05e1c095f27', 'Mediator Information - Servier'),
('SERVIER', '5c38e52f-023b-4d34-979e-e3e398d6e1ee', 'Découvrez les actualités du groupe Servier'),
('SERVIER', 'a88d8e3d-c329-4b38-8d2f-ee1157c66026', '#WeAreServier | Our employees'' testimonials'),
('STAGO', '91ddb2af-2f0c-4522-96ee-c2b21d242e2b', 'Events & Congresses | Stago.com'),
('STAGO', 'd16beb00-956b-4d6d-a495-b095ac0fb133', 'Stago Group News | Stago.com'),
('STAGO', 'e57f76cf-e031-4375-ac36-d4bbd48a062f', 'Just published | Stago.com');
