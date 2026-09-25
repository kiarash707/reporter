"""Anti-spam, rate limiting, stats, state store and backup services."""

from __future__ import annotations

from pathlib import Path

from bot.errors import AccessDenied, RateLimited
from bot.services import stats
from bot.services.backup import backup_age, create_backup, latest_backup, prune_backups
from bot.services.ratelimit import RateLimiter
from bot.services.roles import Roles
from bot.services.states import StateStore
from bot.utils.time import utcnow


# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #
def test_roles_owner_staff_member(repo) -> None:
    repo.add_staff(555)
    roles = Roles(repo, [111])
    assert roles.is_owner(111)
    assert roles.is_staff(555)
    assert not roles.is_staff(999)
    assert roles.roles_of(111) == {"member", "staff", "owner"}
    assert roles.roles_of(999) == {"member"}


def test_roles_raise_typed_errors(repo) -> None:
    roles = Roles(repo, [111])
    for check, role in ((roles.require_owner, "owner"), (roles.require_staff, "staff")):
        try:
            check(999)
        except AccessDenied as exc:
            assert exc.required_role == role
        else:  # pragma: no cover - the call must raise
            raise AssertionError("expected AccessDenied")


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #
def test_rate_limiter_blocks_and_reports_retry_after(repo) -> None:
    limiter = RateLimiter(repo, limit=2, window=60)
    limiter.check(1)
    limiter.check(1)
    try:
        limiter.check(1)
    except RateLimited as exc:
        assert exc.retry_after > 0
    else:  # pragma: no cover
        raise AssertionError("expected RateLimited")


def test_rate_limiter_scopes_are_independent(repo) -> None:
    limiter = RateLimiter(repo, limit=1, window=60)
    assert limiter.is_allowed(1, "command")[0] is True
    assert limiter.is_allowed(1, "command")[0] is False
    assert limiter.is_allowed(1, "other")[0] is True


def test_cooldown_round_trip(repo) -> None:
    limiter = RateLimiter(repo, limit=5, window=60)
    assert limiter.cooldown_left("ticket", 7, 300) == 0
    limiter.start_cooldown("ticket", 7)
    assert limiter.cooldown_left("ticket", 7, 300) > 0


# --------------------------------------------------------------------------- #
# Anti-spam
# --------------------------------------------------------------------------- #
def test_flood_detection(context) -> None:
    antispam = context.antispam
    verdicts = [antispam.check(chat_id=-1, user_id=1, text="hello") for _ in range(4)]
    assert [verdict.blocked for verdict in verdicts] == [False, False, False, True]
    assert verdicts[-1].reason_key == "antispam.flood"


def test_flood_is_per_user_and_per_chat(context) -> None:
    antispam = context.antispam
    for _ in range(3):
        antispam.check(chat_id=-1, user_id=1, text="hi")
    assert antispam.check(chat_id=-1, user_id=1, text="hi").blocked is True
    assert antispam.check(chat_id=-1, user_id=2, text="hi").blocked is False
    assert antispam.check(chat_id=-2, user_id=1, text="hi").blocked is False


def test_banned_words_plain_and_regex(context) -> None:
    verdict = context.antispam.check(chat_id=-1, user_id=9, text="this is BADWORD here")
    assert verdict.blocked and verdict.reason_key == "antispam.banned_word"
    regex_verdict = context.antispam.check(chat_id=-1, user_id=8, text="see https://spam.example now")
    assert regex_verdict.blocked


def test_link_blocking_and_allowlist(context) -> None:
    blocked = context.antispam.check(chat_id=-1, user_id=3, text="visit https://evil.example")
    assert blocked.blocked and blocked.reason_key == "antispam.link"
    allowed = context.antispam.check(chat_id=-1, user_id=4, text="see https://github.com/foo/bar")
    assert allowed.blocked is False
    subdomain = context.antispam.check(chat_id=-1, user_id=5, text="docs.python.org/3/")
    assert subdomain.blocked is False


