"""Repository behaviour: users, warnings, tickets, counters, rate limits, import."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.errors import StorageError
from bot.storage.database import Database
from bot.storage.repository import TICKET_ANSWERED, TICKET_CLOSED, TICKET_OPEN, Repository


def test_migration_is_idempotent(settings) -> None:
    database = Database(settings.db_file)
    assert database.migrate() == 1
    assert database.migrate() == 1
    database.close()


def test_user_lifecycle(repo: Repository) -> None:
    repo.upsert_user(5, username="ali", first_name="Ali")
    assert repo.get_language(5) == "fa"
    repo.set_language(5, "en")
    assert repo.get_language(5) == "en"
    assert repo.is_blocked(5) is False
    repo.set_blocked(5, True, reason="spam")
    assert repo.is_blocked(5) is True
    assert repo.broadcast_targets() == []
    repo.set_blocked(5, False)
    assert len(repo.broadcast_targets()) == 1
    stats = repo.user_stats()
    assert stats["total"] == 1 and stats["active"] == 1


def test_rules_acceptance_flag(repo: Repository) -> None:
    repo.upsert_user(6)
    repo.set_accepted_rules(6, True)
    assert repo.get_user(6)["accepted_rules"] is True


def test_groups_toggles_and_rules(repo: Repository) -> None:
    repo.upsert_group(-100, "Test Group")
    assert repo.group_feature_enabled(-100, "anti_spam") is True
    repo.set_group_feature(-100, "anti_spam", False)
    assert repo.group_feature_enabled(-100, "anti_spam") is False
    assert repo.group_feature_enabled(-100, "welcome") is True
    repo.set_group_rules(-100, "be nice")
    assert repo.get_group_rules(-100) == "be nice"
    assert repo.list_groups()[0]["title"] == "Test Group"
    with pytest.raises(ValueError):
        repo.group_feature_enabled(-100, "nonsense")


def test_warnings_flow(repo: Repository) -> None:
    assert repo.add_warning(-1, 2, 3, "flood") == 1
    assert repo.add_warning(-1, 2, 3, "flood") == 2
    assert repo.warning_count(-1, 2) == 2
    assert repo.recent_warnings(-1)[0]["reason"] == "flood"
    assert repo.clear_warnings(-1, 2) == 2
    assert repo.warning_count(-1, 2) == 0


def test_ticket_lifecycle(repo: Repository) -> None:
    ticket_id = repo.create_ticket(10, "help", "my problem")
    ticket = repo.get_ticket(ticket_id)
    assert ticket is not None and ticket["status"] == TICKET_OPEN
    assert len(repo.ticket_messages(ticket_id)) == 1
    repo.add_ticket_message(ticket_id, 999, "answer", from_staff=True)
    repo.set_ticket_status(ticket_id, TICKET_ANSWERED, admin_id=999, reply="answer")
    assert repo.get_ticket(ticket_id)["status"] == TICKET_ANSWERED
    assert repo.count_open_tickets(10) == 1
    repo.set_ticket_status(ticket_id, TICKET_CLOSED)
    assert repo.count_open_tickets(10) == 0
    assert repo.list_tickets(status=TICKET_CLOSED)[0]["id"] == ticket_id
    with pytest.raises(ValueError):
        repo.set_ticket_status(ticket_id, "nonsense")


def test_settings_flags_and_counters(repo: Repository) -> None:
    assert repo.get_flag("bot_enabled", True) is True
    repo.set_flag("bot_enabled", False)
    assert repo.get_flag("bot_enabled") is False
    repo.set_setting("custom", "value")
    assert repo.get_setting("custom") == "value"
    assert repo.increment_counter("hits") == 1
    assert repo.increment_counter("hits", 4) == 5
    assert repo.get_counter("hits") == 5
    assert repo.all_counters()["hits"] == 5


def test_staff_management(repo: Repository) -> None:
    assert repo.staff_ids() == set()
    assert repo.add_staff(777, actor_id=1) is True
    assert repo.add_staff(777) is False
    assert repo.staff_ids() == {777}
    assert repo.remove_staff(777) is True
    assert repo.remove_staff(777) is False


def test_rate_limit_window(repo: Repository) -> None:
    for _ in range(3):
        allowed, _retry = repo.check_rate_limit("cmd", "user", 3, 60)
        assert allowed
    allowed, retry = repo.check_rate_limit("cmd", "user", 3, 60)
    assert allowed is False and retry > 0


def test_cooldown_helpers(repo: Repository) -> None:
    assert repo.cooldown_remaining("ticket", 1, 300) == 0.0
    repo.start_cooldown("ticket", 1)
    assert repo.cooldown_remaining("ticket", 1, 300) > 0
    assert repo.cooldown_remaining("ticket", 1, -1) == 0.0


def test_audit_log(repo: Repository) -> None:
    repo.audit(1, "ban", target="2", details={"reason": "spam"})
    entry = repo.recent_audit(1)[0]
    assert entry["action"] == "ban"
    assert "spam" in str(entry["details"])


def test_database_health(repo: Repository, settings) -> None:
    health = repo.db.health()
    assert health["ok"] is True
    assert health["schema_version"] == 1
    assert health["tables"] >= 9


def test_backup_produces_a_readable_copy(repo: Repository, tmp_path: Path) -> None:
    repo.upsert_user(1)
    destination = tmp_path / "copy.db"
    repo.backup(destination)
    assert destination.exists()
    restored = Database(destination)
    assert restored.scalar("SELECT COUNT(*) FROM users") == 1
    restored.close()


def test_prune_rate_limits(repo: Repository) -> None:
    repo.check_rate_limit("x", "y", 1, 1)
    assert repo.prune_rate_limits() >= 0


def test_legacy_import(repo: Repository, legacy_file: Path) -> None:
    summary = repo.import_legacy_json(legacy_file)
    assert summary == {"users": 3, "blocked": 1, "languages": 2, "tickets": 1}
    assert repo.get_language(2) == "en"
    assert repo.is_blocked(3) is True
    assert repo.count_open_tickets() == 1
    assert repo.get_setting("legacy_total_reports") == "120"


def test_legacy_import_rejects_invalid_files(repo: Repository, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        repo.import_legacy_json(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        repo.import_legacy_json(broken)
    not_object = tmp_path / "list.json"
    not_object.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        repo.import_legacy_json(not_object)


def test_storage_error_is_raised_for_bad_sql(settings) -> None:
    database = Database(settings.db_file)
    database.migrate()
    with pytest.raises(StorageError):
        database.execute("SELECT * FROM missing_table")
    database.close()


def test_executemany_and_scalar(settings) -> None:
    database = Database(settings.db_file)
    database.migrate()
    database.executemany(
        "INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)", [("a", "1", "now"), ("b", "2", "now")]
    )
    assert database.scalar("SELECT COUNT(*) FROM settings") == 2
    database.close()
