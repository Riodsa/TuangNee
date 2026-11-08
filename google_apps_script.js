/**
 * ============================================================================
 * LINE Monthly Payment Tracker Bot — Google Apps Script + Google Sheets (24/7)
 * ============================================================================
 *
 * วิธีตั้งค่า (Setup Guide):
 * 1. สร้างไฟล์ Google Sheet ใหม่ที่ https://sheets.new
 * 2. ไปที่เมนู Extensions (ส่วนขยาย) -> Apps Script
 * 3. ลบโค้ดเดิมทั้งหมด แล้ววางโค้ดไฟล์นี้ลงไปทั้งหมด
 * 4. แก้ไขค่า LINE_CHANNEL_ACCESS_TOKEN และ TOTAL_COST ด้านล่างนี้
 * 5. กดปุ่ม Save (💾) แล้วเลือกฟังก์ชัน `setup` จากเมนูด้านบน แล้วกด Run (▶️)
 *    (ระบบจะสร้างตาราง Members และ Groups พร้อมตั้งเวลาเช็คส่งสรุปรายเดือนอัตโนมัติ)
 * 6. กดปุ่ม Deploy (ทำให้ใช้งานได้) -> New deployment (การทำให้ใช้งานได้รายการใหม่)
 *    - Select type: Web app (เว็บแอป)
 *    - Execute as: Me (ฉัน)
 *    - Who has access: Anyone (ทุกคน)  <-- สำคัญมาก!
 * 7. คัดลอก Web app URL (ที่ลงท้ายด้วย /exec) ไปใส่ในช่อง Webhook URL ของ LINE Developers Console
 *    แล้วเปิด Use webhook ได้เลย!
 */

// ======================= 1. ตั้งค่าเริ่มต้น (CONFIG) =======================
const LINE_CHANNEL_ACCESS_TOKEN = 'oRbH+4i2FnzD+iv442axMOO6FDDS6rAY9mNT2xA/v4iAbzubCc2ELdELgxcdAV180mp5fN1SzB8YzpHQz4tfVr6bxugvLbqrA9pPNczsDM1n2PqlPS45c2fyQo3my3s2hPVzRnRatyzoy/w1M8keEAdB04t89/1O/w1cDnyilFU=';
const DEFAULT_TOTAL_COST = 99;       // ยอดรวมรายเดือน (บาท) แก้ในชีต Settings ได้ด้วย
const DEFAULT_SCHEDULE_DAY = 25;     // วันที่แจ้งเตือนเริ่มต้นของทุกเดือน (1-28)
const DEFAULT_SCHEDULE_HOUR = 16;    // เวลาแจ้งเตือนเริ่มต้น (ชั่วโมง 0-23)
const TIMEZONE = 'Asia/Bangkok';

const THAI_MONTHS_SHORT = [
  '', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
  'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'
];

// ======================= 2. ฟังก์ชันเริ่มต้น (SETUP) =======================
/**
 * รันฟังก์ชันนี้ 1 ครั้งเพื่อสร้างตารางใน Google Sheet และตั้งเวลาส่งข้อความอัตโนมัติ
 */
function setup() {
  initSheets_();
  setupHourlyTrigger_();
  Logger.log('✅ ตั้งค่าตารางและระบบแจ้งเตือนอัตโนมัติเรียบร้อยแล้ว!');
}

function initSheets_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1) ตาราง Members
  let memberSheet = ss.getSheetByName('Members');
  if (!memberSheet) {
    memberSheet = ss.insertSheet('Members');
    memberSheet.appendRow(['GroupID', 'Name', 'PaidUntil (YYYY-MM)', 'LineUserID', 'UpdatedAt']);
    memberSheet.getRange('A1:E1').setFontWeight('bold').setBackground('#d9ead3');
  }

  // 2) ตาราง Groups
  let groupSheet = ss.getSheetByName('Groups');
  if (!groupSheet) {
    groupSheet = ss.insertSheet('Groups');
    groupSheet.appendRow(['GroupID', 'ScheduleDay', 'ScheduleHour', 'ScheduleMinute', 'Active', 'LastSentYM']);
    groupSheet.getRange('A1:F1').setFontWeight('bold').setBackground('#cfe2f3');
  }

  // 3) ตาราง Settings (แก้ไข TOTAL_COST ในชีตได้ตลอดเวลา)
  let settingSheet = ss.getSheetByName('Settings');
  if (!settingSheet) {
    settingSheet = ss.insertSheet('Settings');
    settingSheet.appendRow(['Key', 'Value', 'Description']);
    settingSheet.appendRow(['TOTAL_COST', DEFAULT_TOTAL_COST, 'ยอดรวมรายเดือน (บาท) หารเท่ากันทุกคนในกลุ่ม']);
    settingSheet.getRange('A1:C1').setFontWeight('bold').setBackground('#fff2cc');
  }
}

