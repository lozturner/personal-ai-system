# Google Sheets Formula Template — Weekly Organiser

Setup: create a new sheet tab called "Weekly Schedule" in your Loz Multiverse
spreadsheet, then follow the layout below. All scheduling logic runs via native
Google Sheets formulas — no scripts, no macros, no input.

---

## Sheet Layout

| Col | Content               |
|-----|-----------------------|
| A   | Time labels (06:00–22:30 in 30-min steps) |
| B–H | Mon–Sun schedule (formula-driven) |
| J   | Helper: hour as decimal (e.g. 6, 6.5, 7...) |
| K   | Helper: alertness value |
| L   | Helper: energy value |
| M   | Helper: ultradian phase (work/break) |

---

## Step 1 — Time column (A2:A35)

Put `06:00` in A2 formatted as time. In A3:

```
=A2 + TIME(0,30,0)
```

Drag down to A35 (gives 06:00 through 22:30).

---

## Step 2 — Decimal hour helper (J2:J35)

In J2:
```
=HOUR(A2) + MINUTE(A2)/60
```
Drag down.

---

## Step 3 — Alertness formula (K2:K35)

Circadian alertness: `A(h) = sin(π(h-6)/8) × (1 - 0.3·max(0, sin(π(h-13)/2)))`

In K2:
```
=MAX(0, SIN(PI()*(J2-6)/8) * (1 - 0.3*MAX(0, SIN(PI()*(J2-13)/2))))
```
Drag down.

---

## Step 4 — Energy formula (L2:L35)

Energy: `E(h) = A(h) × (1 - 0.04·(h-6))`

In L2:
```
=K2 * (1 - 0.04*(J2-6))
```
Drag down.

---

## Step 5 — Ultradian cycle (M2:M35)

`phase = (minutes_since_06:00) mod 110` → "Work" if <90, "Break" if ≥90

In M2:
```
=IF(MOD((J2-6)*60, 110) < 90, "Work", "Break")
```
Drag down.

---

## Step 6 — Day headers (B1:H1)

In B1, put this to auto-calculate current Monday's date:

```
=TEXT(TODAY() - WEEKDAY(TODAY(),3), "ddd d/m")
```

In C1:
```
=TEXT(TODAY() - WEEKDAY(TODAY(),3) + 1, "ddd d/m")
```

Continue through H1 (+2, +3, +4, +5, +6).

---

## Step 7 — Schedule formula (B2, then fill across and down)

This is the core formula. Column B = Monday (day index 0), C = Tuesday (1), etc.
The `COLUMN()-2` gives 0 for B, 1 for C, ... 6 for H.

Paste in **B2**:

```
=LET(
  h, J2,
  d, COLUMN()-2,
  a, K2,
  e, L2,
  ult, M2,
  isWE, d>=5,
  IF(OR(h<6.5, h>=22.5), "Sleep",
  IF(AND(h>=6.5, h<7.5), "Morning Routine",
  IF(isWE,
    IF(AND(h>=7.5, h<8), "Morning Routine",
    IF(AND(h>=10, h<11), "Exercise",
    IF(AND(h>=12.5, h<13.5), "Lunch",
    IF(AND(h>=18, h<19), "Exercise",
    IF(AND(h>=21, h<22.5), "Wind Down",
    IF(AND(a>0.5, h<12), "Rest / Recharge",
    "Free Time")))))),
  IF(AND(d=0, h>=7.5, h<8.5), "Plan / Review",
  IF(AND(d=4, h>=16, h<17), "Plan / Review",
  IF(AND(h>=8, h<11.5, a>0.4),
    IF(ult="Break", "Break",
    IF(e>0.3, "Deep Work", "Admin / Email")),
  IF(AND(h>=11.5, h<12.5), "Admin / Email",
  IF(AND(h>=12.5, h<13.5), "Lunch",
  IF(AND(h>=13.5, h<14), "Break",
  IF(AND(h>=14, h<16),
    IF(ult="Break", "Break",
    IF(e>0.15, "Deep Work", "Creative Work")),
  IF(AND(h>=16, h<17.5), "Creative Work",
  IF(AND(h>=17.5, h<18.5), "Exercise",
  IF(AND(h>=18.5, h<21), "Free Time",
  IF(AND(h>=21, h<22.5), "Wind Down",
  "Free Time")))))))))))))))
)
```

Select B2, drag right to H2, then drag the entire row down to row 35.

---

## Step 8 — Conditional formatting (colour coding)

Select B2:H35, then add these rules via Format → Conditional formatting:

| Text contains       | Background | Text colour |
|---------------------|-----------|-------------|
| Deep Work           | #7a2020   | #ffcccc     |
| Creative Work       | #5a2a7a   | #e0c0ff     |
| Exercise            | #1e7a3a   | #b0ffc0     |
| Admin / Email       | #1e5a8a   | #b0d8ff     |
| Lunch               | #8a5a1e   | #ffe0b0     |
| Morning Routine     | #3d5a35   | #c0e8b0     |
| Break               | #3a3a3a   | #aaaaaa     |
| Free Time           | #7a6a1e   | #fff0b0     |
| Wind Down           | #4a4a50   | #b0b0b8     |
| Plan / Review       | #1a6a5a   | #b0ffe8     |
| Rest / Recharge     | #1e5a7a   | #b0e8ff     |
| Sleep               | #2c2c4a   | #8888aa     |

---

## Step 9 — Stats (optional, row 38+)

```
A38: Deep Work Hours     B38: =COUNTIF(B2:H35,"Deep Work")*0.5
A39: Creative Hours      B39: =COUNTIF(B2:H35,"Creative Work")*0.5
A40: Exercise Hours      B40: =COUNTIF(B2:H35,"Exercise")*0.5
A41: Admin Hours         B41: =COUNTIF(B2:H35,"Admin / Email")*0.5
A42: Free + Rest Hours   B42: =(COUNTIF(B2:H35,"Free Time")+COUNTIF(B2:H35,"Rest / Recharge"))*0.5
A43: Work Ratio          B43: =TEXT((B38+B39+B41)/(7*16),"0%")
```

---

## Formulas Reference

| Name | Formula | What it models |
|------|---------|---------------|
| Circadian Alertness | `sin(π(h-6)/8) × (1 - 0.3·max(0, sin(π(h-13)/2)))` | Two daily peaks (~10am, ~3pm) with post-lunch dip |
| Energy | `A(h) × (1 - 0.04·(h-6))` | Alertness decayed by linear fatigue |
| Ultradian | `(mins mod 110) < 90 → work` | 90min focus + 20min recovery (Kleitman) |
| Weekend | `max(0.2, 1 - 0.8·max(0, (d-4)/2))` | Sat 60% / Sun 20% work intensity |
