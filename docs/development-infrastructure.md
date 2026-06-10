# Development Infrastructure (sanitized)

Source reference: `I:\2026AILab\树洞\开发基础设施清单.md`.

This file intentionally omits tokens, passwords, access keys, webhook secrets,
and server credentials. Real values belong in local `.env`, server environment
variables, or the deployment secret store.

## GitHub

- Default organization: `SilentGenesisLab`
- Repository: `videoGEO2`
- Branch strategy: `feature/* -> uat -> main`
- Proxy placeholder: `http://127.0.0.1:7888`
- Token variable: `GITHUB_TOKEN`

## Branch Policy

- `main`: production/stable branch
- `uat`: integration branch
- `feature/<task-id>`: working branches
- Push meaningful commits after substantial framework changes.

## Port Pools

- PostgreSQL: `54321` to `54399`
- Redis: `63791` to `63800`

## OSS

- Endpoint: `oss-cn-shenzhen.aliyuncs.com`
- Custom domain: `oss3.sligenai.cn`
- Required variables:
  - `OSS_BUCKET`
  - `OSS_ENDPOINT`
  - `OSS_ACCESS_KEY_ID`
  - `OSS_ACCESS_KEY_SECRET`
  - `OSS_CUSTOM_DOMAIN`

## Notifications

- Feishu webhook variable: `FEISHU_WEBHOOK_URL`
- Aliyun SMS variables:
  - `ALIYUN_SMS_ACCESS_KEY_ID`
  - `ALIYUN_SMS_ACCESS_KEY_SECRET`
  - `ALIYUN_SMS_SIGN_NAME`
  - `ALIYUN_SMS_TEMPLATE_CODE`
  - `ALIYUN_SMS_REGION_ID`

## Security Rules

- Do not commit `.env` or raw infrastructure inventories containing secrets.
- Do not paste tokens in logs, issues, commits, or documentation.
- Rotate any token that has been exposed in chat or local transcripts.
- Keep the committed version limited to names, placeholders, branch policy, and
  non-secret endpoints.
