from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from . import config, db, discord_client, webhook


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run() -> None:
    _setup_logging()
    cfg = config.load()

    store = await db.TodoStore.open(cfg.db_path)
    client = discord_client.build_client(store, cfg.discord_guild_id)
    app = webhook.build_app(
        client=client,
        channel_id=cfg.discord_channel_id,
        secret=cfg.github_webhook_secret,
    )

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=cfg.port)

    try:
        async with client:
            await asyncio.gather(
                client.start(cfg.discord_token),
                site.start(),
            )
    finally:
        await runner.cleanup()
        await store.close()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
