from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    discord_token: str
    discord_guild_id: int
    discord_channel_id: int
    github_webhook_secret: str
    db_path: str
    port: int


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


def load() -> Config:
    load_dotenv()
    return Config(
        discord_token=_required("DISCORD_TOKEN"),
        discord_guild_id=int(_required("DISCORD_GUILD_ID")),
        discord_channel_id=int(_required("DISCORD_CHANNEL_ID")),
        github_webhook_secret=_required("GITHUB_WEBHOOK_SECRET"),
        db_path=os.environ.get("DB_PATH", "./todos.db"),
        port=int(os.environ.get("PORT", "8080")),
    )