function setupHourlyTrigger_() {
  const triggers = ScriptApp.getProjectTriggers();
  for (const t of triggers) {
    if (t.getHandlerFunction() === 'checkAndSendMonthlyReports') {
      ScriptApp.deleteTrigger(t);
    }
  }
  ScriptApp.newTrigger('checkAndSendMonthlyReports')
    .timeBased()
    .everyHours(1)
    .create();
}

// ======================= 3. WEBHOOK HANDLER (LINE) =======================
function doGet(e) {
  return ContentService.createTextOutput(
    JSON.stringify({ status: 'ok', message: 'LINE Monthly Payment Tracker Bot is running 24/7 on Google Apps Script!' })
  ).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  initSheets_();
  if (!e || !e.postData || !e.postData.contents) {
    return ContentService.createTextOutput(JSON.stringify({ status: 'ok' })).setMimeType(ContentService.MimeType.JSON);
  }

  const body = JSON.parse(e.postData.contents);
  const events = body.events || [];

  for (const event of events) {
    const targetId = extractTargetId_(event.source);
    if (!targetId) continue;

    if (event.type === 'join') {
      const group = ensureGroup_(targetId);
      const welcomeMsg =
        'สวัสดีครับ! 🤖 บอทเช็คสถานะการจ่ายเงินรายเดือน (Google Sheets 24/7) พร้อมใช้งานแล้ว\n\n' +
        '📌 คำสั่งเริ่มต้น:\n' +
        '• `!add <ชื่อ> [YYYY-MM]` — เพิ่มสมาชิก (เพิ่มหลายคนพร้อมกันได้)\n' +
        '• `!paid <ชื่อ> [+จำนวนเดือน]` — บันทึกการจ่ายเงิน\n' +
        '• `!status` — ดูสรุปสถานะของทุกคน\n' +
        '• `!help` — ดูคำสั่งทั้งหมด\n\n' +
        `⏰ บอทจะส่งสรุปสถานะอัตโนมัติทุกวันที่ ${group.scheduleDay} เวลา ${pad2_(group.scheduleHour)}:00 น.`;
      sendReplyMessage_(event.replyToken, welcomeMsg);
    } else if (event.type === 'leave') {
      deactivateGroup_(targetId);
    } else if (event.type === 'message' && event.message.type === 'text') {
      const text = (event.message.text || '').trim();
      if (!text.startsWith('!') && !text.startsWith('/')) continue;

      ensureGroup_(targetId);
      const senderUserId = event.source.userId || '';
      let senderName = '';
      const cmdWord = text.split(/\s+/)[0].substring(1).toLowerCase();
      if (cmdWord === 'จ่ายแล้ว' || cmdWord === 'me') {
        senderName = getSenderDisplayName_(event.source) || '';
      }

      const reply = handleCommand_(text, targetId, senderName, senderUserId);
      if (reply) {
        sendReplyMessage_(event.replyToken, reply);
      }
    }
  }

  return ContentService.createTextOutput(JSON.stringify({ status: 'ok' })).setMimeType(ContentService.MimeType.JSON);
}

// ======================= 4. ระบบประมวลผลคำสั่ง (COMMANDS) =======================
const HELP_TEXT = `🤖 คำสั่งจัดการสถานะการจ่ายเงินรายเดือน:

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
  ตัวอย่าง: !schedule 25 16:00`;

