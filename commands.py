import os
from typing import Callable, Optional
from dotenv import load_dotenv
from database import (
    Database,
    diff_months,
    format_thai_year_month,
    get_current_year_month,
    parse_year_month,
)


def format_amount(value: float) -> str:
    """Format THB currency amount cleanly (omit .00 if integer, else 2 decimals)."""
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"


def get_total_cost(override_cost: Optional[float] = None) -> float:
    """Read TOTAL_COST from .env dynamically so changes to .env take effect immediately."""
    if override_cost is not None:
        return override_cost
    load_dotenv(override=True)
    raw = os.getenv("TOTAL_COST", "0").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.0


def build_status_message(
    db: Database,
    group_id: str,
    current_ym: Optional[str] = None,
    tz_name: str = "Asia/Bangkok",
    total_cost: Optional[float] = None,
) -> str:
    """Build the Thai monthly payment status summary message for a group."""
    ym = current_ym or get_current_year_month(tz_name)
    members = db.list_members(group_id)
    group = db.get_group(group_id)
    cost = get_total_cost(total_cost)

    header = f"📊 สรุปสถานะการจ่ายเงินประจำเดือน {format_thai_year_month(ym)}\n"
    if cost > 0 and members:
        per_person = cost / len(members)
        header += f"💰 ยอดรวม: {format_amount(cost)} บาท/เดือน (คนละ {format_amount(per_person)} บาท)\n"
    elif cost > 0:
        header += f"💰 ยอดรวม: {format_amount(cost)} บาท/เดือน\n"
    header += "━━━━━━━━━━━━━━━━━━\n"

    if not members:
        return (
            header
            + "ยังไม่มีรายชื่อสมาชิกในกลุ่มนี้\n"
            + "พิมพ์ !add <ชื่อ> [YYYY-MM] เพื่อเพิ่มสมาชิก หรือ !help เพื่อดูคำสั่งทั้งหมด"
        )

    per_person = (cost / len(members)) if cost > 0 else 0.0
    lines = []
    paid_count = 0
    unpaid_count = 0

    for idx, m in enumerate(members, start=1):
        paid_until = m["paid_until"]
        diff = diff_months(paid_until, ym)
        thai_paid = format_thai_year_month(paid_until)

        if diff > 0:
            status_icon = "✅"
            detail = f"จ่ายล่วงหน้า {diff} เดือน"
            paid_count += 1
        elif diff == 0:
            status_icon = "✅"
            detail = "จ่ายแล้ว"
            paid_count += 1
        else:
            status_icon = "❌"
            overdue_months = abs(diff)
            if per_person > 0:
                overdue_amt = per_person * overdue_months
                detail = f"ค้างชำระ {overdue_months} เดือน = {format_amount(overdue_amt)} บาท"
            else:
                detail = f"ค้างชำระ {overdue_months} เดือน"
            unpaid_count += 1

        lines.append(
            f"{idx}. {status_icon} {m['name']}\n"
            f"   └ จ่ายถึง: {thai_paid} ({detail})"
        )

    footer = (
        "\n━━━━━━━━━━━━━━━━━━\n"
        f"✅ จ่ายแล้ว: {paid_count} คน | ❌ ค้างชำระ: {unpaid_count} คน"
    )
    if group:
        footer += (
            f"\n⏰ แจ้งเตือนอัตโนมัติ: ทุกวันที่ {group['schedule_day']} "
            f"เวลา {group['schedule_hour']:02d}:{group['schedule_minute']:02d} น."
        )

    return header + "\n".join(lines) + footer


HELP_TEXT = """🤖 คำสั่งจัดการสถานะการจ่ายเงินรายเดือน:

1️⃣ ดูสถานะทั้งหมด
• !status หรือ !สรุป — แสดงสถานะการจ่ายเงินของทุกคนพร้อมยอดหารต่อคน

2️⃣ เพิ่ม/อัปเดตการจ่ายเงิน
• !paid <ชื่อ> [+จำนวนเดือน] — บวกเดือนที่จ่ายเพิ่ม (ค่าเริ่มต้น +1 เดือน)
  ตัวอย่าง: !paid นัท หรือ !paid นัท +3
• !จ่ายแล้ว [+จำนวนเดือน] — บันทึกว่าตัวคุณเองจ่ายแล้ว (ดึงชื่อจากโปรไฟล์ LINE)
• !set <ชื่อ> <YYYY-MM> — กำหนดเดือนล่าสุดที่จ่ายแล้วโดยตรง
  ตัวอย่าง: !set นัท 2026-12 หรือ !set นัท 2569-12

3️⃣ จัดการรายชื่อสมาชิก
• !add <ชื่อ> [YYYY-MM] [ชื่อ2 YYYY-MM ...] — เพิ่มสมาชิกใหม่พร้อมกันได้หลายคน
  ตัวอย่าง: !add titan 2026-11 poom 2026-5 teno 2026-1
• !remove <ชื่อ> หรือ !ลบ <ชื่อ> — ลบสมาชิกออกจากรายการ
• !reset — ลบรายชื่อสมาชิกทั้งหมดในกลุ่ม
• !reset <YYYY-MM> — รีเซ็ตเดือนที่จ่ายของสมาชิกทุกคนเป็นเดือนที่ระบุ

4️⃣ ตั้งค่าแจ้งเตือนรายเดือนอัตโนมัติ
• !schedule <วันที่ 1-28> <HH:MM> — ตั้งเวลาส่งสรุปอัตโนมัติทุกเดือน
  ตัวอย่าง: !schedule 1 09:00"""


