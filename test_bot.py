from commands import build_status_message, handle_command
from database import Database, add_months, diff_months, parse_year_month


def test_year_month_helpers():
    assert parse_year_month("2026-11") == "2026-11"
    assert parse_year_month("2569-11") == "2026-11"
    assert add_months("2026-11", 1) == "2026-12"
    assert add_months("2026-11", 2) == "2027-01"
    assert add_months("2026-01", -1) == "2025-12"
    assert diff_months("2026-11", "2026-11") == 0
    assert diff_months("2026-12", "2026-11") == 1
    assert diff_months("2026-09", "2026-11") == -2


def test_commands_and_status(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(str(db_file))
    group_id = "G12345"

    # Add members
    reply1 = handle_command("!add นัท 2026-11", group_id, db)
    assert reply1 is not None and "นัท" in reply1

    reply2 = handle_command("!add บีม 2026-09", group_id, db)
    assert reply2 is not None and "บีม" in reply2

    # Increment payment (+2 months from 2026-11 -> 2027-01)
    reply3 = handle_command("!paid นัท +2", group_id, db)
    assert reply3 is not None and "2027-01" in reply3

    # Self payment via !จ่ายแล้ว
    reply4 = handle_command(
        "!จ่ายแล้ว",
        group_id,
        db,
        sender_name="แพรว",
        sender_user_id="U999",
    )
    assert reply4 is not None and "แพรว" in reply4

    # Status message for 2026-11 (3 members, total_cost=99 -> 33/person)
    status = build_status_message(db, group_id, current_ym="2026-11", total_cost=99)
    assert "ยอดรวม: 99 บาท/เดือน (คนละ 33 บาท)" in status
    assert "นัท" in status and "จ่ายล่วงหน้า 2 เดือน" in status
    assert "บีม" in status and "ค้างชำระ 2 เดือน = 66 บาท" in status

    # Update schedule
    scheduled = {}

    def on_sched(gid, d, h, m):
        scheduled["args"] = (gid, d, h, m)

    reply_sched = handle_command(
        "!schedule 5 10:30", group_id, db, on_schedule_updated=on_sched
    )
    assert reply_sched is not None and "10:30" in reply_sched
    assert scheduled["args"] == (group_id, 5, 10, 30)

    # Add multiple members at once
    reply_multi = handle_command(
        "!add titan 2026-11 poom 2026-5 teno 2026-1", group_id, db
    )
    assert reply_multi is not None
    assert "บันทึกสมาชิก 3 คน" in reply_multi
    assert db.get_member(group_id, "titan")["paid_until"] == "2026-11"
    assert db.get_member(group_id, "poom")["paid_until"] == "2026-05"
    assert db.get_member(group_id, "teno")["paid_until"] == "2026-01"

    # Remove member
    reply_rm = handle_command("!remove บีม", group_id, db)
    assert reply_rm is not None and "ลบ" in reply_rm
    assert db.get_member(group_id, "บีม") is None

    # Reset all existing members' paid month to 2026-12
    reply_reset_ym = handle_command("!reset 2026-12", group_id, db)
    assert reply_reset_ym is not None and "2026-12" in reply_reset_ym
    assert db.get_member(group_id, "titan")["paid_until"] == "2026-12"

    # Reset (clear) all members in the group
    reply_reset_clear = handle_command("!reset", group_id, db)
    assert reply_reset_clear is not None and "ล้างรายชื่อสมาชิกทั้งหมด" in reply_reset_clear
    assert len(db.list_members(group_id)) == 0