function handleCommand_(text, groupId, senderName, senderUserId) {
  const parts = text.trim().split(/\s+/);
  const cmd = parts[0].substring(1).toLowerCase();
  const args = parts.slice(1);

  if (['help', 'คำสั่ง', 'วิธีใช้'].includes(cmd)) {
    return HELP_TEXT;
  }

  if (['status', 'สรุป', 'เช็ค', 'list'].includes(cmd)) {
    return buildStatusMessage_(groupId);
  }

  if (['add', 'เพิ่ม'].includes(cmd)) {
    if (args.length === 0) {
      return '⚠️ กรุณาระบุชื่อสมาชิก เช่น:\n• `!add titan 2026-11`\n• `!add titan 2026-11 poom 2026-5 teno 2026-1`';
    }
    const defaultYm = getCurrentYearMonth_();
    const entries = [];
    let pendingNames = [];

    for (const tok of args) {
      if (isYmToken_(tok)) {
        if (pendingNames.length === 0) {
          return `⚠️ พบเดือน \`${tok}\` โดยไม่มีชื่อสมาชิกข้างหน้า`;
        }
        for (const n of pendingNames) {
          entries.push([n, tok]);
        }
        pendingNames = [];
      } else {
        for (const sub of tok.split(',')) {
          const clean = sub.trim().replace(/^@+/, '');
          if (clean) pendingNames.push(clean);
        }
      }
    }
    for (const n of pendingNames) {
      entries.push([n, defaultYm]);
    }
    if (entries.length === 0) {
      return '⚠️ กรุณาระบุชื่อสมาชิก';
    }

    try {
      const addedLines = [];
      for (const [nameArg, ymArg] of entries) {
        const member = setMemberPaidUntil_(groupId, nameArg, ymArg, '');
        addedLines.push(`• **${member.name}** — จ่ายถึง: ${formatThaiYearMonth_(member.paidUntil)}`);
      }
      if (addedLines.length === 1) {
        return `✅ บันทึกสมาชิกเรียบร้อยแล้ว\n${addedLines[0]}`;
      }
      return `✅ บันทึกสมาชิก ${addedLines.length} คน เรียบร้อยแล้ว:\n` + addedLines.join('\n');
    } catch (err) {
      return `⚠️ ${err.message}`;
    }
  }

  if (['set', 'ตั้งค่า'].includes(cmd)) {
    if (args.length < 2) {
      return '⚠️ รูปแบบคำสั่ง: `!set <ชื่อ> <YYYY-MM>` เช่น `!set นัท 2026-12`';
    }
    const ymArg = args[args.length - 1];
    const nameArg = args.slice(0, -1).join(' ').replace(/^@+/, '').trim();
    if (!nameArg) return '⚠️ กรุณาระบุชื่อสมาชิก';
    try {
      const member = setMemberPaidUntil_(groupId, nameArg, ymArg, '');
      return `✅ อัปเดตสถานะของ **${member.name}** เรียบร้อยแล้ว\nเดือนล่าสุดที่จ่าย: ${formatThaiYearMonth_(member.paidUntil)}`;
    } catch (err) {
      return `⚠️ ${err.message}`;
    }
  }

  if (['paid', 'จ่าย'].includes(cmd)) {
    if (args.length === 0) {
      return '⚠️ รูปแบบคำสั่ง: `!paid <ชื่อ> [+จำนวนเดือน]` เช่น `!paid นัท` หรือ `!paid นัท +2`';
    }
    let months = 1;
    let nameArg = '';
    const lastArg = args[args.length - 1];
    if (args.length >= 2 && (/^[+-]?\d+$/.test(lastArg))) {
      months = parseInt(lastArg, 10);
      nameArg = args.slice(0, -1).join(' ').replace(/^@+/, '').trim();
    } else {
      nameArg = args.join(' ').replace(/^@+/, '').trim();
    }
    if (!nameArg) return '⚠️ กรุณาระบุชื่อสมาชิก';

    const member = addMemberPaidMonths_(groupId, nameArg, months, '');
    const sign = months >= 0 ? `+${months}` : `${months}`;
    return `💸 บันทึกการจ่ายเงินของ **${member.name}** (${sign} เดือน)\nจ่ายถึงเดือน: ${formatThaiYearMonth_(member.paidUntil)}`;
  }

  if (['จ่ายแล้ว', 'me'].includes(cmd)) {
    let months = 1;
    if (args.length > 0) {
      if (!/^[+-]?\d+$/.test(args[0])) {
        return '⚠️ รูปแบบคำสั่ง: `!จ่ายแล้ว` หรือ `!จ่ายแล้ว +2`';
      }
      months = parseInt(args[0], 10);
    }
    let targetName = '';
    if (senderUserId) {
      const existing = getMemberByUserId_(groupId, senderUserId);
      if (existing) targetName = existing.name;
    }
    if (!targetName) targetName = senderName;
    if (!targetName) {
      return '⚠️ ไม่สามารถดึงชื่อจากโปรไฟล์ของคุณได้ กรุณาใช้ `!paid <ชื่อ>` แทน';
    }
    const member = addMemberPaidMonths_(groupId, targetName, months, senderUserId);
    const sign = months >= 0 ? `+${months}` : `${months}`;
    return `💸 บันทึกการจ่ายเงินของ **${member.name}** (${sign} เดือน)\nจ่ายถึงเดือน: ${formatThaiYearMonth_(member.paidUntil)}`;
  }

  if (['remove', 'rm', 'del', 'ลบ'].includes(cmd)) {
    if (args.length === 0) {
      return '⚠️ กรุณาระบุชื่อสมาชิกที่ต้องการลบ เช่น `!remove นัท`';
    }
    const nameArg = args.join(' ').replace(/^@+/, '').trim();
    const removed = removeMember_(groupId, nameArg);
    if (removed) {
      return `🗑️ ลบ **${nameArg}** ออกจากรายการเรียบร้อยแล้ว`;
    }
    return `⚠️ ไม่พบชื่อ **${nameArg}** ในกลุ่มนี้`;
  }

  if (['reset', 'รีเซ็ต', 'ล้าง'].includes(cmd)) {
    if (args.length === 0) {
      const count = clearMembers_(groupId);
      if (count === 0) return 'ℹ️ ไม่มีรายชื่อสมาชิกในกลุ่มให้ลบ';
      return `🔄 ล้างรายชื่อสมาชิกทั้งหมด (${count} คน) เรียบร้อยแล้ว`;
    }
    try {
      const normalizedYm = parseYearMonth_(args[0]);
      const count = resetAllMembersPaidUntil_(groupId, normalizedYm);
      if (count === 0) return '⚠️ ยังไม่มีสมาชิกในกลุ่มนี้ให้รีเซ็ตเดือน';
      return `🔄 รีเซ็ตเดือนที่จ่ายของสมาชิกทั้งหมด (${count} คน) เป็น **${formatThaiYearMonth_(normalizedYm)}** เรียบร้อยแล้ว`;
    } catch (err) {
      return `⚠️ ${err.message}`;
    }
  }

  if (['schedule', 'ตั้งเวลา'].includes(cmd)) {
    if (args.length === 0) {
      const group = ensureGroup_(groupId);
      return `⏰ เวลาแจ้งเตือนปัจจุบัน: ทุกวันที่ ${group.scheduleDay} เวลา ${pad2_(group.scheduleHour)}:${pad2_(group.scheduleMinute)} น.\nหากต้องการเปลี่ยน ใช้คำสั่ง: \`!schedule <วันที่ 1-28> <HH:MM>\` เช่น \`!schedule 25 16:00\``;
    }
    if (args.length !== 2) {
      return '⚠️ รูปแบบคำสั่ง: `!schedule <วันที่ 1-28> <HH:MM>` เช่น `!schedule 25 16:00`';
    }
    const day = parseInt(args[0], 10);
    if (isNaN(day) || day < 1 || day > 28) {
      return '⚠️ วันที่ต้องอยู่ระหว่าง 1 ถึง 28 เพื่อให้ส่งได้ครบทุกเดือน';
    }
    const timeParts = args[1].split(':');
    if (timeParts.length !== 2) {
      return '⚠️ รูปแบบไม่ถูกต้อง ตัวอย่าง: `!schedule 25 16:00`';
    }
    const hour = parseInt(timeParts[0], 10);
    const minute = parseInt(timeParts[1], 10);
    if (isNaN(hour) || isNaN(minute) || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
      return '⚠️ เวลาต้องอยู่ในรูปแบบ 00:00 ถึง 23:59';
    }
    updateGroupSchedule_(groupId, day, hour, minute);
    return `✅ ตั้งเวลาส่งสรุปรายเดือนอัตโนมัติเป็น: ทุกวันที่ **${day}** เวลา **${pad2_(hour)}:${pad2_(minute)} น.**`;
  }

  return null;
}

