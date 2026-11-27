"""17.3/1  Cost tracking from run logs

Every lesson run writes a JSON-lines log (logs/*.jsonl), one JSON object per line. Each model
call leaves a `usage` event with token counts. That is enough to answer "what did we spend,
and on what?" without adding any code to your app: read the logs, multiply tokens by a price
list, and group by lesson.

The script makes two small real calls first, so the logs always have something in them.
The prices are INVENTED constants. Replace them with your provider's price list.

Run it:   ./run 17.3/1          (Windows: run 17.3/1)
     or:  python modules/17-monitoring-and-fine-tuning/03-cost-tracking-budgets-and-service-level-objectiv/01_cost_from_logs.py
"""

import json
from collections import defaultdict

from labkit import lesson
from labkit.config import state_dir

PRICE_IN_PER_M = 0.50  # dollars per million tokens (invented)
PRICE_OUT_PER_M = 1.50


def dollars(t_in, t_out):
    return t_in * PRICE_IN_PER_M / 1e6 + t_out * PRICE_OUT_PER_M / 1e6


def read_usage(folder):
    """Return one dict per log file: lesson id, calls, tokens in/out, unreported calls."""
    rows = []
    for path in sorted(folder.glob("*.jsonl")):
        row = {"file": path.name, "lesson": "?", "calls": 0, "in": 0, "out": 0, "unreported": 0}
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue  # a half-written last line is normal in a live log
                if event.get("event") == "start":
                    row["lesson"] = event.get("lesson", "?")
                elif event.get("event") == "usage":
                    row["calls"] += 1
                    if event.get("reported"):
                        row["in"] += event.get("tokens_in", 0)
                        row["out"] += event.get("tokens_out", 0)
                    else:
                        row["unreported"] += 1
        except OSError:
            continue
        rows.append(row)
    return rows


@lesson("17.3/1", "Cost tracking from run logs")
def main(ctx):
    ctx.step("Make two small calls so the logs are never empty")
    for text in ("The VPN client crashes when I open it.", "I am locked out of my account."):
        r = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": "You are the Larkspur Labs IT helpdesk. Reply in one short sentence."}, {"role": "user", "content": text}],
        )
        ctx.show_response(r)  # records usage, which writes the usage event we read below

    ctx.step("Read every run log")
    folder = state_dir("logs")
    rows = read_usage(folder)
    ctx.note(f"{len(rows)} log file(s) in the logs folder.")

    ctx.step("Group tokens and estimated dollars by lesson")
    by_lesson = defaultdict(lambda: {"runs": 0, "calls": 0, "in": 0, "out": 0, "unreported": 0})
    for row in rows:
        g = by_lesson[row["lesson"]]
        g["runs"] += 1
        for k in ("calls", "in", "out", "unreported"):
            g[k] += row[k]
    ranked = sorted(by_lesson.items(), key=lambda kv: dollars(kv[1]["in"], kv[1]["out"]), reverse=True)
    ctx.console.print(f"{'lesson':10} {'runs':>4} {'calls':>5} {'tokens in':>9} {'tokens out':>10} {'dollars':>9}", markup=False)
    for name, g in ranked[:8]:
        ctx.console.print(f"{name:10} {g['runs']:>4} {g['calls']:>5} {g['in']:>9} {g['out']:>10} {dollars(g['in'], g['out']):>9.6f}", markup=False)
    if len(ranked) > 8:
        ctx.note(f"... and {len(ranked) - 8} more lessons")

    ctx.step("Totals, and what the totals hide")
    t_in = sum(g["in"] for g in by_lesson.values())
    t_out = sum(g["out"] for g in by_lesson.values())
    calls = sum(g["calls"] for g in by_lesson.values())
    unreported = sum(g["unreported"] for g in by_lesson.values())
    total = dollars(t_in, t_out)
    ctx.note(f"{calls} calls, {t_in} tokens in, {t_out} tokens out: about ${total:.6f} at the invented prices.")
    if calls:
        ctx.note(f"average per call: ${total / calls:.7f}; input is {t_in / max(t_in + t_out, 1):.0%} of all tokens.")
    if unreported:
        ctx.note(f"{unreported} call(s) reported no token counts, so the true spend is higher than shown. An endpoint that hides usage cannot be budgeted exactly: estimate from text length (script 2).")
    ctx.note("Input and output have different prices, so keep both counts. A cache hit or batch discount needs another column.")


if __name__ == "__main__":
    main()
