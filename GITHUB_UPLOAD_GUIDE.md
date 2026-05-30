# GitHub Cloud Publishing Setup

This guide moves the blog automation from your PC to GitHub Actions so posts can publish even when your PC is off. GitHub runs the stale-feed failover, so it checks the live blog first and only publishes when the site has gone stale.

Important: do not upload `.env`. It contains private passwords. Use GitHub repository secrets instead.

## 1. Create the GitHub Repository

1. Go to https://github.com and sign in.
2. Click the `+` button near the top right.
3. Click `New repository`.
4. Repository name: `chuckys-autoblog`
5. Choose `Public` if you want to avoid GitHub Actions minute charges for standard runners.
6. Do not add README, gitignore, or license on GitHub. This project already includes the files.
7. Click `Create repository`.

## 2. Upload the Files

1. Open the new repository page.
2. Click `uploading an existing file`.
3. Open the prepared upload folder on your PC.
4. Select everything inside that folder and drag it into GitHub.
5. Make sure `.env` is not there.
6. Click `Commit changes`.

## 3. Add GitHub Secrets

Go to:

`Repository -> Settings -> Secrets and variables -> Actions -> New repository secret`

Add these secrets one by one:

```text
POST_BY_EMAIL_ADDRESS
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_FROM
```

For Gmail, use:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your Gmail address
SMTP_PASSWORD=your Gmail app password
SMTP_FROM=your Gmail address
```

Use your real private values from your local `.env` file, but do not paste them into GitHub code files.

## 4. Start the Cloud Automation

1. Open the repository `Actions` tab.
2. If GitHub asks, click `I understand my workflows, go ahead and enable them`.
3. Click `WordPress Auto Blog Failover`.
4. Click `Run workflow`.
5. Click the green `Run workflow` button.
6. Open the running job and watch the logs.

A successful run should show something like:

```text
Delivered post with status=publish
```

## 5. After It Works

Once GitHub Actions publishes successfully, keep the Windows/Codex jobs as backups only. The stale-feed guard prevents duplicate posts, but GitHub should become the main PC-off runner.

The workflow now runs as a cloud watchdog. One run checks the public feed every 5 minutes for about 70 minutes, then queues the next watchdog run. GitHub scheduled runs at `:13` and `:43` are backup kicks in case a runner dies or the self-queue is delayed.

A second GitHub workflow, `WordPress Auto Blog Rescue Guard`, checks every 15 minutes at `:05`, `:20`, `:35`, and `:50`. It uses the public feed and GitHub run history to stand down while the main watchdog is healthy, cancel a stale main watchdog run if needed, and publish only when the feed is stale.

The main watchdog publishes when the latest public post is at least 20 minutes old. The rescue guard publishes only when the latest public post is at least 35 minutes old, unless the feed becomes much older and needs emergency recovery. The automation still respects:

```text
MAX_POSTS_PER_RUN=1
MAX_POSTS_PER_DAY=90
```

The files `data/autoblog.sqlite3` and `data/failover_last_publish.json` are included on purpose. They remember posting state so the cloud version does not reuse old source clusters or double-send while WordPress email is still catching up.
