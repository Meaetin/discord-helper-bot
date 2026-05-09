from __future__ import annotations

import logging

import discord
from discord import app_commands

from .db import Todo, TodoStore

log = logging.getLogger(__name__)

STATUS_CHOICES = [
    app_commands.Choice(name="open", value="open"),
    app_commands.Choice(name="done", value="done"),
    app_commands.Choice(name="all", value="all"),
]


def _format_todo_line(t: Todo) -> str:
    check = "✅" if t.status == "done" else "▫️"
    parts = [f"{check} **#{t.id}** {t.text}"]
    meta: list[str] = []
    if t.assignee_id:
        meta.append(f"<@{t.assignee_id}>")
    if t.tags:
        meta.append(" ".join(f"`#{tag}`" for tag in t.tag_list))
    if meta:
        parts.append("— " + " ".join(meta))
    return " ".join(parts)


def build_client(store: TodoStore, guild_id: int) -> discord.Client:
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    guild = discord.Object(id=guild_id)

    todo_group = app_commands.Group(name="todo", description="Team todo list")

    @todo_group.command(name="add", description="Add a todo")
    @app_commands.describe(
        text="What needs doing",
        assignee="Who owns it (optional)",
        tags="Comma-separated tags (optional)",
    )
    async def todo_add(
        interaction: discord.Interaction,
        text: str,
        assignee: discord.User | None = None,
        tags: str | None = None,
    ) -> None:
        todo = await store.add(
            text=text,
            created_by=interaction.user.id,
            assignee_id=assignee.id if assignee else None,
            tags=tags,
        )
        await interaction.response.send_message(
            f"Added **#{todo.id}**: {todo.text}", ephemeral=False
        )

    @todo_group.command(name="list", description="List todos")
    @app_commands.describe(
        assignee="Filter by assignee",
        tag="Filter by tag",
        status="Filter by status (default: open)",
    )
    @app_commands.choices(status=STATUS_CHOICES)
    async def todo_list(
        interaction: discord.Interaction,
        assignee: discord.User | None = None,
        tag: str | None = None,
        status: app_commands.Choice[str] | None = None,
    ) -> None:
        status_value = status.value if status else "open"
        todos = await store.list(
            status=status_value,  # type: ignore[arg-type]
            assignee_id=assignee.id if assignee else None,
            tag=tag,
        )
        if not todos:
            await interaction.response.send_message("No todos found.", ephemeral=True)
            return
        title_bits = [f"Todos ({status_value})"]
        if assignee:
            title_bits.append(f"for {assignee.display_name}")
        if tag:
            title_bits.append(f"#{tag}")
        embed = discord.Embed(
            title=" · ".join(title_bits),
            description="\n".join(_format_todo_line(t) for t in todos),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed)

    @todo_group.command(name="done", description="Mark a todo as done")
    @app_commands.describe(id="Todo id")
    async def todo_done(interaction: discord.Interaction, id: int) -> None:
        try:
            todo = await store.mark_done(id)
        except KeyError:
            await interaction.response.send_message(f"No todo with id {id}.", ephemeral=True)
            return
        await interaction.response.send_message(f"Done ✅ **#{todo.id}**: {todo.text}")

    @todo_group.command(name="remove", description="Delete a todo")
    @app_commands.describe(id="Todo id")
    async def todo_remove(interaction: discord.Interaction, id: int) -> None:
        try:
            await store.remove(id)
        except KeyError:
            await interaction.response.send_message(f"No todo with id {id}.", ephemeral=True)
            return
        await interaction.response.send_message(f"Removed **#{id}**.")

    @todo_group.command(name="assign", description="Assign a todo to a user")
    @app_commands.describe(id="Todo id", user="Assignee")
    async def todo_assign(
        interaction: discord.Interaction, id: int, user: discord.User
    ) -> None:
        try:
            todo = await store.assign(id, user.id)
        except KeyError:
            await interaction.response.send_message(f"No todo with id {id}.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Assigned **#{todo.id}** to {user.mention}."
        )

    tree.add_command(todo_group, guild=guild)

    @client.event
    async def on_ready() -> None:
        await tree.sync(guild=guild)
        log.info("logged in as %s; commands synced to guild %s", client.user, guild_id)

    return client
