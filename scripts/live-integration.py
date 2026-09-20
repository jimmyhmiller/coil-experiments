#!/usr/bin/env python3
"""Development-only end-to-end gate; all application and tool code is Coil.

Creates a standalone consumer outside the workspace. Never edits a user's app.
Use --gui on macOS to exercise real AppKit/CALayer rendering on the main thread.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time

REPO = Path(__file__).resolve().parents[1]
COIL = os.environ.get("COIL_COMPILER", "coil")
CLI = REPO / "src/experiments/live-cli/build/release/coil-live"


def run(args, cwd, expected=0, timeout=120):
    result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True,
                            text=True, timeout=timeout)
    if result.returncode != expected:
        raise AssertionError(f"{args}: expected {expected}, got {result.returncode}\n"
                             f"{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def source(gui=False, version=1, broken=False, migrate=False):
    schema = "(defstruct State [(ticks i64) (enabled bool)])"
    enabled = "(if (.enabled state) 1 0)"
    initial = "true"
    if version >= 3:
        schema = "(defsum Visibility (Hidden) (Visible))\n" \
                 "(defstruct State [(ticks i64) (enabled Visibility)])"
        enabled = "(match (.enabled state) (Hidden [] 0) (Visible [] 1))"
        initial = "(Visible)"
    migration = "(migrate State enabled old (if old (Visible) (Hidden)))" if migrate else ""
    imports = '(import "proof.window" :as window)' if gui else ""
    main_thread = "(extern pthread_main_np :cc c [] (-> i32))" if gui else ""
    thread_value = "(primitive/cast i64 (pthread_main_np))" if gui else "1"
    render = """
      (window/window-begin-frame!)
      (window/window-ball! 0 (% (.ticks state) 600) 200 (radius) 80 0)
      (window/window-end-frame!)""" if gui else "(usleep 16000)"
    open_window = "(window/window-open!)" if gui else "0"
    condition = "(window/window-open?)" if gui else "true"
    return f'''(module proof.main)
(import "coil.primitive" :as primitive)
(import "proof.logic" :as logic)
{imports}
(extern usleep :cc c [i32] (-> i32))
(extern printf :cc c [(ptr i8) ...] (-> i32))
(extern fflush :cc c [(ptr i8)] (-> i32))
(extern abort :cc c [] (-> void))
{main_thread}
{schema}
{migration}
(letonce state (State :ticks 100 :enabled {initial}))
(defn radius [] (-> i64) {('"bad"' if broken else '(+ ' + str(10 if version == 1 else 30) + ' (logic/adjustment))')})
(defn frame [] (-> i64)
  (set! (.ticks state) (+ (.ticks state) 1))
  {render}
  (when (= (% (.ticks state) 10) 0)
    (printf c"PROOF %ld %ld %ld %ld\\n" (.ticks state) (radius) {enabled} {thread_value})
    (fflush (primitive/cast (ptr i8) 0)) 0)
  0)
; A project host must not invent calls to application callbacks on its worker.
(defn redraw [] (-> i64) (abort) 0)
(defn main [] (-> i64)
  {open_window}
  (while {condition} (frame))
  0)
'''


def write(path, text):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def await_row(log, proc, radius, after=0):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"application exited {proc.returncode}\n{log.read_text()}")
        rows = re.findall(r"PROOF (\d+) (\d+) (\d+) (\d+)", log.read_text())
        matches = [tuple(map(int, row)) for row in rows
                   if int(row[1]) == radius and int(row[0]) > after]
        if matches:
            row = matches[-1]
            assert row[2:] == (1, 1), row
            return row
        time.sleep(.05)
    raise AssertionError(f"no frame with radius={radius} after ticks={after}\n{log.read_text()}")


def cli(root, op="status", expected=0):
    output = run([CLI, op, "--json", "--dir", root], REPO, expected, timeout=40)
    return json.loads(output)


def wait_state(root, expected, code):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = subprocess.run([str(CLI), "status", "--json", "--dir", str(root)],
                                capture_output=True, text=True, timeout=35)
        if result.returncode == code:
            report = json.loads(result.stdout)
            if report["state"] == expected:
                return report
        time.sleep(.05)
    raise AssertionError(f"did not reach {expected}: {result.stdout} {result.stderr}")


def transport_gate(root):
    # A stale discovery file pointing to a silent or malformed local service
    # must not hang, crash, or report a successful live operation.
    port_file = root / ".nrepl-port"
    original = port_file.read_text()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port_file.write_text(str(listener.getsockname()[1]))
        started = time.monotonic()
        output = run([CLI, "status", "--dir", root, "--timeout-ms", "100"], REPO, 2)
        assert time.monotonic() - started < 3, output
        assert "deadline" in output, output
    for bad in ("0", "65536", "9999999999999999999999999999999999"):
        port_file.write_text(bad)
        assert "port number" in run([CLI, "status", "--dir", root], REPO, 2)
    port_file.write_text(original)
    for payload in (b"le", b"d1:xe", b"di1e1:xe", b"d6:statusi1ee",
                    b"l" * 70 + b"e" * 70):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port_file.write_text(str(listener.getsockname()[1]))
            def reply():
                with listener.accept()[0] as connection:
                    connection.recv(4096)
                    connection.sendall(payload)
            worker = threading.Thread(target=reply)
            worker.start()
            run([CLI, "status", "--dir", root, "--timeout-ms", "500"], REPO, 2)
            worker.join(timeout=2)
            assert not worker.is_alive()
    port_file.write_text(original)


def nrepl_gate(root):
    def bstring(text):
        data = text.encode()
        return str(len(data)).encode() + b":" + data
    def request(**fields):
        return b"d" + b"".join(bstring(k) + bstring(v) for k, v in sorted(fields.items())) + b"e"
    port = int((root / ".nrepl-port").read_text())
    # Every byte is sent separately. The server must retain partial frames.
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        for byte in request(op="coil/file-status", format="json"):
            connection.sendall(bytes([byte]))
            time.sleep(.001)
        reply = connection.recv(65536)
        assert b'"state":"live"' in reply, reply
        # Same persistent connection, two requests in one TCP payload.
        connection.sendall(request(op="eval", code="(defn radius [] (-> i64) 999)") +
                           request(op="coil/file-status", project="/wrong-project"))
        replies = b""
        while b"different project" not in replies:
            replies += connection.recv(65536)
        assert b"owned by a live source file" in replies, replies
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(request(op="coil/file-apply", policy="typo"))
        assert b"invalid file operation options" in connection.recv(65536)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--hold", type=int, default=0, help="keep the verified window open this many seconds for visual inspection")
    args = parser.parse_args()
    run([COIL, "build"], CLI.parents[2])
    root = Path(tempfile.mkdtemp(prefix="coil-live-proof-")).resolve()
    print(f"consumer: {root}", flush=True)
    entry = root / "main.coil"
    manifest = f'''[package]
name = "proof"
entry = "main.coil"
[dependencies]
live = {{ path = "{REPO}/src/experiments/live" }}
[metaprograms]
use = ["experiments.live.enable"]
'''
    if args.gui:
        manifest = manifest.replace("[metaprograms]", f'''invaders = {{ path = "{REPO}/src/apps/invaders" }}
[link]
frameworks = ["QuartzCore"]
[metaprograms]''')
        window = (REPO / "src/experiments/live-demo/window.coil").read_text()
        (root / "window.coil").write_text(window.replace("experiments.live-demo.window", "proof.window"))
    (root / "Coil.toml").write_text(manifest)
    logic = root / "logic.coil"
    write(logic, '(module proof.logic)\n(defstruct Config [(offset i64)])\n'
                 '(letonce config (Config :offset 0))\n'
                 '(defn adjustment [] (-> i64) (.offset config))\n')
    write(entry, source(args.gui, broken=True))
    for command in ([COIL, "check"], [COIL, "lint", "main.coil"]):
        output = run(command, root, 1)
        assert "radius" in output, output
    print("PASS offline check and file lint reject a bad entry", flush=True)
    write(entry, source(args.gui))
    run([COIL, "build"], root)
    log = root / "application.log"
    proc = None
    try:
        with log.open("w") as stream:
            proc = subprocess.Popen([str(root / "build/release/proof")], cwd="/",
                                    stdout=stream, stderr=subprocess.STDOUT)
        row = await_row(log, proc, 10)
        original = cli(root)
        assert original["state"] == "live", original
        print("PASS external dependency, foreign launch directory, native frame loop", flush=True)
        duplicate = run([root / "build/release/proof"], root, 1)
        assert "already has an active" in duplicate, duplicate
        assert cli(root)["epoch"] == original["epoch"]
        print("PASS second launch cannot steal discovery", flush=True)
        nested = root / "nested"
        nested.mkdir()
        assert cli(nested)["entry"] == str(entry)
        write(entry, source(args.gui, version=2))
        live = cli(root, "apply")
        assert live["epoch"] > original["epoch"], live
        row = await_row(log, proc, 30, row[0])
        print("PASS direct agent edit changes native frames and preserves state", flush=True)
        # A source change confined to an imported module is one project edit.
        initial_logic = logic.read_text()
        write(logic, initial_logic.replace('(.offset config))', '(+ 5 (.offset config)))'))
        imported = cli(root, "apply")
        assert imported["epoch"] > live["epoch"], imported
        assert str(logic) in [f["path"] for f in imported["files"]], imported
        row = await_row(log, proc, 35, row[0])
        print("PASS imported function edit reaches the unchanged entry and native main", flush=True)
        floating_logic = '(module proof.logic)\n(import "coil.primitive" :as primitive)\n' \
                         '(defstruct Config [(offset f64)])\n' \
                         '(letonce config (Config :offset 99.0))\n' \
                         '(defn adjustment [] (-> i64) (+ 5 (primitive/cast i64 (.offset config))))\n'
        write(logic, floating_logic)
        need = cli(root, "apply", 1)
        assert need["state"] == "needs-migration", need
        assert any(p["file"] == str(logic) for p in need["problems"]), need
        for command in ("check", "lint"):
            output = run([COIL, command], root, 1)
            assert "migrate Config offset old" in output and "logic.coil" in output, output
        row = await_row(log, proc, 35, row[0])
        floating_logic += '(migrate Config offset old (primitive/cast f64 old))\n'
        write(logic, floating_logic)
        live = cli(root, "apply")
        row = await_row(log, proc, 35, row[0])  # old offset 0 survived; initializer 99 did not run
        print("PASS imported schema migration, original file diagnostics, and state retention", flush=True)
        palette = root / "arbitrary-file-name.coil"
        write(palette, '(module proof.palette) (defn amount [] (-> i64) 6)')
        transitive_logic = floating_logic.replace('(import "coil.primitive" :as primitive)',
                            '(import "coil.primitive" :as primitive)\n(import "proof.palette" :as palette)')
        transitive_logic = transitive_logic.replace('(+ 5 ', '(+ (palette/amount) ')
        write(logic, transitive_logic)
        live = cli(root, "apply")
        row = await_row(log, proc, 36, row[0])
        assert str(palette) in [f["path"] for f in live["files"]], live
        write(palette, '(module proof.palette) (defn amount [] (-> i64) 8)')
        live = cli(root, "apply")
        row = await_row(log, proc, 38, row[0])
        for value in (7, 9, 4, 0):
            write(palette, f'(module proof.palette) (defn amount [] (-> i64) {value})')
            live = cli(root, "apply")
            row = await_row(log, proc, 30 + value, row[0])
        print("PASS new transitive import, namespace discovery, repeated image reclamation", flush=True)
        write(entry, source(args.gui, version=2, broken=True))
        rejected = cli(root, "apply", 1)
        assert rejected["state"] == "rejected", rejected
        assert rejected["epoch"] == live["epoch"], rejected
        row = await_row(log, proc, 30, row[0])
        print("PASS rejected function leaves the previous generation rendering", flush=True)
        write(entry, source(args.gui, version=3))
        migration = cli(root, "apply", 1)
        assert migration["state"] == "needs-migration", migration
        assert migration["epoch"] == live["epoch"], migration
        assert "migrate State enabled old" in json.dumps(migration), migration
        for command in ("check", "lint"):
            output = run([COIL, command], root, 1)
            assert "migrate State enabled old" in output, output
        print("PASS ordinary project check and lint explain the pending migration", flush=True)
        write(entry, source(args.gui, version=3, migrate=True))
        migrated = cli(root, "apply")
        assert migrated["state"] == "live", migrated
        row = await_row(log, proc, 30, row[0])
        assert cli(root, "check")["epoch"] == migrated["epoch"]
        assert cli(root, "apply")["epoch"] == migrated["epoch"]
        for command in ("check", "lint"):
            run([COIL, command], root)
        print("PASS migration preserves running values and is applied exactly once", flush=True)
        accepted = source(args.gui, version=3, migrate=True)
        write(entry, accepted.replace("(while", "(usleep 1)\n  (while"))
        assert cli(root, "apply", 1)["state"] == "needs-restart"
        write(entry, accepted.replace('(defn radius [] (-> i64) (+ 30 (logic/adjustment)))', ''))
        assert cli(root, "apply", 1)["state"] == "needs-restart"
        assert cli(root, "apply", 1)["state"] == "needs-restart"
        write(entry, accepted + "\n(defn incomplete")
        assert cli(root, "apply", 1)["state"] == "unreadable"
        write(entry, accepted)
        wait_state(root, "live", 0)
        entry.unlink()
        assert cli(root, expected=1)["state"] == "unreadable"
        assert cli(root, "check", 1)["state"] == "unreadable"
        write(entry, accepted)
        wait_state(root, "live", 0)
        print("PASS main/deletion/unreadable edits are recoverable and reported accurately", flush=True)
        if args.gui:
            renderer = root / "window.coil"
            saved = renderer.read_text()
            # Change the actual imported Cocoa renderer while the window runs.
            write(renderer, saved.replace('CGColorCreateGenericRGB r g b 0.96',
                                          'CGColorCreateGenericRGB b r g 0.96'))
            before_renderer = cli(root, "apply")
            row = await_row(log, proc, 30, row[0])
            renderer.unlink()
            assert cli(root, "apply", 1)["state"] == "unreadable"
            write(renderer, saved)
            recovered = wait_state(root, "live", 0)
            assert recovered["epoch"] > before_renderer["epoch"], recovered
            row = await_row(log, proc, 30, row[0])
            print("PASS imported native renderer reloads; deleted module restores without restart", flush=True)
        # The MCP bridge is exercised like an agent client, including a real
        # live_status call; stdout must contain only valid protocol messages.
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "live_status", "arguments": {"dir": str(root)}}},
        ]
        mcp = subprocess.run([str(CLI), "mcp", "--dir", str(root)], input="".join(
            json.dumps(r) + "\n" for r in requests), text=True, capture_output=True, timeout=40)
        assert mcp.returncode == 0, mcp.stderr
        responses = [json.loads(line) for line in mcp.stdout.splitlines()]
        assert [r["id"] for r in responses] == [1, 2, 3], responses
        assert len(responses[1]["result"]["tools"]) == 3, responses
        assert not responses[2]["result"].get("isError"), responses
        print("PASS MCP discovery and a real agent status operation", flush=True)
        nrepl_gate(root)
        print("PASS fragmented/pipelined requests, file ownership, project identity and option validation", flush=True)
        transport_gate(root)
        print("PASS bounded connection deadline and malformed discovery", flush=True)
        await_row(log, proc, 30, row[0])
        print("PASS application remains alive after all rejected edits and migrations", flush=True)
        if args.hold:
            print(f"holding verified application for {args.hold} seconds", flush=True)
            time.sleep(args.hold)
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        dest = REPO / "build/test-logs/live"
        dest.mkdir(parents=True, exist_ok=True)
        if log.exists():
            shutil.copy2(log, dest / ("gui.log" if args.gui else "headless.log"))
        if not args.keep:
            shutil.rmtree(root)


if __name__ == "__main__":
    main()
