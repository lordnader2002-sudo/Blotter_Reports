# Supabase setup — gating the Blotter dashboard

By default the dashboard runs in **public mode**: no login, and it reads a public
`dashboard_data.json` published to GitHub Pages. To gate it behind the shared password,
this project **reuses the existing Protest-Tracker Supabase project** (the free plan's
2-project limit is already reached) with a second, separate private bucket.

Once configured, the dashboard downloads its data from the private `blotter` bucket using
the authenticated session, and the GitHub Action uploads the data there instead of
publishing it publicly. The flip is automatic, driven by the repo secrets below.

> **Access note:** with the shared-login setup, anyone holding the Protest-Tracker shared
> password can also read the blotter bucket (both grant to `authenticated`). If you ever
> want separate passwords, create a second user and scope the policy with
> `auth.jwt()->>'email'`.

## 1. Create the private bucket (one SQL snippet)

In the **Protest-Tracker project's** SQL Editor, run:

```sql
insert into storage.buckets (id, name, public)
values ('blotter', 'blotter', false)
on conflict (id) do nothing;

-- Only logged-in users may read the blotter data object.
create policy "authenticated read blotter"
  on storage.objects for select
  to authenticated
  using (bucket_id = 'blotter');
```

That's the only console step — the project, auth setup, and shared login
(`lordnader2002@gmail.com`) already exist from Protest-Tracker.

## 2. Add the Action secrets to THIS repo

In **GitHub → Blotter_Reports → Settings → Secrets and variables → Actions**, add the
**same two values already used in the Protest-Tracker repo**:

| Secret | Value |
| --- | --- |
| `SUPABASE_URL` | `https://dkeaeprelbhdabnvcsqc.supabase.co` |
| `SUPABASE_SERVICE_KEY` | the PT project's `service_role` key (Settings → API) |

With these set, the daily Action uploads `reports/latest/dashboard_data.json` to
`blotter/blotter_data.json` and **stops** publishing the data publicly to GitHub Pages.
Until they're set, everything keeps working in public-fallback mode.

## 3. Activate the login gate in the dashboard

Fill the config block at the top of `dashboard.html` with the PT project's values
(these are safe to commit — the anon key is public by design; the password is the gate):

```js
const SUPABASE_URL      = "https://dkeaeprelbhdabnvcsqc.supabase.co";
const SUPABASE_ANON_KEY = "<the PT anon public key>";
const SHARED_EMAIL      = "lordnader2002@gmail.com";
const DATA_BUCKET       = "blotter";
const DATA_OBJECT       = "blotter_data.json";
```

⚠️ Do steps 1 and 2 **before** this one — once these values are real, the page requires
login and reads only from the bucket, so an empty bucket means a broken dashboard.
The **service key must never go in `dashboard.html`** — secrets only.

## 4. Enable GitHub Pages

**Settings → Pages → Build and deployment → Source: Deploy from a branch → `gh-pages` / root.**
The Action force-pushes the dashboard to that branch on every run.
