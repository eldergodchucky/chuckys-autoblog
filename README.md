# WordPress Auto Blog

This project fetches high-quality tech, science, gadget, security, tutorial, and DIY feeds, groups related items, generates an original cited post, and sends it to WordPress through Post by Email or the REST API.

The current focus rotates through science breakthroughs, space, AI, gadgets, phones, Android, Apple/iOS, software/apps, security, tutorials, and practical hacks so the blog does not get stuck in one lane.

Key safety controls:

- Live publishing requires `AUTO_PUBLISH_CONFIRM=I_UNDERSTAND_POSTS_GO_LIVE`.
- Each post needs at least two source URLs by default.
- The scheduler can check frequently, but `MAX_POSTS_PER_DAY` prevents unlimited posting.
- The generated post uses natural inline attribution instead of a visible source dump.
- Free mode creates an original hero image and places a `[more]` break after the intro so your blog listing can show the title/image/teaser before readers click through.
- The script stores seen items so it does not keep reusing the same stories.
- `ARTICLE_GENERATOR=free` uses no paid AI API. It creates original news-style articles with category-aware voice, varied headings, and less template-like phrasing.
- Category rotation picks the next content lane in order, with fallback if no good story exists for that category.
- Science and space posts can use one high-quality source when a good breakthrough story is available but no second matching source has appeared yet.

## Setup

### WordPress.com Free / No-Fee Setup

Use WordPress.com's Post by Email feature:

1. Go to your WordPress.com site dashboard.
2. Open `Settings -> Writing`.
3. Enable `Post by Email`.
4. Copy the secret `@post.wordpress.com` address.
5. Copy `.env.example` to `.env` and fill in:

```text
WP_POST_METHOD=email
POST_BY_EMAIL_ADDRESS=your-secret-address@post.wordpress.com
POST_BY_EMAIL_PUBLICIZE=
POST_STATUS=publish
AUTO_PUBLISH_CONFIRM=I_UNDERSTAND_POSTS_GO_LIVE
ARTICLE_GENERATOR=free
HERO_IMAGE_MODE=real
```

