"""HOBL Dashboard 任务提交脚本。

用法（ad-hoc 模式）：
    python submit.py <scenario1> [scenario2 ...] [options]

选项：
    --profile NAME        Profile 名称（默认 default）
    --iterations N        迭代次数（默认 1）
    --parameters PARAMS   参数，格式 module:key=value，多个用空格分隔
    --plan-name NAME      Plan 显示名称（默认 [Custom]）
    --auto-resubmit N     自动重提交次数（默认 0）
    --check-preps         启用 prep 检查
    --study-type TYPE     Study 类型
    --base-url URL        Dashboard 地址（默认 http://localhost）

示例：
    python submit.py amd_idle_desktop
    python submit.py amd_idle_desktop --profile HPT1 --iterations 6
    python submit.py amd_cinebench_prep amd_cinebench_nt --plan-name "Cinebench Suite"
    python submit.py amd_idle_desktop --iterations 6 --parameters "amd_idle_desktop:duration=10"
"""

import urllib.request
import urllib.error
import json
import sys
import re
import argparse

HTTP_TIMEOUT = 30

# wait_time 估算常量
SETUP_OVERHEAD = 180   # 每个 scenario 的 HOBL 框架初始化开销（秒）
DEFAULT_DURATION = 300  # scenario 默认执行时长（秒）


class SubmitError(Exception):
    """提交失败时抛出，供 template_submit.py 等调用方捕获。"""
    pass


def calc_wait_time(num_scenarios, iterations, parameters=''):
    """根据提交参数计算预估 wait_time（秒）。

    公式：num_scenarios × (SETUP_OVERHEAD + duration) × iterations
    duration 从 parameters 中提取（任意 scenario 的 duration= 取最大值），默认 300。
    """
    duration = DEFAULT_DURATION
    if parameters:
        matches = re.findall(r':duration=(\d+)', parameters)
        if matches:
            duration = max(int(m) for m in matches)
    return num_scenarios * (SETUP_OVERHEAD + duration) * int(iterations)


def submit_to_dashboard(scenarios=None, plan_rows=None, profile='default',
                        plan_name='[Custom]', iterations='1', parameters='',
                        auto_resubmit=0, check_preps=False, study_type='',
                        base_url='http://localhost'):
    """提交任务到 Dashboard。

    两种用法：
    - Ad-hoc：传入 scenarios（名称列表），自动构造 planRows
    - Template：传入预构造的 plan_rows，直接提交

    关键约束：
    - iterations 必须是字符串（如 '6'），不是 int
    - parameters 格式为 'module:key=value'，分隔符是 : 不是 .，多个参数用空格分隔
    """
    if plan_rows is None:
        plan_rows = []
        for i, s in enumerate(scenarios):
            row = {
                'Seq': i,
                'Enabled': '1',
                'Scenario': s,
                'Expand': [],
                'Tools': [],
                'Parameters': parameters,
                'Iterations': iterations,
            }
            if i == 0:
                row['Meta'] = {
                    'StudyVars': {},
                    'PlanBasedStudyVars': [],
                    'StudyType': study_type,
                    'AutoResubmit': auto_resubmit,
                    'CheckPreps': check_preps
                }
            plan_rows.append(row)

    payload = json.dumps({
        'profile': profile,
        'planName': plan_name,
        'planRows': plan_rows,
        'studyType': study_type
    }).encode('utf-8')

    req = urllib.request.Request(
        f'{base_url}/plan/Create',
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
    except urllib.error.HTTPError as e:
        msg = f"ERROR: Dashboard returned HTTP {e.code} — {e.reason}"
        sys.stderr.write(msg + "\n")
        raise SubmitError(msg)
    except urllib.error.URLError as e:
        msg = f"ERROR: Cannot connect to Dashboard at {base_url} — {e}"
        sys.stderr.write(msg + "\n")
        raise SubmitError(msg)

    result = json.loads(resp.read().decode())
    plan_id = result.get('redirectToUrl', '').split('PlanID=')[-1]

    if not plan_id:
        msg = f"ERROR: Unexpected response, no PlanID found: {result}"
        sys.stderr.write(msg + "\n")
        raise SubmitError(msg)

    sys.stdout.buffer.write(f"OK PlanID={plan_id}\n".encode('utf-8'))
    sys.stdout.buffer.write(json.dumps(result).encode('utf-8'))
    sys.stdout.buffer.write(b'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Submit ad-hoc task to HOBL Dashboard')
    parser.add_argument('scenarios', nargs='+', help='Scenario names')
    parser.add_argument('--profile', default='default')
    parser.add_argument('--iterations', default='1')
    parser.add_argument('--parameters', default='')
    parser.add_argument('--plan-name', default='[Custom]')
    parser.add_argument('--auto-resubmit', type=int, default=0)
    parser.add_argument('--check-preps', action='store_true')
    parser.add_argument('--study-type', default='')
    parser.add_argument('--base-url', default='http://localhost')

    args = parser.parse_args()
    try:
        submit_to_dashboard(
            scenarios=args.scenarios,
            profile=args.profile,
            iterations=args.iterations,
            parameters=args.parameters,
            plan_name=args.plan_name,
            auto_resubmit=args.auto_resubmit,
            check_preps=args.check_preps,
            study_type=args.study_type,
            base_url=args.base_url,
        )
    except SubmitError:
        sys.exit(1)

    # 输出 WAIT_TIME 供 monitor.py 使用
    wt = calc_wait_time(len(args.scenarios), args.iterations, args.parameters)
    sys.stdout.buffer.write(f"WAIT_TIME={wt}\n".encode('utf-8'))
