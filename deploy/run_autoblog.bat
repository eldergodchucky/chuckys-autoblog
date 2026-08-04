@echo off
set "ROOT=C:\Users\ELDERCHUCKY\Documents\Codex\2026-05-12\so-i-wanna-automate-my-wordpress"
cd /d "%ROOT%"
"%ROOT%\.venv\Scripts\python.exe" src\wp_auto_blog.py run >> "%ROOT%\data\task_run.log" 2>&1
