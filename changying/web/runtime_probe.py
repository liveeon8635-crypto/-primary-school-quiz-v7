"""Runtime facts exposed by the public health endpoint.

上课时如果整站突然返回 502，只有两种情况：进程重启过（崩溃/被平台拉起），
或者进程还活着但一时无法响应。`/health` 之前只回 `{"status": "ok"}`，事后无法
区分这两者。这里补上进程启动时间、运行时长、pid 和常驻内存（Linux 上可读
/proc），下次再出现同样的现象就能直接判断是不是重启过、内存是不是被吃满。
"""

import os
import time
from datetime import datetime, timezone

_PROCESS_STARTED = time.time()


def _resident_mb():
    """Return RSS in MB when the platform exposes it (/proc), else None."""
    try:
        with open("/proc/self/status", "r", encoding="ascii", errors="ignore") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except (OSError, ValueError, IndexError):
        return None
    return None


def runtime_snapshot():
    """Small JSON-safe dict describing the current process."""
    snapshot = {
        "uptimeSeconds": int(max(0, time.time() - _PROCESS_STARTED)),
        "startedAt": datetime.fromtimestamp(_PROCESS_STARTED, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pid": os.getpid(),
    }
    resident = _resident_mb()
    if resident is not None:
        snapshot["rssMB"] = resident
    return snapshot


def install_runtime_health(app):
    """Expose /health/runtime next to the fast /health probe."""

    @app.get("/health/runtime")
    def health_runtime():
        payload = {"status": "ok"}
        payload.update(runtime_snapshot())
        return payload

    return app
