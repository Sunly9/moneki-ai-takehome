"""跑 eval/llm_gateway.py preflight 接入预检。

预检本身是交互式的：它先起一个假 DeepSeek 服务、打印三个环境变量、
等你用这三个变量重启服务、再回车继续。手工做这一步很容易出错，
这里把它自动化：

1. 挑一个空闲端口，用 `--port` 让假服务的地址变成可预测的
   `http://127.0.0.1:<port>/ds-gw`；
2. `eval/llm_gateway.py` 里的 `--model` / `--api-key` 都是有固定默认值的
   命令行参数（不是随机生成的），所以三个环境变量的值在启动之前就能确定；
3. 先用这三个变量把服务起起来，确认 `/api/health` 报 `llm_mode: "live"`；
4. 再跑 `preflight --no-wait`，让预检直接开始驱动 `/api/chat`。

用法：
    python tools/run_preflight.py
    python tools/run_preflight.py --out eval_reports
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STARTER = ROOT / "starter"

#: 与 eval/llm_gateway.py 里的默认值保持一致；它们可以通过命令行覆盖，
#: 这里显式传进去，避免依赖“默认值不会变”。
FAKE_MODEL = "preflight-model-7f3a"
FAKE_API_KEY = "preflight-key-3b9c1f"
FAKE_PREFIX = "/ds-gw"


def venv_python() -> Path:
    for candidate in (STARTER / ".venv" / "Scripts" / "python.exe", STARTER / ".venv" / "bin" / "python"):
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for_health(base_url: str, timeout: float = 40.0, expect_live: bool = True):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/api/health", timeout=5) as response:
                last = json.loads(response.read().decode("utf-8"))
                if not expect_live or last.get("llm_mode") == "live":
                    return last
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(0.4)
    return last


def main() -> int:
    parser = argparse.ArgumentParser(description="自动化跑 LLM 接入预检")
    parser.add_argument("--service-port", type=int, default=8010)
    parser.add_argument("--out", default="eval_reports", help="预检报告输出目录")
    parser.add_argument("--scenarios", default="", help="只跑其中几个场景，逗号分隔")
    args = parser.parse_args()

    python = venv_python()
    gateway_port = free_port()
    base_url = "http://127.0.0.1:%d" % args.service_port
    llm_base_url = "http://127.0.0.1:%d%s" % (gateway_port, FAKE_PREFIX)

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["LLM_BASE_URL"] = llm_base_url
    env["LLM_API_KEY"] = FAKE_API_KEY
    env["LLM_MODEL"] = FAKE_MODEL

    print("假模型地址：%s" % llm_base_url)
    print("  LLM_BASE_URL=%s" % llm_base_url)
    print("  LLM_API_KEY=%s" % FAKE_API_KEY)
    print("  LLM_MODEL=%s" % FAKE_MODEL)
    print()

    server = subprocess.Popen(
        [str(python), "-m", "uvicorn", "kbqa.server:app",
         "--host", "127.0.0.1", "--port", str(args.service_port)],
        cwd=str(STARTER), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        health = wait_for_health(base_url, expect_live=True)
        if not health or health.get("llm_mode") != "live":
            print("服务没有进入 live 模式，/api/health = %s" % json.dumps(health, ensure_ascii=False), file=sys.stderr)
            return 2
        print("服务已进入 live 模式：llm_mode=%s kb_docs=%s" % (health.get("llm_mode"), health.get("kb_docs")))
        print()

        out_dir = ROOT / args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(python), str(ROOT / "eval" / "llm_gateway.py"), "preflight",
            "--service-url", base_url,
            "--port", str(gateway_port),
            "--model", FAKE_MODEL,
            "--api-key", FAKE_API_KEY,
            "--prefix", FAKE_PREFIX,
            "--out", str(out_dir),
            "--no-wait",
        ]
        if args.scenarios:
            command += ["--scenarios", args.scenarios]
        result = subprocess.run(command, cwd=str(ROOT), env=env)
        print()
        print("预检报告：%s" % (out_dir / "preflight_report.md"))
        return result.returncode
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    sys.exit(main())
