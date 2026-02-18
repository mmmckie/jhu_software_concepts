-- Run as a privileged role (e.g., postgres) once per environment.
-- Replace password before use.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grad_app') THEN
        CREATE ROLE grad_app LOGIN PASSWORD 'change_me';
    ELSE
        ALTER ROLE grad_app WITH LOGIN PASSWORD 'change_me';
    END IF;
END $$;

-- Ensure app role is not elevated.
ALTER ROLE grad_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;

-- Database-level access only.
GRANT CONNECT ON DATABASE grad_data TO grad_app;

\c grad_data

-- Schema permissions: read + write data only, no ownership-level controls.
GRANT USAGE ON SCHEMA public TO grad_app;
GRANT SELECT, INSERT, UPDATE ON TABLE public.admissions TO grad_app;
GRANT USAGE, SELECT ON SEQUENCE public.admissions_p_id_seq TO grad_app;

-- No DROP/ALTER grants are provided.
