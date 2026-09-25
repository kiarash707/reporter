"""Command and menu handlers available to every user."""

from __future__ import annotations

import logging
import re

from telethon import TelegramClient, events

from bot.context import AppContext
from bot.handlers.guard import edit, guard, reply
from bot.keyboards import (
    CB_ACCEPT_RULES,
    CB_CLOSE,
    CB_GROUP,
    CB_HELP,
    CB_HOME,
    CB_LANG,
    CB_OWNER,
    CB_STATS,
    CB_TICKET_LIST,
    CB_TICKET_NEW,
    CB_TICKETS,
    language_menu,
    main_menu,
    tickets_menu,
)
from bot.services import stats
from bot.utils.telegram import display_name
from bot.utils.text import escape_html

logger = logging.getLogger("bot.handlers.common")

START_PATTERN = r"^/start(?:@[\w_]+)?(?:\s|$)"
HELP_PATTERN = r"^/help(?:@[\w_]+)?(?:\s|$)"
CANCEL_PATTERN = r"^/cancel(?:@[\w_]+)?(?:\s|$)"
ID_PATTERN = r"^/id(?:@[\w_]+)?$"
LANG_PATTERN = r"^/lang(?:@[\w_]+)?$"
STATS_PATTERN = r"^/stats(?:@[\w_]+)?$"


