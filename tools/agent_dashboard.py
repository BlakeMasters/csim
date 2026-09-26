#!/usr/bin/env python3
"""Serve a small, read-only dashboard for .agents/BOARD.md on localhost."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / ".agents" / "BOARD.md"
TASK_COLUMNS = ("ID", "Work", "Status", "Owner", "Evidence / next action")
ACTIVITY_COLUMNS = ("UTC date", "Event", "Ledger / evidence")
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def plain_text(value: str) -> str:
    """Keep Markdown labels readable without treating board text as HTML."""
    return LINK.sub(r"\1", value).replace("`", "").strip()


def split_row(line: str) -> list[str]:
    return [part.strip() for part in line.strip().strip("|").split("|")]


def read_table(lines: list[str], columns: tuple[str, ...]) -> list[dict[str, str]]:
    for index, line in enumerate(lines):
        if line.strip().startswith("|") and split_row(line) == list(columns):
            break
    else:
        raise ValueError(f"Board table missing: {', '.join(columns)}")

    rows = []
    for line_number, line in enumerate(lines[index + 2 :], start=index + 3):
        if not line.strip().startswith("|"):
            break
        values = split_row(line)
        if len(values) != len(columns):
            raise ValueError(f"Board table has {len(values)} cells on line {line_number}")
        rows.append(dict(zip(columns, map(plain_text, values))))
    return rows


def parse_board(source: str) -> dict[str, object]:
    lines = source.splitlines()
    updated = next(
        (line.removeprefix("Updated: ").split(". ", 1)[0]
         for line in lines if line.startswith("Updated: ")),
        "Not recorded",
    )
    return {
        "updated": updated,
        "tasks": read_table(lines, TASK_COLUMNS),
        "activity": read_table(lines, ACTIVITY_COLUMNS),
    }


def status_kind(status: str) -> str:
    value = status.casefold()
    if value in {"done", "complete", "completed"}:
        return "done"
    if any(word in value for word in ("in progress", "active", "working", "running")):
        return "active"
    if value.startswith(("needs", "waiting")) or "blocked" in value:
        return "waiting"
    if value.startswith(("later", "planned", "backlog", "queued")):
        return "later"
    return "other"


def render_dashboard(board: dict[str, object], edited: str) -> str:
    tasks = board["tasks"]
    activity = board["activity"]
    counts = Counter(status_kind(task["Status"]) for task in tasks)
    summary = (
        ("Tasks", len(tasks)),
        ("Working", counts["active"]),
        ("Needs input", counts["waiting"]),
        ("Later", counts["later"]),
        ("Done", counts["done"]),
    )
    stats_html = "".join(
        f'<div class="stat"><strong>{number}</strong><span>{escape(label)}</span></div>'
        for label, number in summary
    )
    task_html = "".join(
        '<article class="task">'
        '<div class="task-top">'
        f'<span class="task-id">{escape(task["ID"])}</span>'
        f'<span class="status {status_kind(task["Status"])}">'
        f'{escape(task["Status"])}</span></div>'
        f'<h3>{escape(task["Work"])}</h3>'
        f'<p class="owner">Owner <strong>{escape(task["Owner"])}</strong></p>'
        f'<p class="evidence">{escape(task["Evidence / next action"])}</p>'
        '</article>'
        for task in tasks
    ) or '<p class="empty">No work items are recorded yet.</p>'
    activity_html = "".join(
        '<li>'
        f'<time>{escape(item["UTC date"])}</time>'
        f'<p>{escape(item["Event"])}</p>'
        f'<small>{escape(item["Ledger / evidence"])}</small>'
        '</li>'
        for item in reversed(activity)
    ) or '<li>No completed activity is recorded yet.</li>'

    return PAGE.replace("{{STATS}}", stats_html).replace(
        "{{TASKS}}", task_html
    ).replace("{{ACTIVITY}}", activity_html).replace(
        "{{UPDATED}}", escape(str(board["updated"]))
    ).replace("{{EDITED}}", escape(edited))


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="15">
  <title>CellSim agent work board</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      background: #f3f5f8; color: #1d2938; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    header { background: #17324d; color: #fff; padding: 3rem max(1.5rem, calc((100vw - 1120px) / 2)); }
    header .eyebrow { color: #9de0d3; font-size: .78rem; font-weight: 700;
      letter-spacing: .13em; text-transform: uppercase; }
    h1 { font-size: clamp(2rem, 4vw, 3rem); line-height: 1.1; margin: .65rem 0; }
    header p { color: #d6e3ec; margin: .5rem 0 0; max-width: 700px; }
    main { max-width: 1120px; margin: 0 auto; padding: 1.5rem; }
    .meta { color: #526174; font-size: .85rem; margin: .3rem 0 1.5rem; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .8rem; }
    .stat, .task, .activity { background: #fff; border: 1px solid #dce3eb;
      border-radius: 12px; box-shadow: 0 2px 8px #17324d0a; }
    .stat { padding: 1rem 1.1rem; }
    .stat strong { display: block; font-size: 1.9rem; line-height: 1.1; }
    .stat span { color: #536276; font-size: .85rem; }
    h2 { font-size: 1.2rem; margin: 2.1rem 0 .85rem; }
    .tasks { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: .9rem; }
    .task { padding: 1.15rem; min-width: 0; }
    .task-top { display: flex; align-items: center; justify-content: space-between; gap: .6rem; }
    .task-id { font-size: .78rem; font-weight: 800; letter-spacing: .08em; color: #426078; }
    .status { border-radius: 999px; padding: .28rem .65rem; font-size: .73rem;
      font-weight: 700; white-space: nowrap; }
    .status.done { background: #e2f5ec; color: #196445; }
    .status.active { background: #e1eeff; color: #255a9f; }
    .status.waiting { background: #fff0d0; color: #845300; }
    .status.later { background: #ecedf0; color: #555d68; }
    .status.other { background: #eee8fc; color: #5e418f; }
    h3 { font-size: 1rem; line-height: 1.35; margin: .9rem 0 1rem; }
    .owner { font-size: .78rem; color: #667486; margin: 0 0 .8rem; }
    .owner strong { color: #25374a; margin-left: .35rem; }
    .evidence { border-top: 1px solid #e8edf2; padding-top: .8rem; margin: 0;
      color: #526174; font-size: .85rem; line-height: 1.45; overflow-wrap: anywhere; }
    .activity { padding: .4rem 1.2rem; }
    .activity ol { list-style: none; margin: 0; padding: 0; }
    .activity li { border-bottom: 1px solid #e8edf2; padding: .9rem 0; }
    .activity li:last-child { border-bottom: 0; }
    .activity time { color: #426078; font-size: .76rem; font-weight: 700; }
    .activity p { margin: .25rem 0; font-size: .9rem; }
    .activity small { color: #667486; overflow-wrap: anywhere; }
    .empty { color: #667486; }
    footer { color: #667486; font-size: .78rem; margin: 2rem 0 .5rem; }
    @media (max-width: 640px) { header { padding: 2rem 1.2rem; } main { padding: 1.2rem; } }
  </style>
</head>
<body>
  <header>
    <div class="eyebrow">CellSim / project coordination</div>
    <h1>Agent work board</h1>
    <p>A read-only view of the assignments and evidence recorded in <code>.agents/BOARD.md</code>.</p>
  </header>
  <main>
    <p class="meta">Board says updated {{UPDATED}} · File edited {{EDITED}} · Refreshes every 15 seconds</p>
    <div class="stats" aria-label="Task counts">{{STATS}}</div>
    <section aria-labelledby="work-heading">
      <h2 id="work-heading">Work items</h2>
      <div class="tasks">{{TASKS}}</div>
    </section>
    <section aria-labelledby="activity-heading">
      <h2 id="activity-heading">Completed activity</h2>
      <div class="activity"><ol>{{ACTIVITY}}</ol></div>
    </section>
    <footer>Statuses are board entries, not a live view of running agents or processes. Edit the board to update this page.</footer>
  </main>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlsplit(self.path).path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        try:
            board = parse_board(BOARD.read_text(encoding="utf-8"))
            edited = datetime.fromtimestamp(BOARD.stat().st_mtime, timezone.utc)
            body = render_dashboard(board, edited.strftime("%Y-%m-%d %H:%M UTC"))
            status = 200
        except (OSError, ValueError) as error:
            body = f"<h1>Board unavailable</h1><p>{escape(str(error))}</p>"
            status = 500
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="localhost port (default: 8765)")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Agent dashboard: http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
