"""Long-running installs and downloads, tracked so the UI can show progress."""

import re
import subprocess
import threading
import time
import uuid

_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

_jobs = {}
_lock = threading.Lock()


def _new(title, item_id):
    job = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "item_id": item_id,
        "state": "running",
        "progress": 0.0,
        "message": "",
        "started": time.time(),
    }
    with _lock:
        _jobs[job["id"]] = job
    return job


def start(title, cmd, env=None, on_done=None, item_id=None):
    """Run cmd in the background and parse "NN%" out of its output."""
    job = _new(title, item_id)
    threading.Thread(target=_run, args=(job, cmd, env, on_done), daemon=True).start()
    return dict(job)


def _run(job, cmd, env, on_done):
    try:
        code = _stream(cmd, env, lambda line: _update(job, line))
        job["state"] = "done" if code == 0 else "failed"
        if code == 0:
            job["progress"] = 100.0
    except OSError as exc:
        job["state"] = "failed"
        job["message"] = str(exc)
    _finish(job, on_done)


def _stream(cmd, env, on_line):
    """Run cmd, feed each output line to on_line, return the exit code."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
    )
    # Progress bars redraw with \r, so split on both.
    buf = ""
    while True:
        chunk = proc.stdout.read(256)
        if not chunk:
            break
        buf += chunk
        *lines, buf = re.split(r"[\r\n]", buf)
        for line in lines:
            if line.strip():
                on_line(line.strip())
    if buf.strip():
        on_line(buf.strip())
    return proc.wait()


def _finish(job, on_done):
    if on_done:
        try:
            on_done(job)
        except Exception as exc:  # keep the job record even if the hook breaks
            job["message"] = str(exc)


def start_steps(title, steps, on_done=None, item_id=None):
    """Run several commands one after another as one job.

    steps is a list of (label, cmd, weight, parse): weight is the step's share
    of the progress bar and parse(line) returns how far the step is (0-1) or
    None. A failed step marks the job failed but the later steps still run.
    Each step's exit code lands in job["codes"].
    """
    job = _new(title, item_id)
    job["detail"] = ""
    job["codes"] = []
    total = sum(w for _, _, w, _ in steps) or 1

    def run_all():
        base = 0.0
        failed = []
        for label, cmd, weight, parse in steps:
            share = 100.0 * weight / total
            job["message"] = label

            def on_line(line, base=base, share=share, parse=parse):
                job["detail"] = line[-160:]
                frac = parse(line) if parse else None
                if frac is not None:
                    job["progress"] = max(job["progress"], round(base + share * min(1.0, frac), 1))

            try:
                code = _stream(cmd, None, on_line)
            except OSError as exc:
                code = 127
                job["detail"] = str(exc)
            job["codes"].append(code)
            if code != 0:
                failed.append(label)
            base += share
            job["progress"] = round(base, 1)
        job["message"] = f"{', '.join(failed)} failed" if failed else "Up to date"
        # The hook may add to the job, so it runs before the UI sees it finish.
        _finish(job, on_done)
        job["state"] = "failed" if failed else "done"

    threading.Thread(target=run_all, daemon=True).start()
    return dict(job)


def _update(job, line):
    job["message"] = line[-160:]
    frac = percent(line)
    if frac is not None:
        job["progress"] = min(100.0, 100.0 * frac)


def percent(line):
    """The "NN%" in a progress line as 0-1, or None."""
    match = _PERCENT.search(line)
    return float(match.group(1)) / 100.0 if match else None


def fake(title, item_id=None, seconds=6.0, done_message="Installed", done_extra=None):
    """A job that only advances a timer; used in mock mode."""
    job = _new(title, item_id)
    job["message"] = "Downloading"

    def tick():
        steps = 30
        for i in range(1, steps + 1):
            time.sleep(seconds / steps)
            job["progress"] = round(100.0 * i / steps, 1)
        job.update(done_extra or {})
        job["message"] = done_message
        job["state"] = "done"

    threading.Thread(target=tick, daemon=True).start()
    return dict(job)


def all_jobs():
    with _lock:
        jobs = [dict(j) for j in _jobs.values()]
    # Drop finished jobs after a few minutes so the list stays short.
    cutoff = time.time() - 300
    return [j for j in jobs if j["state"] == "running" or j["started"] > cutoff]
