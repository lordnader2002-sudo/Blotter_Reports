# Supabase setup — gating the Blotter dashboard

By default the dashboard runs in **local-dev / public mode**: no login, and it reads a
public `dashboard_data.json` published to GitHub Pages. To gate it behind a shared password
(so the crime data isn't public), wire it to a **new, dedicated Supabase project** — separate
from the Protest-Tracker project.

Once configured, the dashboard downloads the data from a **private Storage bucket** using the
authenticated session, and the GitHub Action uploads the data there instead of publishing it
publicly. The switch is automatic and driven entirely by the repo secrets below.

## 1. Create the project

1. Create a new project at <https://supabase.com> (e.g. `blotter-reports`).
2. **Settings → API** — copy the **Project URL** and the **anon public** key.

## 2. Create the private bucket

In **SQL Editor**, run:

```sql
insert into storage.buckets (id, name, public)
values ('blotter', 'blotter', false)
on conflict (id) do nothing;

-- Only logged-in users may read the data object.
create policy "authenticated read blotter"
  on storage.objects for select
  to authenticated
  using (bucket_id = 'blotter');
```

## 3. Create the single shared login

**Authentication → Users → Add user**: one email + a strong password. Everyone shares it;
the password is the real gate. Disable public sign-ups (**Authentication → Providers → Email**:
turn off "Enable sign-ups").

## 4. Point the dashboard at the project

Edit the config block at the top of `dashboard.html`:

```js
const SUPABASE_URL      = "https://YOUR-PROJECT.supabase.co";  // Project URL
const SUPABASE_ANON_KEY = "YOUR-ANON-KEY";                      // anon public key (safe to expose)
const SHARED_EMAIL      = "you@example.com";                    // the shared login email
const DATA_BUCKET       = "blotter";
const DATA_OBJECT       = "blotter_data.json";
```

The anon key and URL are safe to commit — access is controlled by Auth + RLS. The **service
key is a secret and must never go in `dashboard.html`**.

## 5. Add the Action secrets

In **GitHub → repo Settings → Secrets and variables → Actions**, add:

| Secret | Value |
| --- | --- |
| `SUPABASE_URL` | the Project URL |
| `SUPABASE_SERVICE_KEY` | **Settings → API → service_role** key (bypasses RLS to upload) |

With these set, the daily Action uploads `reports/latest/dashboard_data.json` to
`blotter/blotter_data.json` and **stops** publishing the data publicly to GitHub Pages —
the page then loads it from the private bucket after login. Until they're set, everything
keeps working in public-fallback mode.

## 6. Enable GitHub Pages

**Settings → Pages → Build and deployment → Source: Deploy from a branch → `gh-pages` / root.**
The Action force-pushes the dashboard to that branch on every run.
