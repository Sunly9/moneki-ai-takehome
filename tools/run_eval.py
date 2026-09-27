"""一键回归：起服务 → 等健康检查 → 跑公开题库 → 收服务。

    python tools/run_eval.py --out eval_reports/latest
    python tools/run_eval.py --out eval_reports/only_doc --only doc

第四关的“评测即回归”就是它：`report.json` 里的分数是机器可读的，
每次改动跑一遍就能看出分数是涨了还是跌了，涨跌一眼可见。

用 Python 而不是 shell 脚本写，是为了不踩 Windows 上
“PowerShell 按 ANSI 读无 BOM 的 UTF-8 脚本”这个坑，也方便在 macOS/Linux 上跑。
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


def venv_python() -> Path:
    """优先用 starter/.venv 里的解释器，找不到就退回当前解释器。"""
    for candidate in (STARTER / ".venv" / "Scripts" / "python.exe", STARTER / ".venv" / "bin" / "python"):
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def port_in_use(port: int) -> bool:
    """这个端口上已经有服务在监听了吗。"""
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def pick_free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def read_llm_mode(base_url: str) -> str:
    """读服务实际跑在哪个模式。分数不对时，先看这个。"""
    try:
        with urllib.request.urlopen(base_url + "/api/health", timeout=5) as response:
            return json.loads(response.read().decode("utf-8")).get("llm_mode") or "未知"
    except (urllib.error.URLError, OSError, ValueError):
        return "未知"


def wait_for_health(base_url: str, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/api/health", timeout=5) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="起服务并跑公开题库，输出分数变化")
    parser.add_argument("--out", default="eval_reports/latest", help="报告输出目录")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--only", default="", help="只跑一个类别，例如 retrieval")
    parser.add_argument("--questions", default="", help="题库文件，默认公开题库")
    parser.add_argument("--keep-server", action="store_true", help="跑完不关服务，方便继续手工调试")
    parser.add_argument(
        "--live", action="store_true",
        help="保留 LLM_* 环境变量，用真实模型跑（又慢又花钱，且同一题措辞会抖）；默认强制 mock",
    )
    args = parser.parse_args()

    python = venv_python()
    # 端口被占用时换一个空闲端口。
    # 否则本次启动的服务绑不上端口，而 `wait_for_health` 会连到那台已经在跑的
    # 服务上；那一台如果跑的是另一个模式，得到的分数就与本次代码无关。
    if port_in_use(args.port):
        fallback = pick_free_port()
        print("提示：端口 %d 已被占用，本次改用 %d（避免评测打到别人的服务上）"
              % (args.port, fallback))
        args.port = fallback

    base_url = "http://127.0.0.1:%d" % args.port
    questions = Path(args.questions) if args.questions else ROOT / "eval" / "public_questions.jsonl"

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if not args.live:
        # 回归测试**默认强制 mock**。
        # 否则只要当前环境里设过 LLM_*，评测启动的服务就会继承过去、跑成 live 模式，
        # 分数与耗时都不可比。要评 live 模式请显式加 --live。
        for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
            env.pop(key, None)

    server = subprocess.Popen(
        [str(python), "-m", "uvicorn", "kbqa.server:app", "--host", "127.0.0.1", "--port", str(args.port)],
        cwd=str(STARTER),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_for_health(base_url):
            print("服务在 40 秒内没有起来：%s/api/health" % base_url, file=sys.stderr)
            return 2

        # 把实际模式打出来。分数异常时，第一眼就能排除「跑错模式」这个可能。
        mode = read_llm_mode(base_url)
        print("服务模式：llm_mode = %s%s" % (mode, "" if args.live else "（回归测试默认强制 mock）"))
        if not args.live and mode != "mock":
            print("模式不对：期望 mock，实际 %s。评测结果不可比，已中止。" % mode, file=sys.stderr)
            return 3

        out_dir = ROOT / args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(python),
            str(ROOT / "eval" / "run_eval.py"),
            "--base-url", base_url,
            "--questions", str(questions),
            "--out", str(out_dir),
        ]
        if args.only:
            command += ["--only", args.only]
        subprocess.run(command, cwd=str(ROOT), check=False)

        report_path = out_dir / "report.json"
        if report_path.exists():
            with report_path.open(encoding="utf-8") as handle:
                report = json.load(handle)
            total = report.get("total", {})
            print()
            for name, item in (report.get("per_category") or {}).items():
                print("  %-12s %6.2f / %-6.2f  (%d/%d)" % (
                    name, item["earned"], item["points"], item["passed"], item["questions"]
                ))
            print()
            print("总分 %s / %s" % (total.get("earned"), total.get("points")))
            failed = [q["id"] for q in report.get("questions", []) if not q.get("passed")]
            print("未全绿：%s" % (" ".join(failed) or "（全部通过）"))
        print("报告：%s" % out_dir)
        return 0
    finally:
        if not args.keep_server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    sys.exit(main())
