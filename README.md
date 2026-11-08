# 🦜 TuangNee (เจ้านกขุนทองทวงหนี้) — LINE Monthly Payment Tracker Bot

A LINE Messaging API bot that tracks the latest paid month (`YYYY-MM`) for every member in a LINE group, splits the monthly cost (`TOTAL_COST`) equally among members, calculates overdue balances in Baht, and automatically sends a monthly payment summary to the group.

Can be run **100% Free & 24/7 on Google Apps Script + Google Sheets** (no server or PC required) or locally using **Python (FastAPI + SQLite)**.

---

## ✨ Features

- **Per-Member Paid Month Tracking**: Tracks each member's `paid_until` (`YYYY-MM`), supporting both Christian Era (`2026-11`) and Buddhist Era (`2569-11`).
- **Automatic Cost Splitting & Overdue Calculation**: Splits `TOTAL_COST` equally among all group members and calculates exact overdue amounts (`per_person × overdue_months`).
- **Bank Account Display (`!bank`)**: Displays your bank account / payment details directly inside the status summary.
- **Automatic Monthly Notification + `!demo` Preview**: Pushes the monthly status report (with randomized "เจ้านกขุนทองทวงหนี้" quotes) on your scheduled day and hour every month.

---

## 💬 Supported Chat Commands (Thai & English)

| Command | Description |
| :--- | :--- |
| `!status` / `!สรุป` | Show everyone's current payment status, cost split per person, and bank account |
| `!demo` / `!ตัวอย่าง` | Preview the monthly notification message with a random TuangNee quote |
| `!bank <เลขบัญชี/ธนาคาร>` / `!บัญชี ...` | Set or view the bank account details shown in the summary |
| `!add <ชื่อ> [YYYY-MM] ...` | Add one or multiple members at once (e.g., `!add titan 2026-11 poom 2026-5 teno 2026-1`) |
| `!paid <ชื่อ> [+จำนวนเดือน]` | Add paid months to a member (defaults to `+1`, e.g., `!paid titan` or `!paid titan +3`) |
| `!จ่ายแล้ว [+จำนวนเดือน]` / `!me` | Record your own payment using your LINE display name |
| `!set <ชื่อ> <YYYY-MM>` | Set a member's latest paid month directly (e.g., `!set titan 2026-12`) |
| `!remove <ชื่อ>` / `!ลบ <ชื่อ>` | Remove a member from the group |
| `!reset` | Clear all members in the group |
| `!reset <YYYY-MM>` | Reset all existing members' paid month to the specified `YYYY-MM` |
| `!schedule <วันที่ 1-28> <HH:MM>` | Change the monthly auto-notification schedule (e.g., `!schedule 25 16:00`) |
| `!help` / `!คำสั่ง` | Show all available commands |

---

## ☁️ Option 1: Run 24/7 for Free with Google Apps Script + Google Sheets (Recommended)

Running the bot on **Google Apps Script** inside a **Google Sheet** keeps it online 24/7 on Google's servers for free—even when your PC is turned off—and lets you view or edit member data directly in the spreadsheet.

