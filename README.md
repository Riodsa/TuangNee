# LINE Monthly Payment Tracker Bot (บอทเช็คสถานะการจ่ายเงินรายเดือน)

A LINE Messaging API bot built with **Python (FastAPI + line-bot-sdk v3 + APScheduler + SQLite)** that tracks the latest paid month (`YYYY-MM`) for every member in a LINE group and automatically sends a monthly status summary to the group.

---

## ✨ Features

- **Per-Member Latest Paid Month Tracking**: Tracks each member's `paid_until` (`YYYY-MM`), supporting both Christian Era (`2026-11`) and Buddhist Era (`2569-11`).
- **Automatic Monthly Status Summary**: Automatically pushes the group's payment summary on your configured day and time every month (configurable via `.env` or live in chat with `!schedule`).
- **Easy Group Chat Commands (Thai & English)**:
  - `!status` / `!สรุป` — Show everyone's current payment status (paid, paid in advance, or overdue by $N$ months).
  - `!add <ชื่อ> [YYYY-MM]` / `!เพิ่ม <ชื่อ> [YYYY-MM]` — Add a member to the group tracker.
  - `!paid <ชื่อ> [+จำนวนเดือน]` / `!จ่าย <ชื่อ> [+จำนวนเดือน]` — Increment a member's paid month (default `+1`).
  - `!จ่ายแล้ว [+จำนวนเดือน]` / `!me [+จำนวนเดือน]` — Record your own payment using your LINE display name.
  - `!set <ชื่อ> <YYYY-MM>` / `!ตั้งค่า <ชื่อ> <YYYY-MM>` — Set a member's latest paid month directly.
  - `!remove <ชื่อ>` / `!ลบ <ชื่อ>` — Remove a member from the group.
  - `!schedule <วันที่ 1-28> <HH:MM>` / `!ตั้งเวลา <วันที่ 1-28> <HH:MM>` — Configure the monthly auto-summary schedule for the group.
  - `!help` / `!คำสั่ง` — Display the help message.

---

## 🚀 Setup & Installation

### 1. Install Dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your LINE Messaging API credentials from the [LINE Developers Console](https://developers.line.biz/console/):

```powershell
Copy-Item .env.example .env
```

In the LINE Developers Console:
1. Create a **Messaging API** channel.
2. Under **Messaging API** tab:
   - Enable **Allow bot to join group chats**.
   - Issue a **Channel access token (long-lived)** and set it as `LINE_CHANNEL_ACCESS_TOKEN` in `.env`.
3. Under **Basic settings** tab:
   - Copy the **Channel secret** and set it as `LINE_CHANNEL_SECRET` in `.env`.

### 3. Run the Bot Server

```powershell
python main.py
```

For local testing with LINE Webhooks, expose port `8000` using [ngrok](https://ngrok.com/) or Cloudflare Tunnel:

```powershell
ngrok http 8000
```

Then set your **Webhook URL** in the LINE Developers Console to:
```text
https://<your-ngrok-domain>/callback
```
and enable **Use webhook**.
