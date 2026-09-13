#!/usr/bin/env python3
"""Acceptance harness for live editing: drive N single-definition edits at a
running live program and record what each one costs and whether it took effect.

Every phase runs under a memory cap that kills the whole process tree, so a
compiler that does not converge is a recorded outcome rather than a dead machine.

  python3 scripts/live-acceptance.py --target paper-calculator --edits 20
  python3 scripts/live-acceptance.py --target papercut --compiler /path/to/coil-candidate

Per edit it records: expansion rounds, bytes the compiler allocated, the
program's RSS and footprint, vmmap MALLOC_SMALL growth, the verdict, and a
correctness signal (the program is still alive and the edit is observable).
"""
import argparse, json, os, re, shutil, signal, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = Path.home() / "Documents/Code/projects/paper-test/.worktrees/live"

# A target names a project, the file and regex an edit rewrites, and how to tell
# from the outside that the running program actually changed.
TARGETS = {
    "paper-calculator": dict(
        project=PAPER / "apps/paper-calculator",
        binary="build/release/paper-calculator",
        edit_file="src/ui.coil",
        # the accent colour of the operator keys; cycles through distinct values
        pattern=r"0x(?:ed7959|2f6fed|3fa65b|c0392b)",
        values=["0xed7959", "0x2f6fed", "0x3fa65b", "0xc0392b"],
        expect_defn="defn key",
        observe="window",
        gui=True,
        manifest_edits=[
            ('path = "../../../coil-experiments/',
             'path = "../../../../../coil-experiments/'),
        ],
    ),
    "papercut": dict(
        project=PAPER,
        binary="build/release/papercut",
        edit_file="examples/main.coil",
        pattern=r"\(caption edition 10\.0 0x[0-9a-f]{6}",
        values=["(caption edition 10.0 0x9eaa98",
                "(caption edition 10.0 0x8e9a88",
                "(caption edition 10.0 0x7e8a78",
                "(caption edition 10.0 0x6e7a68"],
        expect_defn="defn toolbar",
        observe="window",
        gui=True,
        # whole-project live is not committed anywhere: it cannot build yet, so
        # the harness enables it for the run and restores the manifest after.
        # Ordered manifest edits. The dependency line must land inside
        # [dependencies] and the [metaprograms] section after it, or the
        # remaining dependency keys are read as metaprogram keys. The path
        # rewrites are because this checkout is a worktree two levels deeper
        # than the paths in the committed manifest assume.
        manifest_edits=[
            ('"../coil-experiments/src"', '"../../../coil-experiments/src"'),
            ('path = "../coil-experiments/', 'path = "../../../coil-experiments/'),
            ('layout = { path = "lib/layout" }',
             'layout = { path = "lib/layout" }\n'
             'live = { path = "../../../coil-experiments/src/experiments/live" }'),
            ('[link]', '[metaprograms]\nuse = ["experiments.live.enable"]\n\n[link]'),
        ],
    ),
}


def tree_pids(root):
    pids, out = [root], [root]
    while pids:
        try:
            r = subprocess.run(["pgrep", "-P", ",".join(map(str, pids))],
                               capture_output=True, text=True)
            nxt = [int(x) for x in r.stdout.split()]
        except Exception:
            nxt = []
        if not nxt:
            break
        out += nxt
        pids = nxt
    return out


def rss_kb(pid):
    r = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