def handle_command(
    text: str,
    group_id: str,
    db: Database,
    sender_name: Optional[str] = None,
    sender_user_id: Optional[str] = None,
    mentioned_map: Optional[dict[str, str]] = None,
    on_schedule_updated: Optional[Callable[[str, int, int, int], None]] = None,
    tz_name: Optional[str] = None,
) -> Optional[str]:
    """Process a chat message and return a reply string if it matches a command."""
    tz = tz_name or os.getenv("TIMEZONE", "Asia/Bangkok")
    raw = text.strip()
    if not raw.startswith(("!", "/")):
        return None

    parts = raw.split()
    cmd = parts[0][1:].lower()
    args = parts[1:]

    if cmd in ("help", "คำสั่ง", "วิธีใช้"):
        return HELP_TEXT

    if cmd in ("status", "สรุป", "เช็ค", "list"):
        return build_status_message(db, group_id, tz_name=tz)

    if cmd in ("add", "เพิ่ม"):
        if not args:
            return (
                "⚠️ กรุณาระบุชื่อสมาชิก เช่น:\n"
                "• `!add titan 2026-11`\n"
                "• `!add titan 2026-11 poom 2026-5 teno 2026-1`"
            )

        default_ym = get_current_year_month(tz)

        def is_ym_token(tok: str) -> bool:
            if "-" not in tok:
                return False
            parts_ym = tok.split("-")
            return len(parts_ym) == 2 and parts_ym[0].isdigit() and parts_ym[1].isdigit()

        entries: list[tuple[str, str]] = []
        pending_names: list[str] = []

        for tok in args:
            if is_ym_token(tok):
                if not pending_names:
                    return f"⚠️ พบเดือน `{tok}` โดยไม่มีชื่อสมาชิกข้างหน้า"
                for n in pending_names:
                    entries.append((n, tok))
                pending_names = []
            else:
                for sub in tok.split(","):
                    clean = sub.strip().lstrip("@")
                    if clean:
                        pending_names.append(clean)

        # Any trailing names without an explicit YYYY-MM get the current month
        for n in pending_names:
            entries.append((n, default_ym))

        if not entries:
            return "⚠️ กรุณาระบุชื่อสมาชิก"

        try:
            added_lines = []
            for name_arg, ym_arg in entries:
                user_id = (mentioned_map or {}).get(name_arg)
                member = db.set_member_paid_until(
                    group_id, name_arg, ym_arg, line_user_id=user_id
                )
                added_lines.append(
                    f"• **{member['name']}** — จ่ายถึง: {format_thai_year_month(member['paid_until'])}"
                )

            if len(added_lines) == 1:
                return f"✅ บันทึกสมาชิกเรียบร้อยแล้ว\n{added_lines[0]}"
            return (
                f"✅ บันทึกสมาชิก {len(added_lines)} คน เรียบร้อยแล้ว:\n"
                + "\n".join(added_lines)
            )
        except ValueError as e:
            return f"⚠️ {e}"

    if cmd in ("set", "ตั้งค่า"):
        if len(args) < 2:
            return "⚠️ รูปแบบคำสั่ง: `!set <ชื่อ> <YYYY-MM>` เช่น `!set นัท 2026-12`"
        ym_arg = args[-1]
        name_arg = " ".join(args[:-1]).lstrip("@")
        if not name_arg:
            return "⚠️ กรุณาระบุชื่อสมาชิก"
        try:
            user_id = (mentioned_map or {}).get(name_arg)
            member = db.set_member_paid_until(
                group_id, name_arg, ym_arg, line_user_id=user_id
            )
            return (
                f"✅ อัปเดตสถานะของ **{member['name']}** เรียบร้อยแล้ว\n"
                f"เดือนล่าสุดที่จ่าย: {format_thai_year_month(member['paid_until'])}"
            )
        except ValueError as e:
            return f"⚠️ {e}"

    if cmd in ("paid", "จ่าย"):
        if not args:
            return "⚠️ รูปแบบคำสั่ง: `!paid <ชื่อ> [+จำนวนเดือน]` เช่น `!paid นัท` หรือ `!paid นัท +2`"

        months = 1
        if len(args) >= 2 and (
            args[-1].startswith(("+", "-")) or args[-1].isdigit()
        ):
            try:
                months = int(args[-1])
                name_arg = " ".join(args[:-1]).lstrip("@")
            except ValueError:
                name_arg = " ".join(args).lstrip("@")
        else:
            name_arg = " ".join(args).lstrip("@")

        if not name_arg:
            return "⚠️ กรุณาระบุชื่อสมาชิก"

        user_id = (mentioned_map or {}).get(name_arg)
        current_ym = get_current_year_month(tz)
        member = db.add_member_paid_months(
            group_id,
            name_arg,
            months=months,
            current_ym=current_ym,
            line_user_id=user_id,
        )
        sign = f"+{months}" if months >= 0 else str(months)
        return (
            f"💸 บันทึกการจ่ายเงินของ **{member['name']}** ({sign} เดือน)\n"
            f"จ่ายถึงเดือน: {format_thai_year_month(member['paid_until'])}"
        )

    if cmd in ("จ่ายแล้ว", "me"):
        months = 1
        if args:
            try:
                months = int(args[0])
            except ValueError:
                return "⚠️ รูปแบบคำสั่ง: `!จ่ายแล้ว` หรือ `!จ่ายแล้ว +2`"

        target_name = None
        if sender_user_id:
            existing_by_id = db.get_member_by_user_id(group_id, sender_user_id)
            if existing_by_id:
                target_name = existing_by_id["name"]

        if not target_name:
            target_name = sender_name

        if not target_name:
            return "⚠️ ไม่สามารถดึงชื่อจากโปรไฟล์ของคุณได้ กรุณาใช้ `!paid <ชื่อ>` แทน"

        current_ym = get_current_year_month(tz)
        member = db.add_member_paid_months(
            group_id,
            target_name,
            months=months,
            current_ym=current_ym,
            line_user_id=sender_user_id,
        )
        sign = f"+{months}" if months >= 0 else str(months)
        return (
            f"💸 บันทึกการจ่ายเงินของ **{member['name']}** ({sign} เดือน)\n"
            f"จ่ายถึงเดือน: {format_thai_year_month(member['paid_until'])}"
        )

    if cmd in ("remove", "rm", "del", "ลบ"):
        if not args:
            return "⚠️ กรุณาระบุชื่อสมาชิกที่ต้องการลบ เช่น `!remove นัท`"
        name_arg = " ".join(args).lstrip("@")
        removed = db.remove_member(group_id, name_arg)
        if removed:
            return f"🗑️ ลบ **{name_arg}** ออกจากรายการเรียบร้อยแล้ว"
        return f"⚠️ ไม่พบชื่อ **{name_arg}** ในกลุ่มนี้"

    if cmd in ("reset", "รีเซ็ต", "ล้าง"):
        if not args:
            count = db.clear_members(group_id)
            if count == 0:
                return "ℹ️ ไม่มีรายชื่อสมาชิกในกลุ่มให้ลบ"
            return f"🔄 ล้างรายชื่อสมาชิกทั้งหมด ({count} คน) เรียบร้อยแล้ว"

        ym_arg = args[0]
        try:
            normalized_ym = parse_year_month(ym_arg)
            count = db.reset_all_members_paid_until(group_id, normalized_ym)
            if count == 0:
                return "⚠️ ยังไม่มีสมาชิกในกลุ่มนี้ให้รีเซ็ตเดือน"
            return (
                f"🔄 รีเซ็ตเดือนที่จ่ายของสมาชิกทั้งหมด ({count} คน) เป็น "
                f"**{format_thai_year_month(normalized_ym)}** เรียบร้อยแล้ว"
            )
        except ValueError as e:
            return f"⚠️ {e}"

    if cmd in ("schedule", "ตั้งเวลา"):
        if not args:
            group = db.ensure_group(group_id)
            return (
                f"⏰ เวลาแจ้งเตือนปัจจุบัน: ทุกวันที่ {group['schedule_day']} "
                f"เวลา {group['schedule_hour']:02d}:{group['schedule_minute']:02d} น.\n"
                f"หากต้องการเปลี่ยน ใช้คำสั่ง: `!schedule <วันที่ 1-28> <HH:MM>` เช่น `!schedule 1 09:00`"
            )
        if len(args) != 2:
            return "⚠️ รูปแบบคำสั่ง: `!schedule <วันที่ 1-28> <HH:MM>` เช่น `!schedule 1 09:00`"
        try:
            day = int(args[0])
            if not (1 <= day <= 28):
                return "⚠️ วันที่ต้องอยู่ระหว่าง 1 ถึง 28 เพื่อให้ส่งได้ครบทุกเดือน"
            time_parts = args[1].split(":")
            if len(time_parts) != 2:
                raise ValueError()
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return "⚠️ เวลาต้องอยู่ในรูปแบบ 00:00 ถึง 23:59"
        except ValueError:
            return "⚠️ รูปแบบไม่ถูกต้อง ตัวอย่าง: `!schedule 1 09:00`"

        db.update_group_schedule(group_id, day, hour, minute)
        if on_schedule_updated:
            on_schedule_updated(group_id, day, hour, minute)
        return f"✅ ตั้งเวลาส่งสรุปรายเดือนอัตโนมัติเป็น: ทุกวันที่ **{day}** เวลา **{hour:02d}:{minute:02d} น.**"

    return None
