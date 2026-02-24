# 14 — Troubleshooting

## Common issues

### 1) Invite emails contain bad links
- Ensure `APP_BASE_URL` is set (required by `_send_set_password_email`).

### 2) Google login returns to error
- Check OAuth client id/secret and callback URL alignment.

### 3) Production startup crash
- `production.py` intentionally fails fast when missing `SECRET_KEY`, `DATABASE_URL`, or S3 config.

### 4) Receiving cannot be edited
- Final statuses (`REVIWED` typo constant value, DENIED) and COO decisions hard-lock records.

### 5) Inventory numbers look off
- Verify signed transaction logic: RECEIVE/ADJUST_IN positive, ISSUE/ADJUST_OUT negative.

> Gotcha: `REVIWED` is a constant typo in code but is the canonical value used in workflow logic.
