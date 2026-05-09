# discord-helper-bot

Discord bot for a small team:

- Posts a rich embed when a GitHub PR is merged.
- `/todo` slash commands to manage a shared team todo list.

## Setup

1. **Discord bot** — create one at https://discord.com/developers/applications. Enable `applications.commands` scope. Invite to your server with permission to read/send messages in the target channel. Copy the bot token.
2. **GitHub webhook** — repo Settings → Webhooks → Add webhook:
   - Payload URL: `https://your-host/github/webhook`
   - Content type: `application/json`
   - Secret: random 32+ char string (also put in `.env`)
   - Events: only **Pull requests**
3. **Env vars** — copy `.env.example` to `.env` and fill in.

## Run locally

```sh
uv sync
uv run python -m bot.main
```

For local webhook testing, use `cloudflared tunnel --url http://localhost:8080` or `ngrok http 8080` and point the GitHub webhook at the public URL.

## Slash commands

- `/todo add text:<text> [assignee:@user] [tags:<csv>]`
- `/todo list [assignee:@user] [tag:<name>] [status:open|done|all]`
- `/todo done id:<n>`
- `/todo remove id:<n>`
- `/todo assign id:<n> user:@user`

## Deploy (Railway)

1. Push to GitHub, connect the repo on https://railway.app.
2. Add env vars in Railway dashboard.
3. Mount a volume at `/data` and set `DB_PATH=/data/todos.db`.
4. Copy the public URL and add `+/github/webhook` to the GitHub webhook config.
