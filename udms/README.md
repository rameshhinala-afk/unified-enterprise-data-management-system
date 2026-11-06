# Unified Enterprise Data Management System

A small, dependency-free (Python 3.9+ standard library only) base project that brings data
from separate enterprise systems into **one governed, high-quality store**.

```
HR csv ──┐                                   ┌─► Data quality rules ─► dq_issues
CRM csv ─┼─► connectors ─► MDM match/merge ──┤
ERP csv ─┘   (canonical     (golden records) └─► Unified SQLite store
              shape)                                   │
                                   Governance: roles + masking + audit trail
                                                       │
                                               Service layer ─► CLI / REST API
```

| Capability            | File                  | What it does                                                              |
|-----------------------|-----------------------|---------------------------------------------------------------------------|
| Integration           | `udms/connectors.py`  | Maps each source's layout/field names to one canonical shape              |
| Master data mgmt      | `udms/mdm.py`         | Matches duplicates (email, then phone), merges into golden records, keeps xref |
| Data quality          | `udms/quality.py`     | Rules (invalid email, bad salary, duplicates...) stored in `dq_issues`    |
| Governance / security | `udms/governance.py`  | Entity catalog, role permissions, field masking, audit logging            |
| Service layer         | `udms/service.py`     | Single entry point: authorize → query/update → audit                      |
| API                   | `udms/api.py`         | REST API with API-key auth                                                |

## Quick start

```bash
python main.py demo                                   # build DB from sample HR/CRM/ERP files
python main.py search customers hyd --key sales-key   # query as the sales role
python main.py search employees --key analyst-key     # salary shows as ***
python main.py audit --key admin-key                  # who accessed what
python main.py serve --port 8000
python -m unittest discover -s tests -v               # run the tests
```

Demo users: `admin-key`, `hr-key`, `sales-key`, `analyst-key` (demo values only; use real
secrets and hashed keys in production).

## API

```bash
curl -H "X-API-Key: hr-key" "localhost:8000/entities/employees?q=Sales"
curl -H "X-API-Key: sales-key" localhost:8000/entities/customers/1
curl -X PUT -H "X-API-Key: sales-key" -d '{"city":"Pune"}' localhost:8000/entities/customers/1
curl -H "X-API-Key: admin-key" localhost:8000/quality
curl -H "X-API-Key: admin-key" localhost:8000/audit
```

## Access rules

| Role    | employees | customers | quality | audit | Masked from this role     |
|---------|-----------|-----------|---------|-------|---------------------------|
| admin   | read/write| read/write| read    | read  | –                         |
| hr      | read/write| –         | –       | –     | –                         |
| sales   | –         | read/write| –       | –     | –                         |
| analyst | read      | read      | read    | –     | salary, customer phone    |

## Extending it

- Add a new source: write a connector returning the canonical dict, pass it to `sync_customers`.
- Add a new entity: register it in `governance.ENTITIES` and `PERMISSIONS`, and add a table.
- Production steps: Postgres, hashed API keys / SSO, fuzzy name matching in MDM, scheduled syncs.
