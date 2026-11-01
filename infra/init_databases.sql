-- Dedicated local databases only. Idempotent psql script; no production data.
SELECT 'CREATE DATABASE arbit_test' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'arbit_test')
\gexec
SELECT 'CREATE DATABASE arbit_fixture' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'arbit_fixture')
\gexec
SELECT 'CREATE DATABASE arbit_member_fixture' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'arbit_member_fixture')
\gexec
