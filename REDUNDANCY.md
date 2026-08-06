# Redundant Publishing (multi-platform)

The auto-blog no longer depends on a single CI provider. Four independent
"publishing legs" watch the same blog; each leg only publishes when the
blog feed goes stale, so they never fight each other:

| Leg        | Executor                  | Cadence         | Status                |
| ---------- | ------------------------- | --------------- | --------------------- |
| Primary    | GitHub Actions            | every 15 min    | already running       |
| Secondary  | GitLab.com CI (scheduled) | every 30 min    | live                  |
| Tertiary   | CircleCI (scheduled)      | hourly          | not set up (optional) |
| Local      | Your PC (watchdog script) | every 15 min    | already running       |

Safety (all legs, code-level):
- `src/wp_failover_publish.py` publishes ONLY when the public feed is stale
  (default threshold: 30 minutes for secondary legs), with its own lock and
  cooldown.
- `site_posts_today()` enforces the daily cap against the SITE API, not a
  local database, so parallel platforms cannot overshoot
  `MAX_POSTS_PER_DAY` (env `GLOBAL_DAILY_CAP=true`).
- Duplicate-title and duplicate-source guards query the live site before
  every publish, so two legs can never post the same story twice.
- X/Tumblr/Bluesky sharing runs ONLY on GitHub Actions (`X_SHARE_ENABLED`)
  so social posts are never duplicated.

---

## Leg 1: GitHub Actions (primary)

Already configured in `.github/workflows/`. Nothing to do.

## Leg 2: GitLab.com (secondary)

**Live project:** https://gitlab.com/eldergodchucky/chuckys-autoblog (public)

Already done (2026-08-06): project created, repo pushed, CI variables set,
30-minute schedule active (`*/30 * * * *` UTC on `main`), identity verified.
If it ever needs to be rebuilt from scratch:

1. Sign up/in at gitlab.com.
2. Create a project named `chuckys-autoblog` (public — free CI minutes for
   public projects are much more generous: 50,000/month vs 400 for private;
   this pipeline runs 48 times a day).
3. **Settings > CI/CD > Variables** — add (values from your `.env`):
   - `WP_BASE_URL`
   - `WP_USERNAME`
   - `WP_APPLICATION_PASSWORD`
   - `WP_COM_ACCESS_TOKEN` (masked)
   - `POST_BY_EMAIL_ADDRESS`
   - `MAX_POSTS_PER_DAY=90`
4. **Build > Pipeline schedules > New schedule**: cron `*/30 * * * *`,
   target branch `main`, timezone UTC. GitLab does the rest —
   `.gitlab-ci.yml` is already in the repo.
5. New accounts must complete GitLab's **identity verification** (phone or
   free card authorization) before shared runners will execute CI.

Keep the GitLab copy in sync: push the repo to both remotes
(`git push origin main && git push gitlab main`).

## Leg 3: CircleCI (tertiary)

1. Sign in at app.circleci.com with your GitHub account.
2. **Projects > Set Up Project** for `chuckys-autoblog` (skip the demo
   config; keep our `.circleci/config.yml`).
3. **Project Settings > Environment Variables** — same five variables as
   GitLab above.
4. Push any commit to `main`; the hourly schedule in `.circleci/config.yml`
   takes over from there. (Hourly cadence keeps the free 2,500 minutes/month
   comfortable while still covering multi-hour outages.)

## Leg 4: Local watchdog (your PC)

`scripts/local_watchdog.ps1` runs the failover publisher every 15 minutes
while your PC is on — zero cost, zero accounts. Already installed on this
machine as Windows scheduled tasks:

- `ChuckyAutoblog-WatchdogKeepalive` — starts the watchdog every 30 minutes
  (it exits instantly if the watchdog is already alive, so a crashed or
  killed loop is healed within 30 minutes).
- `ChuckyAutoblog-Digest` — runs the weekly digest every Monday 06:00 local
  (05:00 UTC, matching the GitHub schedule) in case GitHub misses it.
- Log: `data/local_watchdog.log`; the singleton lock lives at
  `data/local_watchdog.lock`.

Manual run: `powershell -ExecutionPolicy Bypass -File scripts\local_watchdog.ps1`

## How an outage is handled

Example: GitHub Actions has a "major outage" (like 2026-08-06).
- 0–30 min: posts still flow; the feed stays fresh, secondaries skip.
- 30+ min: GitLab (every 30 min) and CircleCI (hourly) see the stale feed
  and publish one post each run; the local watchdog does the same every 15
  minutes. The site-wide daily cap keeps totals sane.
- GitHub recovers: secondaries see a fresh feed again and step back.

## Verifying health

- Blog feed: https://chuckyscarnage.tech.blog/feed/ (latest item's pubDate)
- Each leg writes its own `data/failover_status.json` (state: fresh /
  published / skipped / locked).
- GitHub: https://github.com/eldergodchucky/chuckys-autoblog/actions
- GitLab: your project's **Build > Pipelines**
- CircleCI: app.circleci.com pipeline list
