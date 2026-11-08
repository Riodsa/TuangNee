import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from zoneinfo import ZoneInfo

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    GroupSource,
    JoinEvent,
    LeaveEvent,
    MessageEvent,
    RoomSource,
    TextMessageContent,
)

from commands import build_status_message, handle_command
from database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("icloud_bot")

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Bangkok")
DEFAULT_SCHEDULE_DAY = int(os.getenv("SCHEDULE_DAY", "1"))
DEFAULT_SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "9"))
DEFAULT_SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

db = Database()
scheduler = BackgroundScheduler(timezone=ZoneInfo(TIMEZONE))

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


def send_push_message(target_id: str, text: str) -> None:
    if not CHANNEL_ACCESS_TOKEN:
        logger.warning("LINE_CHANNEL_ACCESS_TOKEN is not set; skipping push message.")
        return
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=target_id,
                    messages=[TextMessage(text=text)],
                )
            )
    except Exception as e:
        logger.error("Failed to send push message to %s: %s", target_id, e)


def send_reply_message(reply_token: str, text: str) -> None:
    if not CHANNEL_ACCESS_TOKEN:
        logger.warning("LINE_CHANNEL_ACCESS_TOKEN is not set; skipping reply message.")
        return
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text)],
                )
            )
    except Exception as e:
        logger.error("Failed to send reply message: %s", e)


def get_sender_display_name(source) -> Optional[str]:
    if not CHANNEL_ACCESS_TOKEN or not getattr(source, "user_id", None):
        return None
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            if isinstance(source, GroupSource):
                profile = line_bot_api.get_group_member_profile(
                    source.group_id, source.user_id
                )
                return profile.display_name
            elif isinstance(source, RoomSource):
                profile = line_bot_api.get_room_member_profile(
                    source.room_id, source.user_id
                )
                return profile.display_name
            else:
                profile = line_bot_api.get_profile(source.user_id)
                return profile.display_name
    except Exception as e:
        logger.debug("Could not fetch profile name: %s", e)
        return None


def send_monthly_report_job(group_id: str) -> None:
    logger.info("Sending scheduled monthly status report to group %s", group_id)
    msg = build_status_message(db, group_id, tz_name=TIMEZONE)
    send_push_message(group_id, msg)


def schedule_group_job(
    group_id: str, day: int, hour: int, minute: int
) -> None:
    job_id = f"monthly_report_{group_id}"
    trigger = CronTrigger(
        day=day,
        hour=hour,
        minute=minute,
        timezone=ZoneInfo(TIMEZONE),
    )
    scheduler.add_job(
        send_monthly_report_job,
        trigger=trigger,
        args=[group_id],
        id=job_id,
        replace_existing=True,
    )
    logger.info(
        "Scheduled monthly report for %s on day %d at %02d:%02d (%s)",
        group_id,
        day,
        hour,
        minute,
        TIMEZONE,
    )


def sync_all_group_schedules() -> None:
    for group in db.get_active_groups():
        schedule_group_job(
            group["group_id"],
            group["schedule_day"],
            group["schedule_hour"],
            group["schedule_minute"],
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    sync_all_group_schedules()
    yield
    scheduler.shutdown()


app = FastAPI(title="LINE Monthly Payment Tracker Bot", lifespan=lifespan)


def extract_target_id(source) -> str:
    if isinstance(source, GroupSource):
        return source.group_id
    if isinstance(source, RoomSource):
        return source.room_id
    return source.user_id


@handler.add(JoinEvent)
def handle_join(event: JoinEvent) -> None:
    target_id = extract_target_id(event.source)
    group = db.ensure_group(
        target_id,
        default_day=DEFAULT_SCHEDULE_DAY,
        default_hour=DEFAULT_SCHEDULE_HOUR,
        default_minute=DEFAULT_SCHEDULE_MINUTE,
    )
    schedule_group_job(
        target_id,
        group["schedule_day"],
        group["schedule_hour"],
        group["schedule_minute"],
    )
    welcome_msg = (
        "สวัสดีครับ! 🤖 บอทเช็คสถานะการจ่ายเงินรายเดือนพร้อมใช้งานแล้ว\n\n"
        "📌 คำสั่งเริ่มต้น:\n"
        "• `!add <ชื่อ> [YYYY-MM]` — เพิ่มสมาชิก\n"
        "• `!paid <ชื่อ> [+จำนวนเดือน]` — บันทึกการจ่ายเงิน\n"
        "• `!status` — ดูสรุปสถานะของทุกคน\n"
        "• `!help` — ดูคำสั่งทั้งหมด\n\n"
        f"⏰ บอทจะส่งสรุปสถานะอัตโนมัติทุกวันที่ {group['schedule_day']} "
        f"เวลา {group['schedule_hour']:02d}:{group['schedule_minute']:02d} น."
    )
    send_reply_message(event.reply_token, welcome_msg)


@handler.add(LeaveEvent)
def handle_leave(event: LeaveEvent) -> None:
    target_id = extract_target_id(event.source)
    db.deactivate_group(target_id)
    job_id = f"monthly_report_{target_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent) -> None:
    text: str = event.message.text
    if not text.strip().startswith(("!", "/")):
        return

    target_id = extract_target_id(event.source)
    group = db.ensure_group(
        target_id,
        default_day=DEFAULT_SCHEDULE_DAY,
        default_hour=DEFAULT_SCHEDULE_HOUR,
        default_minute=DEFAULT_SCHEDULE_MINUTE,
    )
    job_id = f"monthly_report_{target_id}"
    if not scheduler.get_job(job_id):
        schedule_group_job(
            target_id,
            group["schedule_day"],
            group["schedule_hour"],
            group["schedule_minute"],
        )

    # Extract @mentions if any so we can link LINE user_id to member names
    mentioned_map: dict[str, str] = {}
    mention = getattr(event.message, "mention", None)
    if mention and getattr(mention, "mentionees", None):
        for m in mention.mentionees:
            uid = getattr(m, "user_id", None)
            idx = getattr(m, "index", None)
            length = getattr(m, "length", None)
            if uid and idx is not None and length is not None:
                raw_mention = text[idx : idx + length].lstrip("@").strip()
                if raw_mention:
                    mentioned_map[raw_mention] = uid

    sender_user_id = getattr(event.source, "user_id", None)
    sender_name = None
    if text.strip().split()[0][1:].lower() in ("จ่ายแล้ว", "me"):
        sender_name = get_sender_display_name(event.source)

    reply = handle_command(
        text=text,
        group_id=target_id,
        db=db,
        sender_name=sender_name,
        sender_user_id=sender_user_id,
        mentioned_map=mentioned_map,
        on_schedule_updated=schedule_group_job,
        tz_name=TIMEZONE,
    )
    if reply:
        send_reply_message(event.reply_token, reply)


@app.post("/callback")
async def callback(
    request: Request,
    x_line_signature: Optional[str] = Header(None),
):
    if not x_line_signature:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")
    body = await request.body()
    body_text = body.decode("utf-8")
    try:
        handler.handle(body_text, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "active_groups": len(db.get_active_groups()),
        "timezone": TIMEZONE,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
