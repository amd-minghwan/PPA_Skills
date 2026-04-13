"""HOBL 任务完成监控脚本。

等待预估执行时间后轮询最后一个 PlanID，完成后输出所有 PlanID 的 RunDir。

用法：
    python monitor.py <wait_time秒> <plan_id_1> [plan_id_2 ...]

示例：
    python monitor.py 5760 8519 8520 8521

参数：
    wait_time       首次检查前的等待秒数（由 Agent 按 §5 公式计算）
    plan_id_N       要监控的 PlanID 列表，最后一个用于轮询判断完成
"""

import urllib.request
import json
import sys
import time
import argparse

POLL_INTERVAL = 300  # 5 分钟
MAX_POLLS = 5


def main():
    parser = argparse.ArgumentParser(description='HOBL task monitor')
    parser.add_argument('wait_time', type=int, help='Seconds to wait before first check')
    parser.add_argument('plan_ids', nargs='+', type=int, help='PlanID list, last one used for polling')
    parser.add_argument('--base-url', default='http://localhost', help='Dashboard base URL')
    args = parser.parse_args()

    wait_time = args.wait_time
    plan_ids = args.plan_ids
    base_url = args.base_url
    last_plan_id = plan_ids[-1]

    w = f"Waiting {wait_time}s before first check...\n"
    sys.stdout.buffer.write(w.encode("utf-8"))
    sys.stdout.flush()
    time.sleep(wait_time)

    # 轮询最后一个 PlanID 直到完成
    done = False
    for poll in range(MAX_POLLS):
        resp = urllib.request.urlopen(
            f"{base_url}/plan/ScenariosData?PlanID={last_plan_id}"
        )
        data = json.loads(resp.read().decode())
        states = [s.get("State", "") for s in data]
        completed = sum(1 for st in states if st == "Complete")
        total = len(data)

        msg = f"[Poll {poll+1}/{MAX_POLLS}] PlanID={last_plan_id}: {completed}/{total} complete\n"
        sys.stdout.buffer.write(msg.encode("utf-8"))
        sys.stdout.flush()

        if all(st == "Complete" for st in states):
            done = True
            break

        if poll < MAX_POLLS - 1:
            time.sleep(POLL_INTERVAL)

    if not done:
        sys.stdout.buffer.write(b"TIMEOUT after 5 polls. Check Dashboard manually.\n")
        sys.exit(1)

    # 完成：收集所有 PlanID 的 RunDir
    sys.stdout.buffer.write(b"\n=== All RunDir paths ===\n")
    for pid in plan_ids:
        resp = urllib.request.urlopen(
            f"{base_url}/plan/ScenariosData?PlanID={pid}"
        )
        scenarios = json.loads(resp.read().decode())
        for s in scenarios:
            status = s.get("Status", "")
            run_dir = s.get("RunDir", "")
            scenario = s.get("Scenario", "")
            line = f"PlanID={pid} | {scenario} | {status} | {run_dir}\n"
            sys.stdout.buffer.write(line.encode("utf-8"))

    fails = 0
    for pid in plan_ids:
        resp = urllib.request.urlopen(
            f"{base_url}/plan/ScenariosData?PlanID={pid}"
        )
        for s in json.loads(resp.read().decode()):
            if s.get("Status") == "FAIL":
                fails += 1

    if fails > 0:
        msg = f"\nDONE with {fails} failure(s). Consider running failure-analyzer.\n"
        sys.stdout.buffer.write(msg.encode("utf-8"))
    else:
        sys.stdout.buffer.write(b"\nALL PASS.\n")


if __name__ == '__main__':
    main()