// ======================= 5. สร้างข้อความสรุปสถานะ (STATUS) =======================
function buildStatusMessage_(groupId) {
  const ym = getCurrentYearMonth_();
  const members = listMembers_(groupId);
  const group = ensureGroup_(groupId);
  const cost = getTotalCost_();

  let header = `📊 สรุปสถานะการจ่ายเงินประจำเดือน ${formatThaiYearMonth_(ym)}\n`;
  if (cost > 0 && members.length > 0) {
    const perPerson = cost / members.length;
    header += `💰 ยอดรวม: ${formatAmount_(cost)} บาท/เดือน (คนละ ${formatAmount_(perPerson)} บาท)\n`;
  } else if (cost > 0) {
    header += `💰 ยอดรวม: ${formatAmount_(cost)} บาท/เดือน\n`;
  }
  header += '━━━━━━━━━━━━━━━━━━\n';

  if (members.length === 0) {
    return (
      header +
      'ยังไม่มีรายชื่อสมาชิกในกลุ่มนี้\n' +
      'พิมพ์ !add <ชื่อ> [YYYY-MM] เพื่อเพิ่มสมาชิก หรือ !help เพื่อดูคำสั่งทั้งหมด'
    );
  }

  const perPerson = cost > 0 ? cost / members.length : 0;
  const lines = [];
  let paidCount = 0;
  let unpaidCount = 0;

  members.forEach((m, idx) => {
    const diff = diffMonths_(m.paidUntil, ym);
    const thaiPaid = formatThaiYearMonth_(m.paidUntil);
    let statusIcon = '✅';
    let detail = '';

    if (diff > 0) {
      statusIcon = '✅';
      detail = `จ่ายล่วงหน้า ${diff} เดือน`;
      paidCount++;
    } else if (diff === 0) {
      statusIcon = '✅';
      detail = 'จ่ายแล้ว';
      paidCount++;
    } else {
      statusIcon = '❌';
      const overdueMonths = Math.abs(diff);
      if (perPerson > 0) {
        const overdueAmt = perPerson * overdueMonths;
        detail = `ค้างชำระ ${overdueMonths} เดือน = ${formatAmount_(overdueAmt)} บาท`;
      } else {
        detail = `ค้างชำระ ${overdueMonths} เดือน`;
      }
      unpaidCount++;
    }

    lines.push(`${idx + 1}. ${statusIcon} ${m.name}\n   └ จ่ายถึง: ${thaiPaid} (${detail})`);
  });

  let footer = `\n━━━━━━━━━━━━━━━━━━\n✅ จ่ายแล้ว: ${paidCount} คน | ❌ ค้างชำระ: ${unpaidCount} คน`;
  if (group) {
    footer += `\n⏰ แจ้งเตือนอัตโนมัติ: ทุกวันที่ ${group.scheduleDay} เวลา ${pad2_(group.scheduleHour)}:${pad2_(group.scheduleMinute)} น.`;
  }

  return header + lines.join('\n') + footer;
}

