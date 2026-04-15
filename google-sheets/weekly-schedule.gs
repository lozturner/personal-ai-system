// ═══════════════════════════════════════════════════════════════════
// Weekly Organiser — Google Apps Script
// ═══════════════════════════════════════════════════════════════════
// HOW TO USE:
//   1. Open your "Loz Multiverse" spreadsheet
//   2. Extensions → Apps Script
//   3. Delete any existing code, paste this entire file
//   4. Click ▶ Run → select "createWeeklySchedule"
//   5. Authorise when prompted → a new "Weekly Schedule" sheet appears
// ═══════════════════════════════════════════════════════════════════

function createWeeklySchedule() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Delete existing sheet if re-running
  let sheet = ss.getSheetByName('Weekly Schedule');
  if (sheet) ss.deleteSheet(sheet);
  sheet = ss.insertSheet('Weekly Schedule');

  const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const activities = buildSchedule();

  // ── Header row ──
  const headerRow = ['Time'];
  const monday = getMonday_();
  for (let d = 0; d < 7; d++) {
    const date = new Date(monday);
    date.setDate(date.getDate() + d);
    headerRow.push(DAYS[d] + ' ' + Utilities.formatDate(date, Session.getScriptTimeZone(), 'd/M'));
  }
  sheet.getRange(1, 1, 1, 8).setValues([headerRow]);

  // ── Data rows (30-min slots from 06:00–22:30) ──
  const rows = [];
  for (let slot = 0; slot < activities.length; slot++) {
    const h = 6 + slot * 0.5;
    const hh = Math.floor(h);
    const mm = (h % 1) * 60;
    const timeStr = pad_(hh) + ':' + pad_(mm);
    const row = [timeStr];
    for (let d = 0; d < 7; d++) {
      row.push(activities[slot][d].label);
    }
    rows.push(row);
  }
  sheet.getRange(2, 1, rows.length, 8).setValues(rows);

  // ── Colour coding ──
  for (let slot = 0; slot < activities.length; slot++) {
    for (let d = 0; d < 7; d++) {
      const cell = sheet.getRange(slot + 2, d + 2);
      cell.setBackground(activities[slot][d].bg);
      cell.setFontColor(activities[slot][d].fg);
    }
  }

  // ── Formatting ──
  sheet.getRange(1, 1, 1, 8)
    .setBackground('#1a1a2e')
    .setFontColor('#a0a0ff')
    .setFontWeight('bold');
  sheet.getRange(2, 1, rows.length, 1)
    .setBackground('#141414')
    .setFontColor('#888888')
    .setHorizontalAlignment('center');
  sheet.setColumnWidth(1, 60);
  for (let c = 2; c <= 8; c++) sheet.setColumnWidth(c, 130);
  sheet.getRange(1, 1, rows.length + 1, 8).setBorder(true,true,true,true,true,true,'#333333',SpreadsheetApp.BorderStyle.SOLID);

  // ── Stats section ──
  const statsStartRow = rows.length + 4;
  writeStats_(sheet, statsStartRow, activities);

  // ── Formulas reference ──
  const formulaStartRow = statsStartRow + 10;
  writeFormulas_(sheet, formulaStartRow);

  SpreadsheetApp.getActiveSpreadsheet().toast('Weekly schedule created!', 'Done', 5);
}

// ═══════════════════════════════════════════════════════════════════
// CORE MATH
// ═══════════════════════════════════════════════════════════════════

function alertness_(hour) {
  var base = Math.sin(Math.PI * (hour - 6) / 8);
  var dip = 1 - 0.3 * Math.max(0, Math.sin(Math.PI * (hour - 13) / 2));
  return Math.max(0, base * dip);
}

function energy_(hour) {
  return alertness_(hour) * (1 - 0.04 * (hour - 6));
}

function isUltradianWork_(hour) {
  var minutesSince6 = (hour - 6) * 60;
  var phase = minutesSince6 % 110;
  return phase < 90;
}

function workWeight_(dayIndex) {
  return Math.max(0.2, 1 - 0.8 * Math.max(0, (dayIndex - 4) / 2));
}

function getActivity_(dayIndex, hour) {
  var isWeekend = dayIndex >= 5;
  var a = alertness_(hour);
  var e = energy_(hour);
  var ultWork = isUltradianWork_(hour);

  if (hour < 6.5 || hour >= 22.5) return 'Sleep';
  if (hour >= 6.5 && hour < 7.5) return 'Morning Routine';

  if (isWeekend) {
    if (hour >= 7.5 && hour < 8) return 'Morning Routine';
    if (hour >= 10 && hour < 11) return 'Exercise';
    if (hour >= 12.5 && hour < 13.5) return 'Lunch';
    if (hour >= 18 && hour < 19) return 'Exercise';
    if (hour >= 21 && hour < 22.5) return 'Wind Down';
    if (a > 0.5 && hour < 12) return 'Rest / Recharge';
    return 'Free Time';
  }

  if (dayIndex === 0 && hour >= 7.5 && hour < 8.5) return 'Plan / Review';
  if (dayIndex === 4 && hour >= 16 && hour < 17) return 'Plan / Review';

  if (hour >= 8 && hour < 11.5 && a > 0.4) {
    if (!ultWork) return 'Break';
    return e > 0.3 ? 'Deep Work' : 'Admin / Email';
  }

  if (hour >= 11.5 && hour < 12.5) return 'Admin / Email';
  if (hour >= 12.5 && hour < 13.5) return 'Lunch';
  if (hour >= 13.5 && hour < 14) return 'Break';

  if (hour >= 14 && hour < 16) {
    if (!ultWork) return 'Break';
    return e > 0.15 ? 'Deep Work' : 'Creative Work';
  }

  if (hour >= 16 && hour < 17.5) return 'Creative Work';
  if (hour >= 17.5 && hour < 18.5) return 'Exercise';
  if (hour >= 18.5 && hour < 21) return 'Free Time';
  if (hour >= 21 && hour < 22.5) return 'Wind Down';

  return 'Free Time';
}

