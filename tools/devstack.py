#!/usr/bin/env python3
"""
SmartCut development stack supervisor.

Cross-platform process manager for:
- backend (FastAPI)
- worker (RQ)
- frontend (Vite)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
RUN_LOG_DIR = ROOT / ".run-logs"
CONFIG_PATH = TOOLS_DIR / "devstack_config.json"
STATE_PATH = RUN_LOG_DIR / "state.json"
PIDS_PATH = RUN_LOG_DIR / "pids.json"
SUPERVISOR_LOG = RUN_LOG_DIR / "supervisor.log"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_run_dirs() -> None:
    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)


def append_supervisor_log(message: str) -> None:
    ensure_run_dirs()
    try:
        with open(SUPERVISOR_LOG, "a", encoding="utf-8") as out:
            out.write(f"[{now_iso()}] {message}\n")
    except OSError:
        # 日志写入失败不应影响主管进程主流程
        pass


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def is_windows() -> bool:
    return os.name == "nt"


def candidate_python_paths() -> List[Path]:
    exe = "python.exe" if is_windows() else "python"
    venv_rel = Path(".venv") / ("Scripts" if is_windows() else "bin") / exe
    candidates: List[Path] = []

    current = ROOT
    for _ in range(8):
        candidates.append(current / venv_rel)
        if current.parent == current:
            break
        current = current.parent

    # project-local fallback
    candidates.append(ROOT / venv_rel)
    return candidates


def resolve_python_executable() -> str:
    for candidate in candidate_python_paths():
        if candidate.exists():
            return str(candidate)

    return sys.executable


def resolve_command_token(token: str, python_exec: str) -> str:
    if token == "{python}":
        return python_exec
    if token == "npm" and is_windows():
        return "npm.cmd"
    return token


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "smartcut-devstack"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def tcp_probe(host: str, port: int, timeout: float = 1.0) -> tuple[bool, str]:
    try:
        addr_infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return False, f"resolve failed: {exc}"

    errors: List[str] = []
    for family, socktype, proto, _, sockaddr in addr_infos:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            return True, "open"
        except OSError as exc:
            errors.append(str(exc))
        finally:
            sock.close()

    detail = " | ".join(errors[:2]) if errors else "connection failed"
    return False, detail


def tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    ok, _ = tcp_probe(host, port, timeout=timeout)
    return ok


def tail_lines(path: Path, n: int = 120) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-n:])


def stop_pid(pid: int, timeout: float = 8.0) -> None:
    if not is_pid_alive(pid):
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return

    start = time.time()
    while time.time() - start < timeout:
        if not is_pid_alive(pid):
            return
        time.sleep(0.2)

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def load_config() -> Dict[str, Any]:
    config = load_json(CONFIG_PATH, {})
    if config:
        return config

    # Safe fallback config if file missing.
    return {
        "health_poll_sec": 2,
        "restart_window_sec": 60,
        "restart_max": 5,
        "health_fail_threshold": 3,
        "services": {
            "backend": {
                "cwd": "backend",
                "cmd": [
                    "{python}",
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                "health_urls": ["http://127.0.0.1:8000/health"],
                "port": 8000,
            },
            "worker": {
                "cwd": "backend",
                "cmd": ["{python}", "-m", "app.workers.worker"],
                "health_urls": [],
                "port": None,
            },
            "frontend": {
                "cwd": "frontend",
                "cmd": ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
                "health_urls": ["http://127.0.0.1:5173/"],
                "port": 5173,
            },
        },
    }


def service_log_path(service_name: str) -> Path:
    return RUN_LOG_DIR / f"{service_name}.log"


@dataclass
class ServiceRuntime:
    name: str
    config: Dict[str, Any]
    proc: Optional[subprocess.Popen[str]] = None
    pid: Optional[int] = None
    status: str = "stopped"
    restarts: List[float] = field(default_factory=list)
    health_failures: int = 0
    last_error: str = ""

    def as_state(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "status": self.status,
            "restart_count": len(self.restarts),
            "health_failures": self.health_failures,
            "last_error": self.last_error,
            "updated_at": now_iso(),
        }


def spawn_service(service: ServiceRuntime, python_exec: str) -> None:
    cmd = [resolve_command_token(token, python_exec) for token in service.config["cmd"]]
    cwd = ROOT / service.config["cwd"]
    log_file = service_log_path(service.name)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    out = open(log_file, "a", encoding="utf-8")
    out.write(f"\n[{now_iso()}] Starting {' '.join(cmd)}\n")
    out.flush()
    append_supervisor_log(f"starting service={service.name} cmd={' '.join(cmd)}")

    kwargs: Dict[str, Any] = {
        "cwd": str(cwd),
        "stdout": out,
        "stderr": subprocess.STDOUT,
        "text": True,
    }
    if not is_windows():
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(cmd, **kwargs)
    service.proc = proc
    service.pid = proc.pid
    service.status = "running"
    service.health_failures = 0
    service.last_error = ""
    append_supervisor_log(f"service={service.name} started pid={proc.pid}")


def check_service_health(service: ServiceRuntime) -> bool:
    urls = service.config.get("health_urls", [])
    if not urls:
        return True
    return all(http_ok(url) for url in urls)


def update_runtime_files(
    runtimes: Dict[str, ServiceRuntime], supervisor_pid: int, stop_reason: str = ""
) -> None:
    state = {
        "supervisor_pid": supervisor_pid,
        "stop_reason": stop_reason,
        "updated_at": now_iso(),
        "services": {name: runtime.as_state() for name, runtime in runtimes.items()},
    }
    pids = {
        "supervisor_pid": supervisor_pid,
        "updated_at": now_iso(),
        "services": {name: runtime.pid for name, runtime in runtimes.items()},
    }
    write_json(STATE_PATH, state)
    write_json(PIDS_PATH, pids)


def run_supervisor_loop() -> int:
    ensure_run_dirs()
    config = load_config()
    python_exec = resolve_python_executable()

    poll_sec = int(config.get("health_poll_sec", 2))
    restart_window_sec = int(config.get("restart_window_sec", 60))
    restart_max = int(config.get("restart_max", 5))
    health_fail_threshold = int(config.get("health_fail_threshold", 3))

    runtimes = {
        name: ServiceRuntime(name=name, config=svc_cfg)
        for name, svc_cfg in config["services"].items()
    }

    should_stop = False
    stop_reason = ""

    append_supervisor_log("supervisor loop started")

    def _handle_signal(signum: int, _frame: Any) -> None:
        nonlocal should_stop
        nonlocal stop_reason
        should_stop = True
        try:
            signal_name = signal.Signals(signum).name
        except ValueError:
            signal_name = str(signum)
        stop_reason = f"signal:{signal_name}"
        append_supervisor_log(f"supervisor received signal {signal_name}, preparing shutdown")

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    for runtime in runtimes.values():
        spawn_service(runtime, python_exec)

    while not should_stop:
        now = time.time()

        for runtime in runtimes.values():
            if runtime.status == "crash_loop":
                continue

            if runtime.proc is None:
                spawn_service(runtime, python_exec)
                continue

            exit_code = runtime.proc.poll()
            if exit_code is not None:
                runtime.status = "restarting"
                runtime.last_error = f"exited with code {exit_code}"
                runtime.restarts = [t for t in runtime.restarts if now - t <= restart_window_sec]
                runtime.restarts.append(now)
                append_supervisor_log(
                    f"service={runtime.name} exited code={exit_code} "
                    f"restart_count={len(runtime.restarts)}"
                )

                if len(runtime.restarts) > restart_max:
                    runtime.status = "crash_loop"
                    runtime.last_error = (
                        f"restart limited: {len(runtime.restarts)} exits in "
                        f"{restart_window_sec}s"
                    )
                    runtime.proc = None
                    append_supervisor_log(
                        f"service={runtime.name} entered crash_loop "
                        f"reason={runtime.last_error}"
                    )
                    continue

                spawn_service(runtime, python_exec)
                continue

            healthy = check_service_health(runtime)
            if healthy:
                runtime.health_failures = 0
                runtime.status = "running"
                runtime.last_error = ""
            else:
                runtime.health_failures += 1
                runtime.last_error = "health check failed"
                if runtime.health_failures >= health_fail_threshold:
                    append_supervisor_log(
                        f"service={runtime.name} health failed "
                        f"{runtime.health_failures}/{health_fail_threshold}, restarting"
                    )
                    if runtime.pid:
                        stop_pid(runtime.pid)
                    runtime.status = "restarting"

        update_runtime_files(runtimes, os.getpid(), stop_reason=stop_reason)
        time.sleep(max(1, poll_sec))

    if not stop_reason:
        stop_reason = "supervisor_exit"

    append_supervisor_log(f"supervisor loop stopping reason={stop_reason}")
    for runtime in runtimes.values():
        if runtime.pid:
            stop_pid(runtime.pid)
        runtime.status = "stopped"
    update_runtime_files(runtimes, os.getpid(), stop_reason=stop_reason)
    return 0


def start_supervisor_background() -> int:
    ensure_run_dirs()
    python_exec = resolve_python_executable()

    if is_supervisor_running():
        print("devstack is already running.")
        return 0

    out = open(SUPERVISOR_LOG, "a", encoding="utf-8")
    out.write(f"\n[{now_iso()}] Starting supervisor\n")
    out.flush()

    args = [python_exec, str(Path(__file__).resolve()), "__supervise"]
    kwargs: Dict[str, Any] = {
        "cwd": str(ROOT),
        "stdout": out,
        "stderr": subprocess.STDOUT,
        "text": True,
    }
    if not is_windows():
        kwargs["start_new_session"] = True
    else:
        flags = 0
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        kwargs["creationflags"] = flags

    proc = subprocess.Popen(args, **kwargs)
    time.sleep(1.0)
    if not is_pid_alive(proc.pid):
        print("failed to start devstack supervisor. check .run-logs/supervisor.log")
        return 1

    print(f"devstack started (supervisor pid: {proc.pid})")
    return 0


def is_supervisor_running() -> bool:
    state = load_json(STATE_PATH, {})
    sup_pid = state.get("supervisor_pid")
    if isinstance(sup_pid, int) and is_pid_alive(sup_pid):
        return True
    pids = load_json(PIDS_PATH, {})
    sup_pid = pids.get("supervisor_pid")
    return isinstance(sup_pid, int) and is_pid_alive(sup_pid)


def command_down() -> int:
    config = load_config()
    pids = load_json(PIDS_PATH, {})
    state = load_json(STATE_PATH, {})

    sup_pid = pids.get("supervisor_pid") or state.get("supervisor_pid")
    append_supervisor_log("manual down requested")

    # 先停止 supervisor，避免继续拉起子进程
    if isinstance(sup_pid, int):
        stop_pid(sup_pid)
        time.sleep(0.3)

    candidate_service_pids: set[int] = set()

    for pid in pids.get("services", {}).values():
        if isinstance(pid, int):
            candidate_service_pids.add(pid)

    for svc in state.get("services", {}).values():
        pid = svc.get("pid")
        if isinstance(pid, int):
            candidate_service_pids.add(pid)

    for pid in sorted(candidate_service_pids):
        stop_pid(pid)

    stopped_state = {
        "supervisor_pid": None,
        "stop_reason": "manual_down",
        "updated_at": now_iso(),
        "services": {
            name: {
                "pid": None,
                "status": "stopped",
                "restart_count": 0,
                "health_failures": 0,
                "last_error": "",
                "updated_at": now_iso(),
            }
            for name in config["services"].keys()
        },
    }
    stopped_pids = {
        "supervisor_pid": None,
        "updated_at": now_iso(),
        "services": {name: None for name in config["services"].keys()},
    }
    write_json(STATE_PATH, stopped_state)
    write_json(PIDS_PATH, stopped_pids)

    print("devstack stopped.")
    return 0


def available_services(config: Optional[Dict[str, Any]] = None) -> List[str]:
    cfg = config if config is not None else load_config()
    services = cfg.get("services", {})
    if not isinstance(services, dict):
        return []
    return list(services.keys())


def resolve_service_pid(service: str) -> Optional[int]:
    pids = load_json(PIDS_PATH, {})
    state = load_json(STATE_PATH, {})

    pid_from_pids = pids.get("services", {}).get(service)
    if isinstance(pid_from_pids, int):
        return pid_from_pids

    pid_from_state = state.get("services", {}).get(service, {}).get("pid")
    if isinstance(pid_from_state, int):
        return pid_from_state

    return None


def command_status() -> int:
    config = load_config()
    state = load_json(STATE_PATH, {})
    svc_state = state.get("services", {})

    print(f"updated_at: {state.get('updated_at', '-')}")
    print(f"supervisor_pid: {state.get('supervisor_pid', '-')}")
    print(f"stop_reason: {state.get('stop_reason', '-')}")
    print("")
    print("SERVICE     STATUS       PID      HEALTH")
    print("-----------------------------------------------")

    for name, svc_cfg in config["services"].items():
        entry = svc_state.get(name, {})
        pid = entry.get("pid")
        status = entry.get("status", "unknown")
        pid_text = str(pid) if isinstance(pid, int) else "-"
        pid_alive = isinstance(pid, int) and is_pid_alive(pid)

        if isinstance(pid, int) and not pid_alive:
            status = "stopped"
        elif status == "unknown" and pid_alive:
            status = "running"

        health = "-"
        urls = svc_cfg.get("health_urls", [])
        if urls and pid_alive:
            health = "ok" if all(http_ok(url) for url in urls) else "fail"
        elif isinstance(pid, int):
            health = "up" if pid_alive else "down"

        print(f"{name:<11}{status:<13}{pid_text:<9}{health}")
    return 0


def command_ps() -> int:
    config = load_config()
    state = load_json(STATE_PATH, {})
    svc_state = state.get("services", {})

    print(f"updated_at: {state.get('updated_at', '-')}")
    print(f"supervisor_pid: {state.get('supervisor_pid', '-')}")
    print(f"stop_reason: {state.get('stop_reason', '-')}")
    print("")

    for name, svc_cfg in config["services"].items():
        entry = svc_state.get(name, {})
        pid = entry.get("pid")
        pid_alive = isinstance(pid, int) and is_pid_alive(pid)
        status = entry.get("status", "unknown")
        cmd_tokens = svc_cfg.get("cmd", [])
        cmd_text = " ".join(str(token) for token in cmd_tokens) if cmd_tokens else "-"

        print(f"[{name}]")
        print(f"  pid: {pid if isinstance(pid, int) else '-'}")
        print(f"  alive: {'yes' if pid_alive else 'no'}")
        print(f"  status: {status}")
        print(f"  cwd: {svc_cfg.get('cwd', '-')}")
        print(f"  cmd: {cmd_text}")
        print(f"  restart_count: {entry.get('restart_count', 0)}")
        print(f"  updated_at: {entry.get('updated_at', '-')}")
        print(f"  last_error: {entry.get('last_error', '') or '-'}")
        print("")
    return 0


def command_logs(service: Optional[str], tail: int) -> int:
    if service:
        path = service_log_path(service)
        content = tail_lines(path, tail)
        if not content:
            print(f"no logs for service: {service}")
            return 0
        print(content)
        return 0

    for path in [SUPERVISOR_LOG, service_log_path("backend"), service_log_path("worker"), service_log_path("frontend")]:
        print(f"\n===== {path.name} =====")
        content = tail_lines(path, tail)
        print(content if content else "(empty)")
    return 0


def command_doctor() -> int:
    config = load_config()
    python_exec = resolve_python_executable()

    checks: List[tuple[str, bool, str]] = []

    checks.append(("python", Path(python_exec).exists(), python_exec))
    npm_path = "npm.cmd" if is_windows() else "npm"
    npm_ok = shutil_which(npm_path) is not None
    checks.append(("npm", npm_ok, npm_path))

    redis_v4_ok, redis_v4_detail = tcp_probe("127.0.0.1", 6379, timeout=0.6)
    redis_local_ok, redis_local_detail = tcp_probe("localhost", 6379, timeout=0.6)
    redis_ok = redis_v4_ok or redis_local_ok
    if redis_ok:
        redis_info = "reachable"
    else:
        redis_info = (
            f"127.0.0.1={redis_v4_detail}; "
            f"localhost={redis_local_detail}"
        )
    checks.append(("redis:6379", redis_ok, redis_info))

    for name, svc_cfg in config["services"].items():
        port = svc_cfg.get("port")
        if isinstance(port, int):
            open_ok, open_detail = tcp_probe("127.0.0.1", port, timeout=0.5)
            checks.append(
                (
                    f"{name}-port:{port}",
                    open_ok,
                    "open" if open_ok else open_detail,
                )
            )

    # Known app endpoints
    checks.append(("backend-health", http_ok("http://127.0.0.1:8000/health"), "/health"))
    checks.append(("frontend-home", http_ok("http://127.0.0.1:5173/"), "/"))
    checks.append(("frontend-proxy", http_ok("http://127.0.0.1:5173/api/tasks"), "/api/tasks"))

    width = max(len(name) for name, _, _ in checks) + 2
    failures = 0
    for name, ok, info in checks:
        state = "OK " if ok else "FAIL"
        print(f"{name:<{width}} {state}  {info}")
        if not ok:
            failures += 1

    return 0 if failures == 0 else 1


def shutil_which(cmd: str) -> Optional[str]:
    from shutil import which

    return which(cmd)


def command_restart(service: Optional[str]) -> int:
    if not service:
        code = command_down()
        if code != 0:
            return code
        return start_supervisor_background()

    config = load_config()
    services = available_services(config)
    if service not in services:
        print(f"unknown service: {service}")
        print(f"available services: {', '.join(services)}")
        return 1

    if not is_supervisor_running():
        print("devstack supervisor is not running. run `python tools/devstack.py up` first.")
        return 1

    pid = resolve_service_pid(service)
    if isinstance(pid, int) and is_pid_alive(pid):
        print(f"restarting service: {service} (pid: {pid})")
        stop_pid(pid)
    else:
        print(f"service {service} has no active pid in state, waiting for supervisor recovery.")

    deadline = time.time() + 12.0
    while time.time() < deadline:
        new_pid = resolve_service_pid(service)
        if isinstance(new_pid, int) and is_pid_alive(new_pid):
            if not isinstance(pid, int) or new_pid != pid:
                print(f"service {service} is running (pid: {new_pid})")
                return 0
        time.sleep(0.5)

    print(f"service {service} restart timed out. run status/logs for details.")
    return 1


def command_restart_all() -> int:
    code = command_down()
    if code != 0:
        return code
    return start_supervisor_background()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SmartCut devstack supervisor")
    sub = parser.add_subparsers(dest="command", required=True)
    services = available_services()
    services_text = "/".join(services) if services else "backend/frontend/worker"

    sub.add_parser("up", help="start stack supervisor in background")
    sub.add_parser("down", help="stop stack and supervisor")
    p_restart = sub.add_parser("restart", help="restart stack or one service")
    p_restart.add_argument("service", nargs="?", choices=services, help=services_text)
    sub.add_parser("ps", help="show detailed service state")
    sub.add_parser("status", help="show stack status")
    sub.add_parser("doctor", help="run environment/health checks")
    sub.add_parser("__supervise", help=argparse.SUPPRESS)

    p_logs = sub.add_parser("logs", help="show logs")
    p_logs.add_argument("service", nargs="?", choices=services, help=services_text)
    p_logs.add_argument("--tail", type=int, default=120, help="tail line count")

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    ensure_run_dirs()
    args = parse_args(argv)

    if args.command == "__supervise":
        return run_supervisor_loop()
    if args.command == "up":
        return start_supervisor_background()
    if args.command == "down":
        return command_down()
    if args.command == "restart":
        if args.service:
            return command_restart(args.service)
        return command_restart_all()
    if args.command == "ps":
        return command_ps()
    if args.command == "status":
        return command_status()
    if args.command == "doctor":
        return command_doctor()
    if args.command == "logs":
        return command_logs(args.service, args.tail)

    return 1


if __name__ == "__main__":
    sys.exit(main())