// ======================= 6. ระบบแจ้งเตือนรายเดือนอัตโนมัติ (CRON) =======================
function checkAndSendMonthlyReports() {
  initSheets_();
  const now = new Date();
  const currentYm = Utilities.formatDate(now, TIMEZONE, 'yyyy-MM');
  const currentDay = parseInt(Utilities.formatDate(now, TIMEZONE, 'd'), 10);
  const currentHour = parseInt(Utilities.formatDate(now, TIMEZONE, 'H'), 10);

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Groups');
  const data = sheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) {
    const [groupId, scheduleDay, scheduleHour, scheduleMinute, active, lastSentYm] = data[i];
    if (!groupId || Number(active) !== 1) continue;

    if (
      currentDay === Number(scheduleDay) &&
      currentHour >= Number(scheduleHour) &&
      String(lastSentYm) !== currentYm
    ) {
      const msg = buildStatusMessage_(String(groupId));
      sendPushMessage_(String(groupId), msg);
      sheet.getRange(i + 1, 6).setValue(currentYm);
    }
  }
}

// ======================= 7. ฟังก์ชันฐานข้อมูล GOOGLE SHEETS =======================
function getTotalCost_() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Settings');
  if (!sheet) return DEFAULT_TOTAL_COST;
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === 'TOTAL_COST') {
      const val = parseFloat(data[i][1]);
      return isNaN(val) ? DEFAULT_TOTAL_COST : val;
    }
  }
  return DEFAULT_TOTAL_COST;
}

