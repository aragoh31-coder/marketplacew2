CREATE DATABASE marketplace;
CREATE USER marketplace WITH ENCRYPTED PASSWORD 'marketplace_password';
GRANT ALL PRIVILEGES ON DATABASE marketplace TO marketplace;

\c marketplace;

GRANT ALL ON SCHEMA public TO marketplace;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO marketplace;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO marketplace;