def footprint_bytes(pid):
    r = subprocess.run(["footprint", "-p", str(pid)], capture_output=True, text=True)
    m = re.search(r"phys_footprint:\s*([\d.]+)\s*([KMG])?B", r.stdout)
    if not m:
        return None
    mult = {None: 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
    return int(float(m.group(1)) * mult[m.group(2)])


def malloc_small_bytes(pid):
    r = subprocess.run(["vmmap", str(pid)], capture_output=True, text=True)
    body = r.stdout.split("REGION TYPE", 1)
    if len(body) < 2:
        return None
    mult = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
    for ln in body[1].split("\n"):
        m = re.match(r"^(MALLOC_SMALL)\s{2,}([\d.]+)([KMG]?)\s", ln)
        if m:
            return int(float(m.group(2)) * mult.get(m.group(3), 1))
    return None


def run_capped(cmd, cwd, cap_mb, timeout_s, env=None, log=None):
    """Run cmd; kill the whole tree if it exceeds cap_mb. Returns a dict."""
    e = dict(os.environ)
    if env:
        e.update(env)
    out = open(log, "wb") if log else subprocess.DEVNULL
    p = subprocess.Popen(cmd, cwd=str(cwd), env=e, stdout=out, stderr=subprocess.STDOUT)
    peak, t0, verdict = 0, time.time(), "ok"
    while p.poll() is None:
        tot = 0
        for pid in tree_pids(p.pid):
            v = rss_kb(pid)
            if v:
                tot += v
        peak = max(peak, tot)
        if tot > cap_mb * 1024:
            verdict = f"KILLED: exceeded {cap_mb}MB"
            for pid in tree_pids(p.pid):
                try: os.kill(pid, signal.SIGKILL)
                except Exception: pass
            break
        if time.time() - t0 > timeout_s:
            verdict = f"KILLED: exceeded {timeout_s}s"
            for pid in tree_pids(p.pid):
                try: os.kill(pid, signal.SIGKILL)
                except Exception: pass
            break
        time.sleep(0.1)
    rc = p.wait()
    if out is not subprocess.DEVNULL:
        out.close()
    return dict(exit=rc, peak_rss_mb=round(peak / 1024, 1),
                seconds=round(time.time() - t0, 1), verdict=verdict)


def window_signature(gui, proc):
    """A cheap behavioural probe: the dominant colours of the app's own window.
    Returns None when no window can be found, which is reported, not guessed.
    The process must be addressed by its exact name -- System Events rejects
    `first process whose name contains ...` with "Invalid index"."""
    if not gui or not proc:
        return None
    try:
        subprocess.run(["osascript", "-e",
                        f'tell application "System Events" to set frontmost of '
                        f'process "{proc}" to true'],
                       capture_output=True, timeout=15)
        # The live host deliberately leaves redraw to the native event loop --
        # the publisher must not call application redraw functions on its
        # worker -- so an applied edit is not on screen until an event arrives.
        # Escape is inert for these apps and is enough to drive one frame.
        subprocess.run(["osascript", "-e",
                        'tell application "System Events" to key code 53'],
                       capture_output=True, timeout=15)
        time.sleep(1.2)
        b = subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to tell process "{proc}" '
             f'to get {{position, size}} of window 1'],
            capture_output=True, text=True, timeout=15).stdout.strip()
        if not b:
            return None
        nums = [int(x) for x in re.findall(r"-?\d+", b)]
        if len(nums) < 4:
            return None
        x, y, w, h = nums[:4]
        png = "/tmp/live_accept_shot.png"
        subprocess.run(["screencapture", "-x", f"-R{x},{y},{w},{h}", png],
                       capture_output=True, timeout=20)
        from PIL import Image
        im = Image.open(png).convert("RGB").resize((12, 12), Image.BOX)
        # A downscaled image hash. Dominant colours were useless here: a control
        # that occupies a few percent of the window can change completely without
        # moving them, so every edit read as "no visible change".
        return "".join(f"{r >> 4:x}{g >> 4:x}{b >> 4:x}"
                       for (r, g, b) in (im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=sorted(TARGETS), default="paper-calculator")
    ap.add_argument("--compiler", default=shutil.which("coil") or "coil")
    ap.add_argument("--coil-live", default=shutil.which("coil-live") or "coil-live")
    ap.add_argument("--edits", type=int, default=20)
    ap.add_argument("--cap-mb", type=int, default=8000)
    ap.add_argument("--build-timeout", type=int, default=1800)
    ap.add_argument("--apply-timeout-ms", type=int, default=600000)
    ap.add_argument("--out", default=None)
    ap.add_argument("--visual", action="store_true",
                    help="also confirm the window changed. Off by default: it "
                         "fronts the app and sends an event to force a frame, "
                         "which perturbs the memory numbers.")
    a = ap.parse_args()

    t = TARGETS[a.target]
    proj, src = Path(t["project"]), Path(t["project"]) / t["edit_file"]
    out_dir = Path(a.out) if a.out else REPO / "build/test-logs/live-acceptance"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    trace_log = out_dir / f"{a.target}-{stamp}-run.log"

    report = dict(target=a.target, project=str(proj), compiler=a.compiler,
                  started=stamp, edits_requested=a.edits, cap_mb=a.cap_mb,
                  build=None, startup=None, edits=[], outcome=None)

    original = src.read_text()
    manifest = proj / "Coil.toml"
    manifest_original = manifest.read_text()
    try:
        m = manifest_original
        for find, repl in t.get("manifest_edits") or []:
            if find in m:                      # idempotent: skip what is already right
                m = m.replace(find, repl, 1)
        if m != manifest_original:
            manifest.write_text(m)
            print("[preflight] adapted the project manifest (restored afterwards)")
        if "experiments.live.enable" not in m:
            report["outcome"] = "PREFLIGHT FAILED — project is not live-enabled"
            return finish(report, out_dir, stamp, a)
        # ---- build -------------------------------------------------------
        print(f"[build] {a.target} with {a.compiler}", flush=True)
        for p in (proj / ".coil-live",):
            if p.exists():
                shutil.rmtree(p)
        b = run_capped([a.compiler, "build"], proj, a.cap_mb, a.build_timeout,
                       log=str(out_dir / f"{a.target}-{stamp}-build.log"))
        report["build"] = b
        print(f"[build] peak={b['peak_rss_mb']}MB {b['seconds']}s exit={b['exit']} {b['verdict']}", flush=True)
        if b["verdict"] != "ok" or b["exit"] != 0:
            report["outcome"] = "BUILD FAILED — no live session to drive"
            return finish(report, out_dir, stamp, a)

        # ---- start -------------------------------------------------------
        env = dict(os.environ); env["COIL_TRACE"] = "1"
        logf = open(trace_log, "wb")
        app = subprocess.Popen([str(proj / t["binary"])], cwd=str(proj),
                               env=env, stdout=logf, stderr=subprocess.STDOUT)
        deadline = time.time() + 180
        live = False
        while time.time() < deadline and app.poll() is None:
            r = subprocess.run([a.coil_live, "status", "--dir", str(proj)],
                               capture_output=True, text=True)
            if "coil live: live" in r.stdout:
                live = True
                break
            tot = sum(rss_kb(p) or 0 for p in tree_pids(app.pid))
            if tot > a.cap_mb * 1024:
                break
            time.sleep(1)
        if not live:
            for pid in tree_pids(app.pid):
                try: os.kill(pid, signal.SIGKILL)
                except Exception: pass
            report["outcome"] = "STARTUP FAILED — program never reported live"
            report["startup"] = dict(rss_mb=None)
            return finish(report, out_dir, stamp, a)

        proc_name = Path(t["binary"]).name
        base = dict(rss_mb=round((rss_kb(app.pid) or 0) / 1024, 1),
                    footprint_mb=round((footprint_bytes(app.pid) or 0) / 1e6, 1),
                    malloc_small_mb=round((malloc_small_bytes(app.pid) or 0) / 1e6, 1),
                    window=window_signature(t["gui"], proc_name))
        report["startup"] = base
        print(f"[startup] rss={base['rss_mb']}MB footprint={base['footprint_mb']}MB", flush=True)

        # ---- edits -------------------------------------------------------
        prev_lines = sum(1 for _ in open(trace_log, errors="replace"))
        prev_window = base["window"]
        prev_version = None
        for i in range(1, a.edits + 1):
            text = src.read_text()
            cur = re.search(t["pattern"], text)
            if not cur:
                report["edits"].append(dict(n=i, error="edit pattern did not match"))
                report["outcome"] = f"EDIT PATTERN NOT FOUND at edit {i}"
                break
            nxt = next(v for v in t["values"] * 2
                       if v != cur.group(0))          # always a real change
            new = re.sub(t["pattern"], nxt, text, count=1)
            tmp = src.with_suffix(src.suffix + ".new")
            tmp.write_text(new); tmp.replace(src)          # atomic

            r = subprocess.run([a.coil_live, "apply", "--json", "--dir", str(proj),
                               "--timeout-ms", str(a.apply_timeout_ms)],
                               capture_output=True, text=True)
            file_version = None
            try:
                v = json.loads(r.stdout)
                state, summary = v.get("state"), v.get("summary", "")
                for f in v.get("files") or []:
                    if Path(f.get("path", "")).name == Path(t["edit_file"]).name:
                        file_version = f.get("version")
            except Exception:
                state, summary = "NO-REPLY", r.stdout[:120]

            alive = app.poll() is None
            time.sleep(1.5)
            lines = list(open(trace_log, errors="replace"))
            seg = lines[prev_lines:]
            prev_lines = len(lines)
            rounds = sum(1 for L in seg if L.startswith("coil-trace begin frontend.expand.round.resolve"))
            alloc = 0
            for L in seg:
                if L.startswith("coil-profile\tallocated\tfrontend.expand\t"):
                    try: alloc += int(L.rstrip("\n").split("\t")[3])
                    except Exception: pass

            win = (window_signature(t["gui"], proc_name)
                   if (alive and a.visual) else None)
            e = dict(n=i, state=state, summary=summary[:70],
                     names_expected_defn=t["expect_defn"] in summary,
                     alive=alive, rounds=rounds,
                     expand_alloc_mb=round(alloc / 1e6, 1),
                     rss_mb=round((rss_kb(app.pid) or 0) / 1024, 1) if alive else None,
                     footprint_mb=round((footprint_bytes(app.pid) or 0) / 1e6, 1) if alive else None,
                     malloc_small_mb=round((malloc_small_bytes(app.pid) or 0) / 1e6, 1) if alive else None,
                     file_version=file_version,
                     # the running program adopted bytes it did not have before
                     adopted_new_source=(file_version is not None
                                         and file_version != prev_version),
                     window_changed=(win != prev_window) if (win and prev_window) else None)
            prev_version = file_version or prev_version
            prev_window = win or prev_window
            report["edits"].append(e)
            print(f"[edit {i:2d}] {state:14s} rounds={rounds:3d} alloc={e['expand_alloc_mb']:7.1f}MB "
                  f"rss={e['rss_mb']} footprint={e['footprint_mb']} small={e['malloc_small_mb']} "
                  f"adopted={e['adopted_new_source']} visible={e['window_changed']}", flush=True)
            if not alive:
                report["outcome"] = f"PROGRAM DIED at edit {i}"
                break
            tot = sum(rss_kb(p) or 0 for p in tree_pids(app.pid))
            if tot > a.cap_mb * 1024:
                report["outcome"] = f"CAP EXCEEDED at edit {i}"
                break
        else:
            report["outcome"] = "COMPLETED"

        for pid in tree_pids(app.pid):
            try: os.kill(pid, signal.SIGKILL)
            except Exception: pass
        logf.close()
        return finish(report, out_dir, stamp, a)
    finally:
        src.write_text(original)
        manifest.write_text(manifest_original)
        subprocess.run(["pkill", "-9", "-f", t["binary"]], capture_output=True)


def finish(report, out_dir, stamp, a):
    ok = [e for e in report["edits"] if e.get("state") == "live"]
    applied = [e for e in ok if e.get("names_expected_defn")]
    visible = [e for e in ok if e.get("window_changed")]
    adopted = [e for e in ok if e.get("adopted_new_source")]
    report["summary"] = dict(
        edits_run=len(report["edits"]), edits_live=len(ok),
        edits_naming_expected_defn=len(applied),
        edits_adopting_new_source=len(adopted),
        edits_visibly_changed=len(visible))
    if len(ok) >= 2:
        d = [ok[i]["rss_mb"] - ok[i - 1]["rss_mb"] for i in range(1, len(ok))
             if ok[i]["rss_mb"] and ok[i - 1]["rss_mb"]]
        if d:
            report["summary"]["median_rss_growth_mb_per_edit"] = round(sorted(d)[len(d) // 2], 1)
            report["summary"]["total_rss_growth_mb"] = round(ok[-1]["rss_mb"] - report["startup"]["rss_mb"], 1)
        for key, label in (("footprint_mb", "footprint"),
                           ("malloc_small_mb", "malloc_small")):
            vals = [e[key] for e in ok if e.get(key)]
            if len(vals) >= 2:
                dd = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
                report["summary"][f"median_{label}_growth_mb_per_edit"] = \
                    round(sorted(dd)[len(dd) // 2], 1)
                base = report["startup"].get(key)
                if base:
                    report["summary"][f"total_{label}_growth_mb"] = round(vals[-1] - base, 1)
        rr = [e["rounds"] for e in ok if e["rounds"]]
        if rr:
            report["summary"]["median_rounds_per_edit"] = sorted(rr)[len(rr) // 2]
    p = out_dir / f"{report['target']}-{stamp}.json"
    p.write_text(json.dumps(report, indent=2))
    print("\n=== SUMMARY ===")
    print(f"outcome: {report['outcome']}")
    for k, v in report["summary"].items():
        print(f"  {k}: {v}")
    print(f"report: {p}")
    return 0 if report["outcome"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
