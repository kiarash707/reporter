"""Inline keyboard builders.

Callback data follows ``<scope>:<action>[:<id>]`` so a single dispatcher can
route everything and the data stays far below Telegram's 64-byte limit.
"""

from __future__ import annotations

from telethon import Button

from bot.context import AppContext

# --- callback data constants ------------------------------------------------
CB_HOME = "menu:home"
CB_HELP = "menu:help"
CB_STATS = "menu:stats"
CB_LANG = "menu:lang"
CB_LANG_FA = "menu:lang:fa"
CB_LANG_EN = "menu:lang:en"
CB_TICKETS = "menu:tickets"
CB_TICKET_NEW = "menu:ticket:new"
CB_TICKET_LIST = "menu:ticket:list"
CB_OWNER = "menu:owner"
CB_GROUP = "menu:group"
CB_CLOSE = "menu:close"

CB_ACCEPT_RULES = "rules:accept"

CB_GROUP_ANTISPAM = "grp:antispam"
CB_GROUP_WELCOME = "grp:welcome"
CB_GROUP_RULES = "grp:rules"
CB_GROUP_STATS = "grp:stats"

CB_OWN_TOGGLE = "own:toggle"
CB_OWN_BROADCAST = "own:broadcast"
CB_OWN_BROADCAST_GO = "own:broadcast:go"
CB_OWN_BACKUP = "own:backup"
CB_OWN_AUDIT = "own:audit"
CB_OWN_IMPORT = "own:import"
CB_OWN_STAFF = "own:staff"

CB_TICKET_REPLY = "ticket:reply"  # ticket:reply:<id>
CB_TICKET_CLOSE = "ticket:close"  # ticket:close:<id>
CB_TICKET_VIEW = "ticket:view"  # ticket:view:<id>


def _t(ctx: AppContext, language: str, key: str, **params: object) -> str:
    return ctx.tr(key, language, **params)


def back_button(ctx: AppContext, language: str, data: str = CB_HOME) -> list[Button]:
    return [Button.inline(_t(ctx, language, "common.back"), data)]


def cancel_button(ctx: AppContext, language: str) -> list[Button]:
    return [Button.inline(_t(ctx, language, "common.cancel"), CB_CLOSE)]


def main_menu(
    ctx: AppContext, language: str, *, is_staff: bool, is_owner: bool, in_group: bool = False
) -> list[list[Button]]:
    """Main menu shown to regular users, extended for staff/owners."""
    rows: list[list[Button]] = [
        [
            Button.inline(_t(ctx, language, "menu.help"), CB_HELP),
            Button.inline(_t(ctx, language, "menu.tickets"), CB_TICKETS),
        ],
        [
            Button.inline(_t(ctx, language, "menu.settings"), CB_LANG),
            Button.inline(_t(ctx, language, "menu.stats"), CB_STATS),
        ],
    ]
    if is_staff and in_group:
        rows.append([Button.inline(_t(ctx, language, "menu.group_panel"), CB_GROUP)])
    if is_owner:
        rows.append([Button.inline(_t(ctx, language, "menu.owner_panel"), CB_OWNER)])
    return rows


def settings_menu(ctx: AppContext, language: str) -> list[list[Button]]:
    return [[Button.inline(_t(ctx, language, "menu.language"), CB_LANG)], back_button(ctx, language)]


def language_menu(ctx: AppContext, language: str) -> list[list[Button]]:
    return [
        [Button.inline("🇮🇷 فارسی", CB_LANG_FA), Button.inline("🇬🇧 English", CB_LANG_EN)],
        back_button(ctx, language),
    ]


def tickets_menu(ctx: AppContext, language: str) -> list[list[Button]]:
    return [
        [Button.inline(_t(ctx, language, "menu.new_ticket"), CB_TICKET_NEW)],
        [Button.inline(_t(ctx, language, "menu.my_tickets"), CB_TICKET_LIST)],
        back_button(ctx, language),
    ]


def ticket_detail_actions(ctx: AppContext, language: str, ticket_id: int) -> list[list[Button]]:
    return [
        [Button.inline(_t(ctx, language, "common.close"), f"{CB_TICKET_CLOSE}:{ticket_id}")],
        [Button.inline(_t(ctx, language, "menu.back_to_menu"), CB_HOME)],
    ]


def staff_ticket_actions(ctx: AppContext, language: str, ticket_id: int) -> list[list[Button]]:
    return [
        [
            Button.inline("✍️ " + _t(ctx, language, "menu.tickets"), f"{CB_TICKET_REPLY}:{ticket_id}"),
            Button.inline("✅ " + _t(ctx, language, "common.close"), f"{CB_TICKET_CLOSE}:{ticket_id}"),
        ]
    ]


def group_panel(ctx: AppContext, language: str, *, antispam: bool, welcome: bool) -> list[list[Button]]:
    def toggle(label_key: str, enabled: bool, data: str) -> Button:
        icon = "🟢" if enabled else "🔴"
        return Button.inline(f"{icon} {_t(ctx, language, label_key)}", data)

    return [
        [toggle("menu.toggle_antispam", antispam, CB_GROUP_ANTISPAM)],
        [toggle("menu.toggle_welcome", welcome, CB_GROUP_WELCOME)],
        [
            Button.inline(_t(ctx, language, "menu.set_rules"), CB_GROUP_RULES),
            Button.inline(_t(ctx, language, "menu.stats"), CB_GROUP_STATS),
        ],
        back_button(ctx, language),
    ]


def owner_panel(ctx: AppContext, language: str, *, bot_enabled: bool) -> list[list[Button]]:
    icon = "🟢" if bot_enabled else "🔴"
    return [
        [Button.inline(f"{icon} {_t(ctx, language, 'owner.toggle_bot')}", CB_OWN_TOGGLE)],
        [
            Button.inline(_t(ctx, language, "owner.broadcast"), CB_OWN_BROADCAST),
            Button.inline(_t(ctx, language, "owner.audit"), CB_OWN_AUDIT),
        ],
        [
            Button.inline(_t(ctx, language, "owner.backup"), CB_OWN_BACKUP),
            Button.inline(_t(ctx, language, "owner.import_legacy"), CB_OWN_IMPORT),
        ],
        [Button.inline("👥 " + _t(ctx, language, "owner.staff_list", staff="").strip(), CB_OWN_STAFF)],
        back_button(ctx, language),
    ]
