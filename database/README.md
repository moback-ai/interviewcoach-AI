Database deployment lives here.

**Schema source of truth**

| Path | Purpose |
|------|---------|
| `backend/schema.sql` | Full schema for new environments |
| `database/migrations/*.sql` | Incremental migrations (apply in filename order) |
| `database/schema.sql` | Pointer only — do not apply on prod |

Workflow behavior:

- change `frontend/**` → frontend deploy
- change `backend/**` → backend deploy
- change `database/**` → database deploy

Apply migrations with your standard RDS migration process after merging to `develop`.