// ═══════════════════════════════════════════════════════════════════
// COLOUR MAP
// ═══════════════════════════════════════════════════════════════════

var COLOUR_MAP = {
  'Sleep':            { bg: '#2c2c4a', fg: '#8888aa' },
  'Morning Routine':  { bg: '#3d5a35', fg: '#c0e8b0' },
  'Deep Work':        { bg: '#7a2020', fg: '#ffcccc' },
  'Break':            { bg: '#3a3a3a', fg: '#aaaaaa' },
  'Admin / Email':    { bg: '#1e5a8a', fg: '#b0d8ff' },
  'Lunch':            { bg: '#8a5a1e', fg: '#ffe0b0' },
  'Creative Work':    { bg: '#5a2a7a', fg: '#e0c0ff' },
  'Exercise':         { bg: '#1e7a3a', fg: '#b0ffc0' },
  'Wind Down':        { bg: '#4a4a50', fg: '#b0b0b8' },
  'Free Time':        { bg: '#7a6a1e', fg: '#fff0b0' },
  'Plan / Review':    { bg: '#1a6a5a', fg: '#b0ffe8' },
  'Rest / Recharge':  { bg: '#1e5a7a', fg: '#b0e8ff' },
};

// ═══════════════════════════════════════════════════════════════════
// BUILD SCHEDULE
// ═══════════════════════════════════════════════════════════════════

function buildSchedule() {
  var result = [];
  for (var slot = 0; slot <= 33; slot++) { // 06:00 to 22:30
    var h = 6 + slot * 0.5;
    var dayRow = [];
    for (var d = 0; d < 7; d++) {
      var label = getActivity_(d, h);
      var colors = COLOUR_MAP[label] || { bg: '#1a1a1a', fg: '#cccccc' };
      dayRow.push({ label: label, bg: colors.bg, fg: colors.fg });
    }
    result.push(dayRow);
  }
  return result;
}

// ═══════════════════════════════════════════════════════════════════
// STATS + FORMULAS SECTIONS
// ═══════════════════════════════════════════════════════════════════

function writeStats_(sheet, startRow) {
  sheet.getRange(startRow, 1).setValue('WEEKLY STATS').setFontWeight('bold').setFontColor('#ffffff');

  var schedule = buildSchedule();
  var tally = {};
  for (var s = 0; s < schedule.length; s++) {
    for (var d = 0; d < 7; d++) {
      var lbl = schedule[s][d].label;
      tally[lbl] = (tally[lbl] || 0) + 0.5;
    }
  }

  var deepH = (tally['Deep Work'] || 0);
  var creativeH = (tally['Creative Work'] || 0);
  var exerciseH = (tally['Exercise'] || 0);
  var adminH = (tally['Admin / Email'] || 0);
  var freeH = (tally['Free Time'] || 0) + (tally['Rest / Recharge'] || 0);
  var totalProd = deepH + creativeH + adminH;
  var ratio = Math.round(totalProd / (7 * 16) * 100);

  var stats = [
    ['Deep Work',    deepH + 'h'],
    ['Creative',     creativeH + 'h'],
    ['Exercise',     exerciseH + 'h'],
    ['Admin',        adminH + 'h'],
    ['Free / Rest',  freeH + 'h'],
    ['Work Ratio',   ratio + '%'],
  ];
  sheet.getRange(startRow + 1, 1, stats.length, 2).setValues(stats);
  sheet.getRange(startRow + 1, 1, stats.length, 1).setFontColor('#888888');
  sheet.getRange(startRow + 1, 2, stats.length, 1).setFontWeight('bold').setFontColor('#cccccc');
}

function writeFormulas_(sheet, startRow) {
  sheet.getRange(startRow, 1).setValue('FORMULAS').setFontWeight('bold').setFontColor('#ffffff');
  var formulas = [
    ['Circadian Alertness', 'A(h) = sin(π·(h−6)/8) × (1 − 0.3·max(0, sin(π·(h−13)/2)))'],
    ['Energy Curve',        'E(h) = A(h) × (1 − 0.04·(h−6))'],
    ['Ultradian Cycle',     'phase = (min_since_06:00) mod 110 → work if <90, break if ≥90'],
    ['Weekend Weight',      'W(d) = max(0.2, 1 − 0.8·max(0, (d−4)/2))'],
    ['Deep Work Trigger',   'A(h) > 0.4 ∧ ultradian=work ∧ E(h) > 0.3'],
    ['Creative Trigger',    'h ∈ [16,17.5] — low alertness = diffuse thinking mode'],
    ['Exercise Slot',       'h ∈ [17.5,18.5] — cortisol + body temp peak'],
  ];
  sheet.getRange(startRow + 1, 1, formulas.length, 2).setValues(formulas);
  sheet.getRange(startRow + 1, 1, formulas.length, 1).setFontColor('#6aaa6a');
  sheet.getRange(startRow + 1, 2, formulas.length, 1).setFontColor('#888888').setFontSize(9);
}

// ═══════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════

function getMonday_() {
  var d = new Date();
  var day = d.getDay();
  var diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  d.setHours(0,0,0,0);
  return d;
}

function pad_(n) {
  return n < 10 ? '0' + n : '' + n;
}
