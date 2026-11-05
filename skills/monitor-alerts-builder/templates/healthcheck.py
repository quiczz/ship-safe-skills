#!/usr/bin/env python3
"""Small dependency-free health checker that alerts a webhook. Run it from cron or a scheduler.

Checks:  --url URL[,max_seconds]   HTTP status below 400 (and optionally fast enough)
         --disk PATH,MAX_PERCENT   disk usage at PATH stays below MAX_PERCENT
         --cert HOST[:PORT],DAYS   TLS certificate has more than DAYS days left
         --backup GLOB,MAX_HOURS   newest file matching GLOB is younger than MAX_HOURS

Alerts:  set the webhook in the ALERT_WEBHOOK_URL environment variable (keeps it out of `ps` and crontab).
         --kind slack|discord|generic|telegram   (telegram also needs --telegram-chat ID; the URL is
         https://api.telegram.org/bot<TOKEN>/sendMessage)
State:   --state FILE remembers results so you get ONE message when a check starts failing (after
         --failures-before-alert consecutive failures) and ONE when it recovers, not one per run.

Examples:
  ALERT_WEBHOOK_URL=https://hooks.slack.com/services/XXX \\
  python3 healthcheck.py --state /var/tmp/hc.json \\
      --url https://example.com/readyz,2 --disk /,85 --cert example.com,14 \\
      --backup '/backups/*.sql.gz,26'
  python3 healthcheck.py --selftest      # exercises every check locally, sends nothing
cron:  * * * * * /usr/bin/python3 /opt/healthcheck.py --state /var/tmp/hc.json --url https://example.com/readyz
"""
import argparse
import glob
import json
import os
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


def check_url(spec):
    url, _, limit = spec.partition(",")
    limit = float(limit) if limit else None
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "healthcheck/1.0"})
        with urllib.request.urlopen(req, timeout=max(limit or 10, 10)) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        return f"url {url}", False, f"unreachable: {type(e).__name__}: {e}"
    took = time.time() - t0
    if code >= 400:
        return f"url {url}", False, f"HTTP {code}"
    if limit and took > limit:
        return f"url {url}", False, f"slow: {took:.2f}s (limit {limit}s)"
    return f"url {url}", True, f"HTTP {code} in {took:.2f}s"


def check_disk(spec):
    path, _, pct = spec.partition(",")
    pct = float(pct or 85)
    u = shutil.disk_usage(path)
    used = u.used / u.total * 100
    return f"disk {path}", used < pct, f"{used:.0f}% used (limit {pct:.0f}%)"


def check_cert(spec):
    target, _, days = spec.partition(",")
    host, _, port = target.partition(":")
    days = float(days or 14)
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, int(port or 443)), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname=host) as t:
                exp = ssl.cert_time_to_seconds(t.getpeercert()["notAfter"])
    except Exception as e:
        return f"cert {host}", False, f"cannot read certificate: {type(e).__name__}: {e}"
    left = (exp - time.time()) / 86400
    return f"cert {host}", left > days, f"{left:.0f} days left (limit {days:.0f})"


def check_backup(spec):
    pattern, _, hours = spec.rpartition(",")
    hours = float(hours or 26)
    files = glob.glob(pattern)
    if not files:
        return f"backup {pattern}", False, "no backup files found"
    newest = max(files, key=os.path.getmtime)
    age = (time.time() - os.path.getmtime(newest)) / 3600
    return f"backup {pattern}", age < hours, f"newest is {age:.1f} h old (limit {hours:.0f} h): {os.path.basename(newest)}"


def send(url, kind, text, telegram_chat=None):
    if kind == "slack":
        body = {"text": text}
    elif kind == "discord":
        body = {"content": text[:1900]}
    elif kind == "telegram":
        body = {"chat_id": telegram_chat, "text": text}
    else:
        body = {"text": text, "timestamp": datetime.now(timezone.utc).isoformat()}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15).read()


def load_state(path):
    try:
        return json.load(open(path))
    except Exception:
        return {}


