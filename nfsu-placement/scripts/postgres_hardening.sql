-- Run once as the database owner after migrations (PostgreSQL only).
-- Makes the audit log append-only at the database level, even if the app is compromised.
REVOKE UPDATE, DELETE, TRUNCATE ON audit_auditlog FROM nfsu_app;
GRANT SELECT, INSERT ON audit_auditlog TO nfsu_app;
-- Note: Django migrations then need a separate owner role. In the hackathon setup, run
-- migrations as the owner and the app as nfsu_app.