function ensureGroup_(groupId) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Groups');
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(groupId)) {
      if (Number(data[i][4]) === 0) {
        sheet.getRange(i + 1, 5).setValue(1);
      }
      return {
        groupId: String(data[i][0]),
        scheduleDay: Number(data[i][1]),
        scheduleHour: Number(data[i][2]),
        scheduleMinute: Number(data[i][3]),
        active: 1,
        lastSentYm: String(data[i][5] || '')
      };
    }
  }
  sheet.appendRow([groupId, DEFAULT_SCHEDULE_DAY, DEFAULT_SCHEDULE_HOUR, 0, 1, '']);
  return {
    groupId: groupId,
    scheduleDay: DEFAULT_SCHEDULE_DAY,
    scheduleHour: DEFAULT_SCHEDULE_HOUR,
    scheduleMinute: 0,
    active: 1,
    lastSentYm: ''
  };
}

function deactivateGroup_(groupId) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Groups');
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(groupId)) {
      sheet.getRange(i + 1, 5).setValue(0);
      return;
    }
  }
}

function updateGroupSchedule_(groupId, day, hour, minute) {
  ensureGroup_(groupId);
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Groups');
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(groupId)) {
      sheet.getRange(i + 1, 2, 1, 3).setValues([[day, hour, minute]]);
      return;
    }
  }
}

function listMembers_(groupId) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Members');
  const data = sheet.getDataRange().getValues();
  const result = [];
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]) === String(groupId)) {
      result.push({
        rowIndex: i + 1,
        groupId: String(data[i][0]),
        name: String(data[i][1]),
        paidUntil: formatCellYm_(data[i][2]),
        lineUserId: String(data[i][3] || '')
      });
    }
  }
  return result;
}

function getMemberByUserId_(groupId, lineUserId) {
  const members = listMembers_(groupId);
  return members.find(m => m.lineUserId && m.lineUserId === lineUserId) || null;
}

function setMemberPaidUntil_(groupId, name, paidUntil, lineUserId) {
  ensureGroup_(groupId);
  const normalizedYm = parseYearMonth_(paidUntil);
  const cleanName = name.trim().replace(/^@+/, '');
  const now = new Date().toISOString();

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Members');
  const members = listMembers_(groupId);
  const existing = members.find(m => m.name.toLowerCase() === cleanName.toLowerCase());

  if (existing) {
    const uid = lineUserId || existing.lineUserId;
    sheet.getRange(existing.rowIndex, 3, 1, 3).setValues([[`'${normalizedYm}`, uid, now]]);
    return { name: existing.name, paidUntil: normalizedYm, lineUserId: uid };
  } else {
    sheet.appendRow([groupId, cleanName, `'${normalizedYm}`, lineUserId || '', now]);
    return { name: cleanName, paidUntil: normalizedYm, lineUserId: lineUserId || '' };
  }
}

function addMemberPaidMonths_(groupId, name, months, lineUserId) {
  const cleanName = name.trim().replace(/^@+/, '');
  const members = listMembers_(groupId);
  const existing = members.find(m => m.name.toLowerCase() === cleanName.toLowerCase());
  if (existing) {
    const newYm = addMonths_(existing.paidUntil, months);
    return setMemberPaidUntil_(groupId, existing.name, newYm, lineUserId);
  } else {
    const baseYm = getCurrentYearMonth_();
    const startYm = addMonths_(baseYm, months - 1);
    return setMemberPaidUntil_(groupId, cleanName, startYm, lineUserId);
  }
}

function removeMember_(groupId, name) {
  const cleanName = name.trim().replace(/^@+/, '');
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Members');
  const members = listMembers_(groupId);
  const existing = members.find(m => m.name.toLowerCase() === cleanName.toLowerCase());
  if (!existing) return false;
  sheet.deleteRow(existing.rowIndex);
  return true;
}

function clearMembers_(groupId) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Members');
  const data = sheet.getDataRange().getValues();
  let count = 0;
  for (let i = data.length - 1; i >= 1; i--) {
    if (String(data[i][0]) === String(groupId)) {
      sheet.deleteRow(i + 1);
      count++;
    }
  }
  return count;
}

function resetAllMembersPaidUntil_(groupId, normalizedYm) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Members');
  const members = listMembers_(groupId);
  const now = new Date().toISOString();
  for (const m of members) {
    sheet.getRange(m.rowIndex, 3).setValue(`'${normalizedYm}`);
    sheet.getRange(m.rowIndex, 5).setValue(now);
  }
  return members.length;
}

