# 11 — Deployment and Infrastructure

## Docker runtime
- `Dockerfile` installs prod requirements and runs:
  1) migrations
  2) collectstatic
  3) gunicorn on `0.0.0.0:8000`

## Compose topology
- `web`: Django/gunicorn container.
- `caddy`: reverse proxy + TLS + static serving from mounted volume.
- shared `static_volume` for collected static files.

## Proxy routing
`Caddyfile` routes `/static/*` from filesystem and proxies everything else to `web:8000`.

## Production checklist
- Set required env vars (`SECRET_KEY`, `DATABASE_URL`, AWS keys/bucket, hosts/origins).
- Ensure SMTP works for invite/reset/notifications.
- Verify S3 write permissions for uploads.
- Run migrations before traffic cutover.
