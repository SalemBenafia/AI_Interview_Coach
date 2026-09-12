-- scripts/init_db.sql
-- Runs automatically via postgres's docker-entrypoint-initdb.d on first boot.
-- Application-level schema is owned by Alembic (backend/alembic/) — this
-- file only sets up extensions/Settings that must exist before migrations run.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

SET timezone = 'UTC';
