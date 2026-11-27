"""19.3/1  Cron expressions by hand

The n8n Schedule Trigger's "Custom (Cron)" mode takes a cron expression such as `0 8 * * 1-5`. This script
parses the five-field form with plain Python (lists, ranges, steps, names), computes the next run times
from a FIXED start date so the output is repeatable, and explains the day-of-month / day-of-week rule that
surprises everyone. No n8n, no model, no network.

Run it:   ./run 19.3/1          (Windows: run 19.3/1)
     or:  python modules/19-workflow-automation-n8n/03-error-handling-schedules-and-expressions/01_cron_by_hand.py
"""

from datetime import datetime, timedelta

from labkit import lesson

FIELDS = [("minute", 0, 59), ("hour", 0, 23), ("day of month", 1, 31), ("month", 1, 12), ("day of week", 0, 6)]
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
DAYS = {d: i for i, d in enumerate("sun mon tue wed thu fri sat".split())}


def parse_field(text, low, high, names):
    """Return the set of allowed values for one field."""
    allowed = set()
    for part in text.lower().split(","):
        step = 1
        if "/" in part:
            part, step_text = part.split("/", 1)
            step = int(step_text)
        if part in ("*", ""):
            start, end = low, high
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = names.get(a, a), names.get(b, b)
            start, end = int(start), int(end)
        else:
            start = int(names.get(part, part))
            end = high if step != 1 else start  # "5/15" means from 5 every 15
        if start < low or end > high + (1 if names is DAYS else 0) or start > end:
            raise ValueError(f"'{text}' is outside {low}-{high}")
        allowed.update(range(start, end + 1, step))
    if names is DAYS and 7 in allowed:  # 7 is also Sunday
        allowed = (allowed - {7}) | {0}
    return allowed


def parse_cron(expr):
    parts = expr.split()
    if len(parts) == 6:
        raise ValueError("6 fields: n8n also accepts a leading SECONDS field; this teaching parser handles the 5-field form")
    if len(parts) != 5:
        raise ValueError(f"expected 5 fields (minute hour day-of-month month day-of-week), got {len(parts)}")
    sets = []
    for (label, low, high), text in zip(FIELDS, parts):
        names = MONTHS if label == "month" else DAYS if label == "day of week" else {}
        try:
            sets.append(parse_field(text, low, high, names))
        except ValueError as err:
            reason = str(err) if "outside" in str(err) else f"'{text}' is not a number, range or name"
            raise ValueError(f"{label}: {reason}") from None
    return sets, parts[2] != "*", parts[4] != "*"


def matches(sets, dom_restricted, dow_restricted, when):
    minute, hour, dom, month, dow = sets
    weekday = (when.weekday() + 1) % 7  # Python Monday=0 -> cron Sunday=0
    if when.minute not in minute or when.hour not in hour or when.month not in month:
        return False
    in_dom, in_dow = when.day in dom, weekday in dow
    # Classic cron rule: if BOTH day fields are restricted, a day matches when EITHER does.
    return (in_dom or in_dow) if dom_restricted and dow_restricted else (in_dom and in_dow)


def next_runs(expr, start, count=3, horizon_days=400):
    parsed = parse_cron(expr)
    when = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    runs = []
    for _ in range(horizon_days * 24 * 60):
        if matches(*parsed, when):
            runs.append(when)
            if len(runs) == count:
                break
        when += timedelta(minutes=1)
    return runs


@lesson("19.3/1", "Cron expressions by hand")
def main(ctx):
    start = datetime(2026, 11, 27, 9, 30)  # a Friday, fixed so the output never changes
    ctx.note(f"Reference time: {start:%A %Y-%m-%d %H:%M} (fixed). n8n uses the workflow's timezone setting for the real thing.")

    ctx.step("The four expressions a helpdesk team actually uses")
    for expr, meaning in (
        ("0 8 * * 1-5", "08:00 on weekdays (the digest workflow)"),
        ("*/15 * * * *", "every 15 minutes (poll for new tickets)"),
        ("30 17 * * fri", "17:30 on Fridays (weekly report)"),
        ("0 9 1 * *", "09:00 on the 1st of each month"),
    ):
        runs = ", ".join(f"{r:%a %d %b %H:%M}" for r in next_runs(expr, start))
        print(f"  {expr:<14} {meaning}\n      next: {runs}")

    ctx.step("The day-of-month / day-of-week trap")
    ctx.note("'0 9 13 * fri' does NOT mean 'Friday the 13th'. When both day fields are set, either one matches.")
    runs = ", ".join(f"{r:%a %d %b}" for r in next_runs("0 9 13 * fri", start, 4))
    print(f"  next four: {runs}")

    ctx.step("Bad expressions give a clear error")
    for expr in ("0 8 * *", "61 8 * * *", "0 25 * * *", "0 8 * * funday", "0 8 * * * *"):
        try:
            parse_cron(expr)
            print(f"  {expr!r}: accepted")
        except ValueError as err:
            print(f"  {expr!r}: {err}")
    ctx.note("n8n tells you at save time too, but validating in code lets a test catch a typo before import.")


if __name__ == "__main__":
    main()
