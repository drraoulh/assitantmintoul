-- Extensions used by later phases. Safe to run on a fresh PostgreSQL 16 volume.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS postgis;
