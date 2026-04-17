"""HOBL testplan 模板转换 + 多轮提交脚本。

读取 testplan JSON，转换为 Dashboard API payload，按队列提交 N 轮。

用法：
    python template_submit.py <testplan_json> <profile> <rounds>

示例：
    python template_submit.py "c:\\hobl\\testplans\\amd_hobl_prep.json" HPT1 3

参数：
    testplan_json   testplan JSON 文件路径
    profile         Profile 名称（不含 .ini）
    rounds          提交轮次数
"""

import json
import sys
import time
import os

# Ensure sibling module is importable regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from submit import submit_to_dashboard, SubmitError, SETUP_OVERHEAD, DEFAULT_DURATION


def main():
    import argparse
    parser = argparse.ArgumentParser(description='HOBL testplan template submit')
    parser.add_argument('testplan_json', help='testplan JSON file path')
    parser.add_argument('profile', help='Profile name (without .ini)')
    parser.add_argument('rounds', type=int, help='Number of rounds')
    parser.add_argument('--base-url', default='http://localhost', help='Dashboard base URL')
    args = parser.parse_args()

    testplan_path = args.testplan_json
    profile = args.profile
    rounds = args.rounds
    base_url = args.base_url

    if rounds < 1:
        sys.stderr.write("ERROR: rounds must be >= 1.\n")
        sys.exit(1)

    # 读模板
    try:
        with open(testplan_path, 'r', encoding='utf-8') as f:
            tpl = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"ERROR: Cannot read testplan file — {e}\n")
        sys.exit(1)

    # 提取 Meta 字段（模板顶层 → 注入第 0 行）
    study_vars = tpl.get("StudyVars", {})
    plan_based_study_vars = tpl.get("PlanBasedStudyVars", [])
    study_type = tpl.get("StudyType", "")
    auto_resubmit = tpl.get("AutoResubmit", 0)
    check_preps = tpl.get("CheckPreps", False)

    # 构造 planRows（类型转换：Enabled bool→str, Iterations int→str, Meta 仅第 0 行）
    plan_rows = []
    num_enabled = 0
    max_iterations = 1
    for i, s in enumerate(tpl["Scenarios"]):
        enabled = s.get("Enabled", True)
        iters = s.get("Iterations", 1)
        row = {
            "Seq": i,
            "Enabled": "1" if enabled else "0",
            "Scenario": s["Scenario"],
            "Expand": s.get("Expand", []),
            "Tools": [],
            "Parameters": s.get("Parameters", ""),
            "Iterations": str(iters)
        }
        if i == 0:
            row["Meta"] = {
                "StudyVars": study_vars,
                "PlanBasedStudyVars": plan_based_study_vars,
                "StudyType": study_type,
                "AutoResubmit": auto_resubmit,
                "CheckPreps": check_preps
            }
        plan_rows.append(row)
        if enabled:
            num_enabled += 1
            max_iterations = max(max_iterations, int(iters))

    if num_enabled == 0:
        sys.stderr.write("ERROR: No enabled scenarios found in testplan.\n")
        sys.exit(1)

    # 多轮提交
    tpl_stem = os.path.splitext(os.path.basename(testplan_path))[0]
    plan_ids = []

    for r in range(1, rounds + 1):
        plan_name = f"[{tpl_stem}] Round {r}/{rounds}"
        try:
            result = submit_to_dashboard(
                plan_rows=plan_rows,
                profile=profile,
                plan_name=plan_name,
                study_type=study_type,
                base_url=base_url
            )
        except SubmitError:
            sys.stderr.write(f"ERROR: Round {r}/{rounds} submission failed. Aborting.\n")
            sys.exit(1)
        pid = result.get('redirectToUrl', '').split('PlanID=')[-1]
        if not pid:
            sys.stderr.write(f"ERROR: Round {r}/{rounds} no PlanID returned. Aborting.\n")
            sys.exit(1)
        plan_ids.append(pid)
        sys.stdout.buffer.write(f"Round {r}/{rounds}: PlanID={pid}\n".encode("utf-8"))
        if r < rounds:
            time.sleep(1)

    sys.stdout.buffer.write(f"\nAll PlanIDs: {plan_ids}\n".encode("utf-8"))
    sys.stdout.buffer.write(f"Monitor last: PlanID={plan_ids[-1]}\n".encode("utf-8"))

    # 输出 WAIT_TIME 供 monitor.py 使用
    wt = rounds * num_enabled * (SETUP_OVERHEAD + DEFAULT_DURATION) * max_iterations
    sys.stdout.buffer.write(f"WAIT_TIME={wt}\n".encode("utf-8"))


if __name__ == '__main__':
    main()