### Step 1: Create a Google Sheet & Paste the Code
1. Create a new Google Sheet at [https://sheets.new](https://sheets.new).
2. In the top menu, click **Extensions (`ส่วนขยาย`)** → **Apps Script**.
3. Delete any existing code in `Code.gs`, copy the entire contents of [`google_apps_script.js`](./google_apps_script.js), paste it into the editor, and press **Save** (`Ctrl+S`).
4. At the top of the file, make sure `LINE_CHANNEL_ACCESS_TOKEN` is set to your channel's long-lived access token from the [LINE Developers Console](https://developers.line.biz/console/).

### Step 2: Run `setup` Once to Create Sheets & Monthly Trigger
1. In the Apps Script toolbar, select **`setup`** from the function dropdown next to the **Run (▶️)** button.
2. Click **Run (▶️)**.
3. When prompted for permissions:
   - Click **Review permissions** → choose your Google account → click **Advanced (`ขั้นสูง`)** → **Go to project (unsafe)** → **Allow (`อนุญาต`)**.
4. This automatically creates 3 tabs in your Google Sheet:
   - **`Members`** — Stores `GroupID`, `Name`, `PaidUntil (YYYY-MM)`, `LineUserID`, and `UpdatedAt`.
   - **`Groups`** — Stores group schedule settings (`ScheduleDay`, `ScheduleHour`, `ScheduleMinute`, `Active`, `LastSentYM`).
   - **`Settings`** — Stores `TOTAL_COST` and `BANK_ACCOUNT` (you can edit these cells directly in the sheet at any time).
5. It also registers an hourly time-driven trigger for `checkAndSendMonthlyReports` so the bot automatically sends the monthly report on your scheduled day and hour.

### Step 3: Deploy as a Web App (Permanent Webhook URL)
1. Click **Deploy (`ทำให้ใช้งานได้`)** → **New deployment (`การทำให้ใช้งานได้รายการใหม่`)**.
2. Click the gear icon ⚙️ next to **Select type** and choose **Web app (`เว็บแอป`)**.
3. Configure the deployment:
   - **Execute as:** `Me` (`ฉัน`)
   - **Who has access:** **`Anyone` (`ทุกคน`)** *(Required so LINE can send webhook requests)*
4. Click **Deploy (`ทำให้ใช้งานได้`)** and copy the **Web app URL** (`https://script.google.com/macros/s/.../exec`).

### Step 4: Connect to LINE Developers Console
1. Open the [LINE Developers Console](https://developers.line.biz/console/) → select your **Messaging API** channel → **Messaging API** tab.
2. Paste your `https://script.google.com/macros/s/.../exec` URL into **Webhook URL** and click **Update**.
3. Toggle **Use webhook** to **Enabled**.
4. Ensure **Allow bot to join group chats** is enabled, and **Auto-response messages** are turned off.

> **ℹ️ Note on the LINE "Verify" Button (`302 Found`):**
> Google Apps Script always returns an HTTP `302 Found` redirect when serving `ContentService` responses. The "Verify" button in the LINE Console may report `302 Found`, which is completely normal for Google Apps Script—real messages in LINE chat still trigger `doPost(e)` and reply immediately.

---

## 🔄 Updating the Google Apps Script Code

### Method A: Automated CLI Push & Deploy via `clasp`
This repository is configured with [`@google/clasp`](https://github.com/google/clasp) (`.clasp.json` pointing to the `gas/` directory) so you can push and deploy updates from your terminal without changing your Webhook URL:

1. Enable the Google Apps Script API at [https://script.google.com/home/usersettings](https://script.google.com/home/usersettings).
2. Log in to `clasp`:
   ```powershell
   npx @google/clasp login
   ```
3. Copy changes from `google_apps_script.js` to `gas/Code.js`, push, and redeploy to your existing Deployment ID:
   ```powershell
   Copy-Item google_apps_script.js gas\Code.js -Force
   npx @google/clasp push --force
   npx @google/clasp deploy -i <YOUR_DEPLOYMENT_ID> -d "Update description"
   ```

### Method B: Manual Update in Browser
1. Paste the updated code into the Apps Script editor and click **Save (💾)**.
2. Click **Deploy (`ทำให้ใช้งานได้`)** → **Manage deployments (`จัดการการทำให้ใช้งานได้`)**.
3. Click the **Edit (✏️)** icon → select **Version: New version (`เวอร์ชันใหม่`)** → click **Deploy**.
   *(Updating an existing deployment keeps your `/exec` Webhook URL unchanged.)*

---

## 💻 Option 2: Local Python Server (FastAPI + SQLite)

If you prefer running the bot locally on your machine using Python and SQLite:

1. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
2. **Configure `.env`:**
   ```powershell
   Copy-Item .env.example .env
   ```
   Fill in `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`, `TOTAL_COST`, and schedule settings in `.env`.
3. **Start the FastAPI server:**
   ```powershell
   python main.py
   ```
4. **Expose port `8000` for LINE Webhooks:**
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
   Then set your LINE Webhook URL to `https://<your-tunnel-domain>/callback`.