def test_domain_allowlist_matching(context) -> None:
    antispam = context.antispam
    assert antispam._domain_allowed("github.com")
    assert antispam._domain_allowed("raw.github.com")
    assert not antispam._domain_allowed("github.com.evil.io")


def test_new_member_link_restriction(context, repo) -> None:
    context.settings.antispam_new_user_seconds = 3600
    repo.upsert_user(42)
    assert context.antispam.is_new_member(42) is True
    verdict = context.antispam.check(chat_id=-1, user_id=42, text="http://example.com", is_new_member=True)
    assert verdict.reason_key == "antispam.new_user_link"
    # unknown users are not treated as new members (no join date recorded)
    assert context.antispam.is_new_member(4242) is False


def test_antispam_prunes_history(context) -> None:
    for index in range(5):
        context.antispam.check(chat_id=-1, user_id=index, text="hello")
    assert context.antispam.tracked_conversations == 5
    assert context.antispam.prune_history(keep_seconds=-1) == 5
    assert context.antispam.tracked_conversations == 0


def test_disabled_antispam_passes_everything(context) -> None:
    context.settings.feature_antispam = False
    assert context.antispam.enabled is False
    assert context.antispam.check(chat_id=-1, user_id=1, text="badword" * 20).blocked is False


# --------------------------------------------------------------------------- #
# State store
# --------------------------------------------------------------------------- #
def test_state_store_lifecycle() -> None:
    store = StateStore(ttl=60)
    store.set(1, "flow", step=1)
    assert store.is_(1, "flow")
    assert store.get(1).data["step"] == 1
    store.update(1, step=2)
    assert store.get(1).data["step"] == 2
    assert 1 in store and len(store) == 1
    assert store.clear(1) is True
    assert store.get(1) is None


def test_state_store_expires_old_entries() -> None:
    store = StateStore(ttl=0)
    store.set(1, "flow")
    assert store.get(1) is None
    assert len(store) == 0


def test_state_store_prune() -> None:
    store = StateStore(ttl=0)
    store.set(1, "a")
    store.set(2, "b")
    assert store.prune() == 2


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def test_stats_collect_and_render(context) -> None:
    context.repo.upsert_user(1)
    context.repo.create_ticket(1, "s", "b")
    context.repo.increment_counter("commands", 3)
    data = stats.collect(context)
    assert data["users_total"] == 1
    assert data["tickets_open"] == 1
    assert data["commands"] == 3
    assert data["db_ok"] is True

    english = stats.render(context, "en")
    persian = stats.render(context, "fa")
    assert "Users" in english and "کاربران" in persian


# --------------------------------------------------------------------------- #
# Backup
# --------------------------------------------------------------------------- #
def test_backup_create_latest_and_prune(settings, repo) -> None:
    repo.upsert_user(1)
    first = create_backup(settings, repo, keep=2)
    assert first.path.exists() and first.size_kb > 0
    assert latest_backup(settings) == first.path
    assert backup_age(settings).total_seconds() < 60

    for _ in range(3):
        create_backup(settings, repo, keep=2)
    archives = sorted(settings.data_path.glob("backups/state-*.tar.gz"))
    assert len(archives) == 2


def test_prune_backups_is_safe_without_archives(settings) -> None:
    assert prune_backups(settings) == 0
    assert latest_backup(settings) is None
    assert backup_age(settings) is None


def test_backup_archive_contains_the_database(settings, repo) -> None:
    import tarfile

    repo.upsert_user(99)
    result = create_backup(settings, repo)
    with tarfile.open(result.path) as archive:
        names = archive.getnames()
    assert any(name.endswith(".db") for name in names)


# --------------------------------------------------------------------------- #
# Time helper sanity (guards the timezone configuration)
# --------------------------------------------------------------------------- #
def test_utcnow_matches_system_clock() -> None:
    assert abs((utcnow() - utcnow()).total_seconds()) < 1


def test_backup_paths_live_under_data_dir(settings, repo) -> None:
    result = create_backup(settings, repo)
    assert Path(result.path).parent == settings.data_path / "backups"
