r"""Quick smoke checks: db CRUD + webhook signature verification.

Run from project root: .\.venv\Scripts\python.exe tests\smoke.py
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bot.db import TodoStore  # noqa: E402
from bot.webhook import _verify_signature  # noqa: E402


async def test_db() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = await TodoStore.open(os.path.join(tmp, "test.db"))
        try:
            t1 = await store.add("buy milk", created_by=111, tags="groceries,#urgent")
            assert t1.id == 1
            assert t1.tags == "groceries,urgent", t1.tags
            assert t1.tag_list == ["groceries", "urgent"]

            t2 = await store.add("write tests", created_by=111, assignee_id=222)
            assert t2.id == 2

            opens = await store.list(status="open")
            assert len(opens) == 2

            await store.mark_done(t1.id)
            opens = await store.list(status="open")
            assert len(opens) == 1, opens
            done = await store.list(status="done")
            assert len(done) == 1

            tagged = await store.list(status="all", tag="urgent")
            assert len(tagged) == 1 and tagged[0].id == t1.id

            assigned = await store.list(status="all", assignee_id=222)
            assert len(assigned) == 1 and assigned[0].id == t2.id

            await store.assign(t1.id, 333)
            assert (await store.get(t1.id)).assignee_id == 333

            await store.remove(t2.id)
            try:
                await store.remove(t2.id)
            except KeyError:
                pass
            else:
                raise AssertionError("expected KeyError on double remove")

            print("db: OK")
        finally:
            await store.close()


def test_webhook_signature() -> None:
    secret = "supersecret"
    body = b'{"hello":"world"}'
    good_sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert _verify_signature(secret, body, good_sig)
    assert not _verify_signature(secret, body, "sha256=" + "0" * 64)
    assert not _verify_signature(secret, body, None)
    assert not _verify_signature(secret, body, "sha1=foo")
    print("webhook signature: OK")


async def main() -> None:
    await test_db()
    test_webhook_signature()
    print("\nall smoke checks passed")


if __name__ == "__main__":
    asyncio.run(main())
