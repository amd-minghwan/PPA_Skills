"""HOBL 任务完成监控脚本。

逐 plan 等待并检查，每个 plan 完成后立即报告结果。
若某 plan 有 FAIL scenario，立即输出警告（但继续监控后续 plan）。

用法：
    python monitor.py <wait_time秒> <plan_id_1> [plan_id_2 ...]

示例：
    python monitor.py 5760 8519 8520 8521

参数：
    wait_time       总预估等待秒数（由提交脚本输出的 WAIT_TIME 值）
    plan_id_N       要监控的 PlanID 列表（按提交顺序）
"""

import urllib.request
import urllib.error
import json
import sys
import time
import argparse

POLL_INTERVAL = 300  # 5 分钟
MAX_POLLS = 12       # 每个 plan 最大额外轮询 = 12 × 300s = 60 分钟
HTTP_TIMEOUT = 30


def fetch_scenarios_data(base_url, plan_id):
    """获取 PlanID 的 ScenariosData，带超时和错误处理。"""
    try:
        resp = urllib.request.urlopen(
            f"{base_url}/plan/ScenariosData?PlanID={plan_id}",
            timeout=HTTP_TIMEOUT
        )
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"ERROR: Dashboard returned HTTP {e.code} for PlanID={plan_id}\n")
        return None
    except urllib.error.URLError as e:
        sys.stderr.write(f"ERROR: Cannot reach Dashboard — {e}\n")
        return None


def poll_until_complete(base_url, plan_id, plan_label):
    """轮询单个 PlanID 直到所有 scenario Complete，返回 (scenarios_data, timed_out)。"""
    for poll in range(MAX_POLLS):
        data = fetch_scenarios_data(base_url, plan_id)
        if data is None:
            sys.stderr.write(f"  Fetch failed, retrying next poll...\n")
            if poll < MAX_POLLS - 1:
                time.sleep(POLL_INTERVAL)
            continue

        states = [s.get("State", "") for s in data]
        completed = sum(1 for st in states if st == "Complete")
        total = len(data)

        msg = f"  [{plan_label} Poll {poll+1}/{MAX_POLLS}] {completed}/{total} complete\n"
        sys.stdout.buffer.write(msg.encode("utf-8"))
        sys.stdout.flush()

        if all(st == "Complete" for st in states):
            return data, False

        if poll < MAX_POLLS - 1:
            time.sleep(POLL_INTERVAL)

    return None, True


def report_plan_result(plan_id, scenarios):
    """输出单个 plan 的结果，返回 FAIL 数量。"""
    fails = 0
    for s in scenarios:
        status = s.get("Status", "")
        run_dir = s.get("RunDir", "")
        scenario = s.get("Scenario", "")
        line = f"  PlanID={plan_id} | {scenario} | {status} | {run_dir}\n"
        sys.stdout.buffer.write(line.encode("utf-8"))
        if status == "FAIL":
            fails += 1
    return fails


def main():
    parser = argparse.ArgumentParser(description='HOBL task monitor')
    parser.add_argument('wait_time', type=int, help='Total estimated wait seconds')
    parser.add_argument('plan_ids', nargs='+', type=int, help='PlanID list (submission order)')
    parser.add_argument('--base-url', default='http://localhost', help='Dashboard base URL')
    args = parser.parse_args()

    wait_time = args.wait_time
    plan_ids = args.plan_ids
    base_url = args.base_url
    num_plans = len(plan_ids)

    # 将总等待时间均分到每个 plan
    per_plan_wait = wait_time // num_plans if num_plans > 1 else wait_time

    total_fails = 0
    timed_out_plans = []

    sys.stdout.buffer.write(
        f"Monitoring {num_plans} plan(s), ~{per_plan_wait}s per plan\n\n".encode("utf-8")
    )
    sys.stdout.flush()

    for idx, pid in enumerate(plan_ids):
        label = f"PlanID={pid} ({idx+1}/{num_plans})"
        sys.stdout.buffer.write(f"--- {label}: waiting {per_plan_wait}s ---\n".encode("utf-8"))
        sys.stdout.flush()
        time.sleep(per_plan_wait)

        # 轮询直到该 plan 完成
        data, timed_out = poll_until_complete(base_url, pid, label)

        if timed_out:
            sys.stdout.buffer.write(
                f"  TIMEOUT: {label} did not complete after {MAX_POLLS} polls.\n".encode("utf-8")
            )
            timed_out_plans.append(pid)
            # 继续监控后续 plan（后续 plan 可能已在执行中，不应放弃）
            continue

        # 立即报告该 plan 结果
        fails = report_plan_result(pid, data)
        total_fails += fails
        if fails > 0:
            sys.stdout.buffer.write(
                f"  WARNING: PlanID={pid} has {fails} FAIL(s)!\n".encode("utf-8")
            )
        else:
            sys.stdout.buffer.write(f"  PlanID={pid}: ALL PASS\n".encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.flush()

    # 最终汇总
    sys.stdout.buffer.write(b"=== Summary ===\n")
    if timed_out_plans:
        sys.stdout.buffer.write(
            f"TIMED OUT: {timed_out_plans}. Check Dashboard manually.\n".encode("utf-8")
        )
    if total_fails > 0:
        sys.stdout.buffer.write(
            f"DONE with {total_fails} failure(s) across all plans.\n".encode("utf-8")
        )
    elif not timed_out_plans:
        sys.stdout.buffer.write(b"ALL PLANS PASS.\n")

    if timed_out_plans:
        sys.exit(1)


if __name__ == '__main__':
    main()
