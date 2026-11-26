KIDSHUB VN - TELEGRAM BOT FOUNDATION

Files:
- KidsHub_VN.py: bot source code
- requirements.txt: Python dependencies
- render.yaml: Render Background Worker blueprint with persistent disk
- KidsHub_VN.env.example: example environment variables (do not put real secrets here)

Deploy on Render:
1. Create a private GitHub repository.
2. Upload the four files above to the repository root.
3. In Render, create a new Blueprint and connect that GitHub repository.
4. Review render.yaml. The worker is configured as a Starter worker and has a 1 GB persistent disk.
5. When prompted, enter BOT_TOKEN as a secret environment variable. Never commit the real token.
6. ADMIN_IDS is preset to 7330307381. Confirm this is the intended owner Telegram ID.
7. Deploy and inspect the worker logs.

Important:
- A Telegram polling bot should run as a Background Worker, not as a static site.
- Render's persistent disk and continuously running worker are paid features; check current pricing before deploying.
- This is a clean starter bot, not a complete port of the two original source files.
- It intentionally does not include gambling prediction, betting integrations, paid prediction access, or bank deposit automation.
- Do not upload real .env files, bot tokens, API keys, bank details, or personal secrets to GitHub.
