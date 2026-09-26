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
    value = status.strip().casefold()
    first = value.split(maxsplit=1)[0].rstrip(";:,") if value else ""
    if first in {"done", "complete", "completed"}:
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
        ("Other", counts["other"]),
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
    :root { color-scheme: dark; --bg: #07111b; --box: #102334; --line: #55778c;
      --ink: #e9f6fa; --muted: #a9c5cf; --cyan: #69dfe5; --amber: #ffd178; }
    * { box-sizing: border-box; }
    body { margin: 0; color: var(--ink); background-color: var(--bg);
      background-image: linear-gradient(#102435 1px, transparent 1px),
        linear-gradient(90deg, #102435 1px, transparent 1px);
      background-size: 16px 16px; font: 11px/1.35 Consolas, "Cascadia Mono", monospace; }
    header { min-height: 38px; padding: 8px max(12px, calc((100vw - 1460px) / 2));
      background: #183345; border-bottom: 4px solid var(--cyan); }
    h1 { margin: 0; padding-left: 9px; border-left: 6px solid var(--cyan);
      font-size: 15px; line-height: 18px; letter-spacing: .05em; }
    main { max-width: 1460px; margin: 0 auto; padding: 9px 12px 20px; }
    .meta { margin: 0 0 8px; color: var(--muted); font-size: 10px; }
    .stats { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 5px; }
    .stat, .task, .activity { min-width: 0; background: var(--box); border: 2px solid var(--line);
      border-radius: 0; box-shadow: 3px 3px 0 #050e17; }
    .stat { display: flex; align-items: baseline; justify-content: space-between; gap: 6px;
      padding: 5px 7px; }
    .stat strong { font-size: 18px; line-height: 1; color: var(--cyan); }
    .stat span { color: var(--muted); font-size: 10px; text-align: right; }
    section { min-width: 0; }
    h2 { margin: 11px 0 5px; padding: 3px 7px; border-left: 5px solid var(--cyan);
      background: #173345; color: var(--ink); font-size: 11px; letter-spacing: .05em; }
    .tasks { display: grid; grid-template-columns: minmax(0, 1fr); gap: 4px; }
    .task { display: grid; grid-template-columns: minmax(140px, .48fr) minmax(220px, 1fr)
      minmax(130px, .48fr) minmax(330px, 2.15fr); gap: 7px; align-items: start;
      padding: 5px 7px; }
    .task:nth-child(even) { background: #142b3c; }
    .task-top { display: flex; flex-direction: column; align-items: flex-start; gap: 3px; min-width: 0; }
    .task-id { color: var(--cyan); font-size: 10px; font-weight: 900; overflow-wrap: anywhere; }
    .status { display: inline-block; max-width: 100%; padding: 1px 4px; border: 1px solid currentColor;
      border-radius: 0; font-size: 9px; line-height: 1.2; overflow-wrap: anywhere; }
    .status.done { color: #86e0bb; background: #1c493d; }
    .status.active { color: #69dfe5; background: #17445a; }
    .status.waiting { color: var(--amber); background: #4c3924; }
    .status.later { color: #c5d1d7; background: #283b48; }
    .status.other { color: #bbabff; background: #352c55; }
    h3 { margin: 0; font-size: 11px; line-height: 1.3; font-weight: 700; }
    .owner { margin: 0; color: var(--muted); font-size: 10px; overflow-wrap: anywhere; }
    .owner strong { display: block; color: var(--ink); font-weight: 600; }
    .evidence { margin: 0; color: var(--muted); font-size: 10px; line-height: 1.3;
      overflow-wrap: anywhere; }
    .activity { padding: 0 7px; }
    .activity ol { list-style: none; margin: 0; padding: 0; }
    .activity li { display: grid; grid-template-columns: 130px minmax(250px, 1fr) minmax(300px, 1.2fr);
      gap: 7px; padding: 6px 0; border-bottom: 1px solid #315268; }
    .activity li:last-child { border-bottom: 0; }
    .activity time { color: var(--cyan); font-size: 10px; font-weight: 700; }
    .activity p, .activity small { margin: 0; font-size: 10px; line-height: 1.3; overflow-wrap: anywhere; }
    .activity small { color: var(--muted); }
    .empty, footer { color: var(--muted); }
    footer { margin: 12px 0 0; font-size: 10px; }
    @media (max-width: 960px) {
      .task { grid-template-columns: minmax(110px, .4fr) minmax(0, 1fr); }
      .task .owner, .task .evidence { grid-column: 2; }
      .activity li { grid-template-columns: 105px minmax(0, 1fr); }
      .activity small { grid-column: 2; }
    }
    @media (max-width: 620px) {
      .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .task { grid-template-columns: minmax(0, 1fr); }
      .task-top { flex-direction: row; align-items: center; flex-wrap: wrap; }
      .task .owner, .task .evidence { grid-column: 1; }
      .owner strong { display: inline; }
      .activity li { grid-template-columns: minmax(0, 1fr); }
      .activity small { grid-column: 1; }
    }
  </style>
</head>
<body>
  <header><h1>Agent work board</h1></header>
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