// ======================= 8. ฟังก์ชันจัดการวันที่และตัวเลข =======================
function formatCellYm_(val) {
  if (val instanceof Date) {
    return Utilities.formatDate(val, TIMEZONE, 'yyyy-MM');
  }
  return String(val).replace(/^'+/, '').trim();
}

function getCurrentYearMonth_() {
  return Utilities.formatDate(new Date(), TIMEZONE, 'yyyy-MM');
}

function isYmToken_(tok) {
  if (!tok.includes('-')) return false;
  const parts = tok.split('-');
  return parts.length === 2 && /^\d+$/.test(parts[0]) && /^\d+$/.test(parts[1]);
}

function parseYearMonth_(value) {
  const parts = String(value).trim().split('-');
  if (parts.length !== 2) {
    throw new Error('รูปแบบเดือนไม่ถูกต้อง กรุณาใช้ YYYY-MM เช่น 2026-11');
  }
  let year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  if (isNaN(year) || isNaN(month)) {
    throw new Error('รูปแบบเดือนไม่ถูกต้อง กรุณาใช้ YYYY-MM เช่น 2026-11');
  }
  if (year >= 2400) year -= 543;
  if (year < 2000 || year > 2100 || month < 1 || month > 12) {
    throw new Error('ปีหรือเดือนไม่ถูกต้อง กรุณาใช้ YYYY-MM เช่น 2026-11');
  }
  return `${year}-${pad2_(month)}`;
}

function addMonths_(ym, monthsToAdd) {
  const [y, m] = ym.split('-').map(Number);
  const total = y * 12 + (m - 1) + monthsToAdd;
  const newY = Math.floor(total / 12);
  const newM = (total % 12) + 1;
  return `${newY}-${pad2_(newM)}`;
}

function diffMonths_(paidUntil, currentYm) {
  const [y1, m1] = paidUntil.split('-').map(Number);
  const [y2, m2] = currentYm.split('-').map(Number);
  return (y1 * 12 + m1) - (y2 * 12 + m2);
}

function formatThaiYearMonth_(ym) {
  const [year, month] = ym.split('-').map(Number);
  const thaiYear = year + 543;
  return `${THAI_MONTHS_SHORT[month]} ${thaiYear} (${ym})`;
}

function formatAmount_(value) {
  if (Math.abs(value - Math.round(value)) < 1e-6) {
    return Math.round(value).toLocaleString('en-US');
  }
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pad2_(n) {
  return String(n).padStart(2, '0');
}

// ======================= 9. ฟังก์ชันเชื่อมต่อ LINE API =======================
function extractTargetId_(source) {
  if (!source) return '';
  return source.groupId || source.roomId || source.userId || '';
}

function sendReplyMessage_(replyToken, text) {
  const url = 'https://api.line.me/v2/bot/message/reply';
  UrlFetchApp.fetch(url, {
    method: 'post',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + LINE_CHANNEL_ACCESS_TOKEN
    },
    payload: JSON.stringify({
      replyToken: replyToken,
      messages: [{ type: 'text', text: text }]
    }),
    muteHttpExceptions: true
  });
}

function sendPushMessage_(to, text) {
  const url = 'https://api.line.me/v2/bot/message/push';
  UrlFetchApp.fetch(url, {
    method: 'post',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + LINE_CHANNEL_ACCESS_TOKEN
    },
    payload: JSON.stringify({
      to: to,
      messages: [{ type: 'text', text: text }]
    }),
    muteHttpExceptions: true
  });
}

function getSenderDisplayName_(source) {
  if (!source || !source.userId) return '';
  let url = `https://api.line.me/v2/bot/profile/${source.userId}`;
  if (source.groupId) {
    url = `https://api.line.me/v2/bot/group/${source.groupId}/member/${source.userId}`;
  } else if (source.roomId) {
    url = `https://api.line.me/v2/bot/room/${source.roomId}/member/${source.userId}`;
  }
  try {
    const resp = UrlFetchApp.fetch(url, {
      method: 'get',
      headers: { 'Authorization': 'Bearer ' + LINE_CHANNEL_ACCESS_TOKEN },
      muteHttpExceptions: true
    });
    if (resp.getResponseCode() === 200) {
      const data = JSON.parse(resp.getContentText());
      return data.displayName || '';
    }
  } catch (e) {}
  return '';
}