Then add a sender email account:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-sender-email@gmail.com
SMTP_PASSWORD=your-sender-email-app-password
SMTP_FROM=your-sender-email@gmail.com
```

You can use Gmail, Outlook.com, or another email provider that supports SMTP. Use a dedicated sender account if you can. Gmail app passwords require 2-Step Verification; Outlook.com uses `smtp-mail.outlook.com` on port `587` with STARTTLS.

For WordPress.com social auto-sharing, leave `POST_BY_EMAIL_PUBLICIZE` blank. That allows WordPress.com/Jetpack Social to use your configured social connections. Set `POST_BY_EMAIL_PUBLICIZE=off` only when you want to suppress social sharing for every emailed post.

### X/Twitter Sharing

The companion script `src/share_blog_to_x.py` checks your published blog feed and posts new links to X. It stores sharing memory in `data/x_shared_posts.json` so the same blog URL is not posted twice.

You do not need to give Codex your X password. The clean setup is OAuth: you approve your own app in the browser, and the local script stores the resulting token in `.env`.

For the easiest local setup, run:

```powershell
.\START_HERE_X_SETUP.ps1
```

That helper opens the X Developer Portal, shows the exact app settings, asks for the Client ID, and then launches the X approval page.

1. Open the X Developer Portal: https://developer.x.com/en/portal/dashboard
2. Create or open a Project and App.
3. In the app's User authentication settings, enable OAuth 2.0.
4. Set the app permissions to Read and Write.
5. Add this exact callback / redirect URL:

```text
http://127.0.0.1:8765/callback
```

6. Save the settings, then open the app's Keys and Tokens page.
7. Copy the OAuth 2.0 Client ID into `.env`.
8. If X shows a Client Secret for your app type, copy that into `.env` too.

Add or update this in `.env`:

```text
BLOG_FEED_URL=https://chuckyscarnage.tech.blog/feed/
X_CLIENT_ID=your_x_client_id
X_CLIENT_SECRET=your_x_client_secret_if_shown
X_REDIRECT_URI=http://127.0.0.1:8765/callback
X_OAUTH_SCOPES=tweet.read tweet.write users.read offline.access
X_SHARE_MAX_PER_RUN=2
X_SHARE_BACKFILL=false
X_SHARE_TEMPLATE=New on Chucky's Carnage: {title}\n{link}
```

Then run the local OAuth helper:

```powershell
& 'C:\Users\ELDERCHUCKY\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\src\x_oauth_setup.py
```

It opens X in your browser. Sign in to the X account that should post, approve the app, and the helper will save `X_USER_ACCESS_TOKEN`, `X_REFRESH_TOKEN`, and `X_TOKEN_EXPIRES_AT` into `.env`.

Use a user-context X API token with `tweet.write` permission. `offline.access` is included so the automation can refresh the token instead of stopping after the short-lived access token expires. Do not paste tokens into chat or commit them to GitHub.

First run behavior is intentionally conservative: with `X_SHARE_BACKFILL=false`, the script marks the current feed as already handled and shares only future posts. Set `X_SHARE_BACKFILL=true` if you deliberately want it to catch up older feed items, capped by `X_SHARE_MAX_PER_RUN`.

Test without posting:

```powershell
& 'C:\Users\ELDERCHUCKY\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\src\share_blog_to_x.py --dry-run
```

Share new feed posts once:

```powershell
& 'C:\Users\ELDERCHUCKY\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\src\share_blog_to_x.py
```

### WordPress REST Setup

For self-hosted or plugin-enabled WordPress sites, you can use the REST API instead:

```text
WP_POST_METHOD=rest
WP_BASE_URL=https://your-site.example
WP_USERNAME=automation-author
WP_APPLICATION_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
ARTICLE_GENERATOR=free
```

`OPENAI_API_KEY` is optional. Only use it if you later choose `ARTICLE_GENERATOR=openai` for longer, higher-polish generated articles.

## Dry Run

```powershell
python .\src\wp_auto_blog.py run --dry-run
```

If `python` is not on PATH in this Codex desktop workspace, use:

```powershell
& 'C:\Users\ELDERCHUCKY\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\src\wp_auto_blog.py run --dry-run
```

Dry runs fetch sources, choose a cluster, and write a preview into `out/` without contacting WordPress.

## Create WordPress Drafts

```powershell
python .\src\wp_auto_blog.py run
```

With `POST_STATUS=draft`, this creates drafts. With `POST_STATUS=publish` and the confirmation flag, this publishes live.

With `ARTICLE_GENERATOR=free`, it does not call any paid AI service.

## Auto-Publish

For live publishing, use:

```text
POST_STATUS=publish
AUTO_PUBLISH_CONFIRM=I_UNDERSTAND_POSTS_GO_LIVE
```

Then run:

```powershell
python .\src\wp_auto_blog.py run
```

## Source Notes

The starter source list lives in `config/sources.json`. I chose feeds that match your blog niche: technology, science, gadgets, tutorials, security, DIY hardware, and practical hacks.

Some well-known publishers have restrictive RSS terms. Those are disabled or should be treated only as topic alerts unless you review their terms. The automation is designed for original synthesis with attribution, not content spinning.

Useful references:

- WordPress REST posts endpoint: https://developer.wordpress.org/rest-api/reference/posts/
- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses
- NASA RSS feeds: https://www.nasa.gov/rss-feeds/
- WIRED RSS feeds: https://www.wired.com/about/rss-feeds/
- ScienceDaily RSS feeds: https://www.sciencedaily.com/newsfeeds.htm
- Phys.org RSS feeds: https://phys.org/feeds/

## Scheduling

### Local Schedule

This only works while your PC is on and Codex/Windows can run the job. Use it for testing, not as the final always-on setup:

```powershell
python C:\Users\ELDERCHUCKY\Documents\Codex\2026-05-12\so-i-wanna-automate-my-wordpress\src\wp_auto_blog.py run
```

Current schedule: every 15 minutes, with `MAX_POSTS_PER_RUN=1` and `MAX_POSTS_PER_DAY=24`. The frequent check keeps posts fresh, while the daily cap reduces the risk of flooding the site. The same schedule can run `src/share_blog_to_x.py` after the blog publisher so newly published feed items are shared to X.

The publisher writes a private local health file at `data/last_run_status.json` and uses `data/autoblog.lock` to prevent overlapping runs. If a run appears stuck, the lock is treated as stale after `RUN_LOCK_STALE_SECONDS` seconds, which defaults to 1800.

Check the latest local publishing status without exposing secrets:

```powershell
python .\src\wp_auto_blog.py status
```

### Free Cloud Schedule With GitHub Actions

Use this when you want posting to continue even if your PC is off. The workflow lives at `.github/workflows/wordpress-autoblog.yml` and checks every 10 minutes around `:07`, `:17`, `:27`, `:37`, `:47`, and `:57`, plus manual runs from the GitHub Actions tab. It runs the stale-feed failover, so it checks the live blog first and only publishes when the newest public post is at least 30 minutes old.

1. Create a GitHub repository for this project. A public repository avoids GitHub Actions minute charges for standard runners. A private repository uses your free monthly Actions minutes.
2. Upload or push this folder to that repository.
3. In GitHub, open `Settings -> Secrets and variables -> Actions -> New repository secret`.
4. Add these repository secrets:

```text
POST_BY_EMAIL_ADDRESS=your-secret-address@post.wordpress.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM=your-sender-email@gmail.com
X_USER_ACCESS_TOKEN=your_x_user_access_token
X_CLIENT_ID=your_x_client_id
X_CLIENT_SECRET=your_x_client_secret_if_shown
X_REFRESH_TOKEN=your_x_refresh_token
```

5. Open the repository `Actions` tab and enable workflows if GitHub asks.
6. Open `WordPress Auto Blog Failover`, choose `Run workflow`, and run it once manually.
7. Check your WordPress.com posts/feed.
8. After the GitHub run works, keep local Codex/Windows schedules as backup only. The stale-feed guard should prevent duplicates, but GitHub should be treated as the main PC-off runner.

Do not upload `.env` to GitHub. Put secret values only in GitHub repository secrets.

The cloud workflow commits `data/autoblog.sqlite3` and `data/failover_last_publish.json` after it publishes. Those files are posting memory, not secrets; they help the next cloud run avoid reusing the same source cluster or double-sending while WordPress email is still catching up. Upload the current `data/autoblog.sqlite3` with the first GitHub version so the cloud job remembers what your local runs already posted.

GitHub schedules are free for public repositories using standard runners and private repositories within GitHub's free monthly minutes, but scheduled runs can be delayed or skipped during heavy GitHub load. If exact-to-the-minute publishing becomes important later, use a paid always-on host or cron service.
