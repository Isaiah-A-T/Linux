"""Long-running installs and downloads, tracked so the UI can show progress."""

import re
import subprocess
import threading
import time
import uuid

_PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

_jobs = {}
_lock = threading.Lock()


def start(title, cmd, env=None, on_done=None, item_id=None):
    """Run cmd in the background and parse "NN%" out of its output."""
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
    threading.Thread(target=_run, args=(job, cmd, env, on_done), daemon=True).start()
    return dict(job)


def _run(job, cmd, env, on_done):
    try:
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
                _update(job, line)
        code = proc.wait()
        job["state"] = "done" if code == 0 else "failed"
        if code == 0:
            job["progress"] = 100.0
    except OSError as exc:
        job["state"] = "failed"
        job["message"] = str(exc)
    if on_done:
        try:
            on_done(job)
        except Exception as exc:  # keep the job record even if the hook breaks
            job["message"] = str(exc)


def _update(job, line):
    line = line.strip()
    if not line:
        return
    job["message"] = line[-160:]
    match = _PERCENT.search(line)
    if match:
        job["progress"] = min(100.0, float(match.group(1)))


def fake(title, item_id=None, seconds=6.0):
    """A job that only advances a timer; used in mock mode."""
    job = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "item_id": item_id,
        "state": "running",
        "progress": 0.0,
        "message": "Downloading",
        "started": time.time(),
    }
    with _lock:
        _jobs[job["id"]] = job

    def tick():
        steps = 30
        for i in range(1, steps + 1):
            time.sleep(seconds / steps)
            job["progress"] = round(100.0 * i / steps, 1)
        job["state"] = "done"
        job["message"] = "Installed"

    threading.Thread(target=tick, daemon=True).start()
    return dict(job)


def all_jobs():
    with _lock:
        jobs = [dict(j) for j in _jobs.values()]
    # Drop finished jobs after a few minutes so the list stays short.
    cutoff = time.time() - 300
    return [j for j in jobs if j["state"] == "running" or j["started"] > cutoff]