def register(client: TelegramClient, ctx: AppContext) -> None:
    """Attach the general-purpose handlers."""

    # ---------------------------------------------------------------- /start
    @client.on(events.NewMessage(pattern=START_PATTERN))
    @guard(ctx)
    async def start(event: events.NewMessage.Event) -> None:
        user = await event.get_sender()
        user_id = int(event.sender_id)
        ctx.repo.upsert_user(
            user_id,
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
        )
        language = ctx.language_of(user_id)

        if ctx.repo.is_blocked(user_id) and not ctx.is_owner(user_id):
            await reply(event, ctx.tr("start.blocked", language))
            return

        ctx.states.clear(user_id)

        if event.is_group:
            intro = ctx.tr("start.private_only", language)
            await reply(event, intro)
            return

        profile = ctx.repo.get_user(user_id) or {}
        if not profile.get("accepted_rules"):
            from telethon import Button

            await reply(
                event,
                ctx.tr("start.rules", language),
                buttons=[[Button.inline(ctx.tr("start.accept_rules", language), CB_ACCEPT_RULES)]],
            )
            return

        await event.respond(
            ctx.tr("start.welcome", language, name=escape_html(display_name(user))),
            buttons=_menu(ctx, event, user_id),
            parse_mode="html",
            link_preview=False,
        )

    # ----------------------------------------------------------------- /help
    @client.on(events.NewMessage(pattern=HELP_PATTERN))
    @guard(ctx)
    async def help_command(event: events.NewMessage.Event) -> None:
        await reply(event, _help_text(ctx, event, int(event.sender_id)))

    # ------------------------------------------------------------------- /id
    @client.on(events.NewMessage(pattern=ID_PATTERN))
    @guard(ctx)
    async def show_id(event: events.NewMessage.Event) -> None:
        lines = [f"👤 <code>{event.sender_id}</code>"]
        if event.is_group:
            lines.append(f"💬 chat: <code>{event.chat_id}</code>")
        await reply(event, "\n".join(lines))

    # ----------------------------------------------------------------- /lang
    @client.on(events.NewMessage(pattern=LANG_PATTERN))
    @guard(ctx)
    async def language_command(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        await event.respond(
            ctx.tr("language.title", language),
            buttons=language_menu(ctx, language),
            parse_mode="html",
            link_preview=False,
        )

    # --------------------------------------------------------------- /cancel
    @client.on(events.NewMessage(pattern=CANCEL_PATTERN))
    @guard(ctx)
    async def cancel(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        ctx.states.clear(int(event.sender_id))
        await reply(event, ctx.tr("common.cancelled", language))

    # ---------------------------------------------------------------- /stats
    @client.on(events.NewMessage(pattern=STATS_PATTERN))
    @guard(ctx)
    async def stats_command(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        await reply(event, stats.render(ctx, language))

    # ------------------------------------------------------------- callbacks
    @client.on(events.CallbackQuery(data=CB_ACCEPT_RULES))
    @guard(ctx)
    async def accept_rules(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        language = ctx.language_of(user_id)
        ctx.repo.set_accepted_rules(user_id, True)
        ctx.repo.upsert_user(user_id)
        await event.answer("✅")
        await edit(event, ctx.tr("start.rules_accepted", language))
        await event.respond(
            ctx.tr("start.welcome", language, name=escape_html(display_name(await event.get_sender()))),
            buttons=_menu(ctx, event, user_id),
            parse_mode="html",
            link_preview=False,
        )

    @client.on(events.CallbackQuery(data=CB_HOME))
    @guard(ctx)
    async def home(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        language = ctx.language_of(user_id)
        await edit(event, ctx.tr("menu.title", language), buttons=_menu(ctx, event, user_id))

    @client.on(events.CallbackQuery(data=CB_HELP))
    @guard(ctx)
    async def help_callback(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        await edit(event, _help_text(ctx, event, user_id), buttons=_menu(ctx, event, user_id))

    @client.on(events.CallbackQuery(data=CB_STATS))
    @guard(ctx)
    async def stats_callback(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        await edit(event, stats.render(ctx, ctx.language_of(user_id)), buttons=_menu(ctx, event, user_id))

    @client.on(events.CallbackQuery(data=CB_LANG))
    @guard(ctx)
    async def language_callback(event: events.CallbackQuery.Event) -> None:
        language = ctx.language_of(event.sender_id)
        await edit(event, ctx.tr("language.title", language), buttons=language_menu(ctx, language))

    # ``data=`` must be bytes (exact match) - a regex covers both language buttons.
    @client.on(events.CallbackQuery(pattern=re.compile(rb"^menu:lang:(fa|en)$")))
    @guard(ctx)
    async def language_set(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        target = "fa" if event.data.decode().endswith(":fa") else "en"
        ctx.repo.set_language(user_id, target)
        await editor_language_changed(event, ctx, user_id, target)

    @client.on(events.CallbackQuery(data=CB_TICKETS))
    @guard(ctx)
    async def tickets_callback(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        language = ctx.language_of(user_id)
        await edit(
            event,
            ctx.tr("menu.tickets", language) + "\n\n" + ctx.tr("help.body", language),
            buttons=tickets_menu(ctx, language),
        )

    @client.on(events.CallbackQuery(data=CB_TICKET_NEW))
    @guard(ctx)
    async def ticket_new_callback(event: events.CallbackQuery.Event) -> None:
        from bot.handlers import tickets as tickets_module

        await tickets_module.start_ticket_flow(ctx, event, int(event.sender_id), mode="callback")

    @client.on(events.CallbackQuery(data=CB_TICKET_LIST))
    @guard(ctx)
    async def ticket_list_callback(event: events.CallbackQuery.Event) -> None:
        from bot.handlers import tickets as tickets_module

        await tickets_module.show_my_tickets(ctx, event, int(event.sender_id), mode="callback")

    @client.on(events.CallbackQuery(data=CB_OWNER))
    @guard(ctx, staff_only=True)
    async def owner_callback(event: events.CallbackQuery.Event) -> None:
        from bot.handlers import owner as owner_module

        await owner_module.show_panel(ctx, event)

    @client.on(events.CallbackQuery(data=CB_GROUP))
    @guard(ctx, staff_only=True)
    async def group_callback(event: events.CallbackQuery.Event) -> None:
        from bot.handlers import moderation as moderation_module

        await moderation_module.show_panel(ctx, event)

    @client.on(events.CallbackQuery(data=CB_CLOSE))
    @guard(ctx)
    async def close_callback(event: events.CallbackQuery.Event) -> None:
        ctx.states.clear(int(event.sender_id))
        await event.answer("👌")
        try:
            await event.delete()
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("Cannot delete menu message: %s", exc)


async def editor_language_changed(
    event: events.CallbackQuery.Event, ctx: AppContext, user_id: int, target: str
) -> None:
    """Confirm the language switch and re-render the menu in the new language."""
    await event.answer("✅")
    await edit(event, ctx.tr("language.changed", target))
    await event.respond(
        ctx.tr("menu.title", target),
        buttons=_menu_for(ctx, target, user_id, in_group=bool(event.is_group)),
        parse_mode="html",
        link_preview=False,
    )


def _menu(ctx: AppContext, event: events.common.EventCommon, user_id: int) -> list[list[object]]:
    return _menu_for(ctx, ctx.language_of(user_id), user_id, in_group=bool(getattr(event, "is_group", False)))


def _menu_for(ctx: AppContext, language: str, user_id: int, *, in_group: bool) -> list[list[object]]:
    return main_menu(
        ctx,
        language,
        is_staff=ctx.roles.is_staff(user_id),
        is_owner=ctx.roles.is_owner(user_id),
        in_group=in_group,
    )


def _help_text(ctx: AppContext, event: events.common.EventCommon, user_id: int) -> str:
    language = ctx.language_of(user_id)
    text = f"{ctx.tr('help.title', language)}\n\n{ctx.tr('help.body', language)}"
    if event.is_group and ctx.roles.is_staff(user_id):
        text += ctx.tr("help.admin_body", language)
    if ctx.is_owner(user_id):
        text += ctx.tr("help.owner_body", language)
    return text
