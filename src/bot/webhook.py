from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any

import discord
from aiohttp import web

log = logging.getLogger(__name__)

MAX_TITLE = 240
PR_MERGED_COLOR = 0x28A745


def _verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def _build_embed(payload: dict[str, Any]) -> discord.Embed:
    pr = payload["pull_request"]
    repo = payload["repository"]

    title = pr["title"]
    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE].rstrip() + "…"

    embed = discord.Embed(
        title=f"PR #{pr['number']} merged: {title}",
        url=pr["html_url"],
        color=PR_MERGED_COLOR,
    )

    author = pr.get("user") or {}
    if author.get("login"):
        author_kwargs: dict[str, str] = {"name": author["login"]}
        if author.get("html_url"):
            author_kwargs["url"] = author["html_url"]
        if author.get("avatar_url"):
            author_kwargs["icon_url"] = author["avatar_url"]
        embed.set_author(**author_kwargs)

    embed.add_field(
        name="Branch",
        value=f"`{pr['head']['ref']}` → `{pr['base']['ref']}`",
        inline=True,
    )
    merged_by = (pr.get("merged_by") or {}).get("login")
    if merged_by:
        embed.add_field(name="Merged by", value=merged_by, inline=True)

    embed.set_footer(text=repo["full_name"])
    if pr.get("merged_at"):
        embed.timestamp = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
    return embed


def build_app(
    *,
    client: discord.Client,
    channel_id: int,
    secret: str,
) -> web.Application:
    async def handle(request: web.Request) -> web.Response:
        body = await request.read()
        if not _verify_signature(secret, body, request.headers.get("X-Hub-Signature-256")):
            log.warning("rejected webhook with bad signature")
            return web.Response(status=401, text="bad signature")

        event = request.headers.get("X-GitHub-Event")
        if event == "ping":
            return web.json_response({"pong": True})
        if event != "pull_request":
            return web.Response(status=204)

        try:
            payload = await request.json()
        except ValueError:
            return web.Response(status=400, text="invalid json")

        if payload.get("action") != "closed":
            return web.Response(status=204)
        if not (payload.get("pull_request") or {}).get("merged"):
            return web.Response(status=204)

        channel = client.get_channel(channel_id)
        if channel is None:
            log.error("channel %s not in cache; cannot post embed", channel_id)
            return web.Response(status=503, text="discord not ready")

        embed = _build_embed(payload)
        await channel.send(embed=embed)  # type: ignore[union-attr]
        log.info("posted PR #%s merged notification", payload["pull_request"]["number"])
        return web.Response(status=204)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_post("/github/webhook", handle)
    app.router.add_get("/health", health)
    return app