def run(args, notify=True):
    checks = ([check_url(s) for s in args.url] + [check_disk(s) for s in args.disk]
              + [check_cert(s) for s in args.cert] + [check_backup(s) for s in args.backup])
    state = load_state(args.state) if args.state else {}
    hook = os.environ.get("ALERT_WEBHOOK_URL")
    messages, failing = [], 0
    for name, ok, detail in checks:
        st = state.get(name, {"fails": 0, "alerted": False})
        if ok:
            if st["alerted"]:
                messages.append(f"RESOLVED  {name}: {detail}")
            st = {"fails": 0, "alerted": False}
        else:
            failing += 1
            st["fails"] += 1
            if st["fails"] >= args.failures_before_alert and not st["alerted"]:
                messages.append(f"ALERT  {name}: {detail}")
                st["alerted"] = True
        state[name] = st
        print(("OK   " if ok else "FAIL ") + f"{name}: {detail}")
    if args.state:
        json.dump(state, open(args.state, "w"))
    if messages and notify:
        host = socket.gethostname()
        text = f"[{host}] " + "\n".join(messages)
        if hook:
            try:
                send(hook, args.kind, text, args.telegram_chat)
            except Exception as e:
                print(f"could not send alert: {type(e).__name__}: {e}", file=sys.stderr)
        else:
            print("(no ALERT_WEBHOOK_URL set; would send:)\n" + text)
    return 1 if failing else 0, messages


def selftest():
    flag = {"down": True}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            healthy = self.path == "/ok" or (self.path == "/flip" and not flag["down"])
            self.send_response(200 if healthy else 503)
            self.end_headers()
        do_POST = do_GET

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    tmp = tempfile.mkdtemp()
    open(os.path.join(tmp, "db.sql.gz"), "w").write("x")
    os.utime(os.path.join(tmp, "db.sql.gz"), (time.time() - 3 * 3600,) * 2)
    results = {
        "url ok": check_url(f"{base}/ok,2")[1] is True,
        "url 503 detected": check_url(f"{base}/down")[1] is False,
        "url unreachable detected": check_url("http://127.0.0.1:1/x")[1] is False,
        "disk limit 100% passes": check_disk(".,100")[1] is True,
        "disk limit 0% fails": check_disk(".,0")[1] is False,
        "backup fresh passes": check_backup(f"{tmp}/*.sql.gz,26")[1] is True,
        "backup too old fails": check_backup(f"{tmp}/*.sql.gz,1")[1] is False,
        "backup missing fails": check_backup(f"{tmp}/none*,26")[1] is False,
    }
    # state/dedupe: down x3 -> exactly one ALERT; back up -> exactly one RESOLVED; still up -> silence
    st = os.path.join(tmp, "state.json")
    ns = argparse.Namespace(url=[f"{base}/flip"], disk=[], cert=[], backup=[], state=st,
                            failures_before_alert=2, kind="generic", telegram_chat=None)
    down = [run(ns, notify=False)[1] for _ in range(3)]
    flag["down"] = False
    up1 = run(ns, notify=False)[1]
    up2 = run(ns, notify=False)[1]
    results["alert fires once, after 2 failures"] = [len(x) for x in down] == [0, 1, 0] and down[1][0].startswith("ALERT")
    results["recovery sends one RESOLVED"] = len(up1) == 1 and up1[0].startswith("RESOLVED")
    results["no repeat while healthy"] = up2 == []
    shutil.rmtree(tmp)
    srv.shutdown()
    for k, v in results.items():
        print(("PASS " if v else "FAIL ") + k)
    return 0 if all(results.values()) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--disk", action="append", default=[])
    ap.add_argument("--cert", action="append", default=[])
    ap.add_argument("--backup", action="append", default=[])
    ap.add_argument("--state")
    ap.add_argument("--failures-before-alert", type=int, default=2)
    ap.add_argument("--kind", choices=["slack", "discord", "generic", "telegram"], default="generic")
    ap.add_argument("--telegram-chat")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    if not (args.url or args.disk or args.cert or args.backup):
        ap.error("give at least one of --url --disk --cert --backup (or --selftest)")
    sys.exit(run(args)[0])


if __name__ == "__main__":
    main()
