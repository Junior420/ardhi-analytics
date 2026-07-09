# Setting up Supabase (free, durable Postgres)

Ardhi stores everything — users, deals, comparables, market cache — in Postgres
when `DATABASE_URL` is set, and in a local SQLite file otherwise. Supabase's
free tier gives you a managed Postgres database (500 MB, with backups) at no
cost, which makes a free/ephemeral web host durable.

## 1. Create the project

1. Go to https://supabase.com/dashboard and sign in (GitHub works).
2. **New project.** Pick a name, a strong database password (save it), and the
   region closest to your users (e.g. `West EU (Ireland)` for Tanzania).
3. Wait ~2 minutes for it to provision.

## 2. Get the connection string

1. In the project: **Project Settings → Database → Connection string**.
2. Choose the **URI** tab. You'll see something like:
   `postgresql://postgres.abcxyz:[YOUR-PASSWORD]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres`
3. Replace `[YOUR-PASSWORD]` with the database password from step 1.

Any of Supabase's connection modes work — the app disables psycopg prepared
statements, so even the transaction pooler (pgbouncer) connects cleanly. For a
long-running server (Render, Cloudflare), the **Session pooler** or direct
connection is the natural choice.

## 3. Give it to your host

Set `DATABASE_URL` to that string wherever the app runs:

- **Render** — the service's **Environment** tab → add `DATABASE_URL` (and
  `ARDHI_JWT_SECRET`). With Postgres holding the data, the app is stateless, so
  you can drop the persistent disk and use the **Free** plan.
- **Cloudflare** — `npx wrangler secret put DATABASE_URL`.
- **Local** — `export DATABASE_URL=...` or copy `backend/.env.example` to
  `backend/.env`.

## 4. First run

Tables are created automatically on first request — no migration step. Register
the first account (it becomes admin), and you're live. Browse the data anytime
under **Table Editor** in the Supabase dashboard.

## Verifying it worked

`GET /api/health` should return ok, and after registering, the `users` table in
Supabase's Table Editor will show your row. CI runs the full test suite against
PostgreSQL 16 on every push, so the Postgres path is continuously exercised.
