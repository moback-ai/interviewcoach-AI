Database deployment lives here.

Use this folder for database-only changes, starting with:

- `database/schema.sql`

Workflow behavior:

- change `frontend/**` -> frontend deploy
- change `backend/**` -> backend deploy
- change `database/**` -> database deploy

If you update the schema, edit `database/schema.sql` so the database-only deploy picks it up.
