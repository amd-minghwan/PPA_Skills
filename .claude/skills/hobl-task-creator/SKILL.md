---
name: hobl-task-creator
description: >
    HOBL 任务创建与提交的唯一入口。用户要运行任何 HOBL scenario（idle、teams、lvp、web、cinebench 等）时使用此 skill。
    支持 ad-hoc 提交和按 testplan JSON 模板多轮提交。通过 Dashboard REST API 提交任务并监控执行结果。
    触发词：提交任务、跑测试、用模板跑、testplan、多轮、round、run、submit、execute、create plan、batch submit、批量跑。
compatibility:
    platform: windows
metadata:
    version: "6.0.0"
    category: testing
    tags: ["hobl", "task", "creator", "dashboard", "api", "job", "submit", "plan", "scenario", "template", "testplan", "round", "batch"]
---

# HOBL Task Creator Skill

## §0 入口判断

收到用户请求后，按以下规则选择模式：

1. 用户提到 **testplan / 模板 / JSON 文件** → **§4B 模板模式**
2. 否则 → **§4 Ad-hoc 模式**
3. 两种模式都先执行 **§2**（Scenario 发现）和 **§3**（Profile 发现）

### 安全护栏

- **Ad-hoc**：`iterations > 10` 时，先向用户确认再提交
- **模板**：`rounds > 5` 时，先向用户确认再提交
- 原因：提交即执行（§7.2），不可撤销，大量提交会占用硬件资源

---

## §1 API 概览

| API | 方法 | 说明 |
|-----|------|------|
| `POST /plan/Create` | POST JSON | **提交新任务**（核心） |
| `GET /plan/ScenariosData?PlanID=<id>` | GET | 获取 Plan scenarios 详情（monitor.py 使用） |

**Base URL**：`http://localhost`（Dashboard 默认运行在本机）

> 其他端点（`/plan/Plans`、`/plan/Scenarios`、`/plan/ScenarioType`）仅供手动查询，自动化流程不使用。

---

## §2 Scenario 发现

在构造提交请求之前，先确认用户要跑的 scenario 名称是否存在。

### 快捷别名

用户使用以下关键词时，**直接使用对应 scenario，跳过搜索步骤**：

| 用户关键词 | Scenario 名称 |
|---|---|
| `idle` | `amd_idle_desktop` |
| `lvp` | `amd_lvp_4KPeru` |
| `teams` | `amd_teams2_3x3v` |
| `web` / `cerweb` | `amd_cer_web_2` |
| `mm30` | `amd_MobileMark30` |

映射之外的 scenario，走下方的搜索验证流程。

### 列出可用 scenario

扫描 `scenarios/windows/` 目录下的 `.py` 文件（去掉 `.py` 后缀即为 scenario 名称）：

```powershell
Get-ChildItem c:\hobl\scenarios\windows\*.py | ForEach-Object { $_.BaseName }
```

### 按关键词搜索 scenario

```powershell
Get-ChildItem c:\hobl\scenarios\windows\*.py | Where-Object { $_.BaseName -match '<关键词>' } | ForEach-Object { $_.BaseName }
```

将 `<关键词>` 替换为用户描述中提取的词（如 `teams`、`cinebench`、`idle`、`youtube`、`web`、`lvp`）。
如果搜不到，向用户确认名称，不要猜测。

---

## §3 Profile 发现

Profile 决定目标设备配置。**必须使用 Dashboard 中已注册的 profile**，而非文件系统中的 `.ini` 文件。

列出 Dashboard 已注册 profile：

```powershell
python .claude/skills/hobl-task-creator/scripts/list_profiles.py [--base-url URL]
```

输出示例：

```
HPT1_FP8_HOBL_Teams  (DUT: HPT1-DUT)
BIRMAN_HOBL_for_idle  (DUT: BIRMAN-01)
```

第一个空格前的 token 即为 `--profile` 参数值。

> **重要**：`c:\profiles\*.ini` 中的文件不一定在 Dashboard 注册。使用未注册 profile 提交后，API 返回成功但 plan 不会出现在 Plans 页面，也无法被正确调度。

### Profile 选择规则

| 模式 | 用户已指定 | 未指定 + 单 profile | 未指定 + 多 profile |
|------|-----------|-------------------|-------------------|
| Ad-hoc | 使用用户指定 | 使用该唯一 profile | 列出让用户选（fallback: `default`）|
| 模板 | 使用用户指定 | 列出让用户确认 | 列出让用户选（无 fallback）|

模板模式不使用默认 profile（原因：模板通常面向远程 DUT，错用 local 会浪费整轮执行）。

- Profile 名称**不含** `.ini` 后缀
- 若 `list_profiles.py` 执行失败（Dashboard 不通或页面结构变化），提示用户手动输入 profile 名称

---

## §4 提交任务 — Ad-hoc 模式

### 提交脚本

路径：`.claude/skills/hobl-task-creator/scripts/submit.py`

```powershell
python .claude/skills/hobl-task-creator/scripts/submit.py <scenario1> [scenario2 ...] [options]
```

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `scenarios` (positional) | 是 | - | Scenario 名称，多个用空格分隔 |
| `--profile` | 否 | `default` | Profile 名称（不含 .ini） |
| `--iterations` | 否 | `1` | 迭代次数（字符串） |
| `--parameters` | 否 | `''` | 格式 `module:key=value`，分隔符 `:` 不是 `.`，多个用空格分隔 |
| `--plan-name` | 否 | `[Custom]` | Plan 显示名称 |
| `--auto-resubmit` | 否 | `0` | 自动重提交次数 |
| `--check-preps` | 否 | 不启用 | 启用 prep 检查（flag） |
| `--study-type` | 否 | `''` | Study 类型 |
| `--base-url` | 否 | `http://localhost` | Dashboard 地址 |

### 使用示例

**单个 scenario**：

```powershell
python .claude/skills/hobl-task-creator/scripts/submit.py amd_idle_desktop
```

**多个 scenario（含 prep）**：

```powershell
python .claude/skills/hobl-task-creator/scripts/submit.py amd_cinebench_prep amd_cinebench_nt amd_cinebench_1t --plan-name "Cinebench Suite"
```

**多次迭代 + 自定义参数**：

```powershell
python .claude/skills/hobl-task-creator/scripts/submit.py amd_idle_desktop --profile HPT1 --iterations 6 --parameters "amd_idle_desktop:duration=10" --plan-name "Idle Task - Duration 10s x6"
```

### 成功响应示例

```
OK PlanID=8519
{"status":"ok","redirectToUrl":"/plan/Scenarios?PlanID=8519"}
WAIT_TIME=2880
```

提交成功后，从输出提取 `PlanID` 和 `WAIT_TIME`，按 §5 启动监控。

---

## §4B 模板提交 — 按 testplan JSON 多轮执行

当用户要求"按模板跑"、"用 xxx testplan 跑 N 轮"时，使用本节流程。

### §4B.1 模板发现

列出可用模板：

```powershell
Get-ChildItem c:\hobl\testplans\*.json | ForEach-Object { $_.Name }
```

用户选定后，读取 JSON 展示摘要（scenario 数量、Enabled 数量、StudyType）供确认。

### §4B.2 交互流程

```
1. 用户说"用 xxx 模板跑 N 轮"
2. Agent 在 testplans/*.json 中查找匹配文件
   - 找到 → 读取并展示 scenario 列表摘要
   - 未找到 → 列出所有 .json 文件让用户选
3. 确认 profile（按 §3 Profile 选择规则）
4. 确认轮次数 N（默认 1）
5. 执行转换脚本，按队列提交 N 轮（1 秒间隔）
6. 输出所有 PlanID，从脚本输出提取 WAIT_TIME，在后台终端启动监控并传入**所有** PlanID
```

### §4B.3 转换与提交脚本

路径：`.claude/skills/hobl-task-creator/scripts/template_submit.py`

```powershell
python .claude/skills/hobl-task-creator/scripts/template_submit.py <testplan_json> <profile> <rounds> [--base-url URL]
```

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `testplan_json` | 是 | - | testplan JSON 文件路径 |
| `profile` | 是 | - | Profile 名称（不含 .ini） |
| `rounds` | 是 | - | 提交轮次数 |
| `--base-url` | 否 | `http://localhost` | Dashboard 地址 |

示例：

```powershell
python .claude/skills/hobl-task-creator/scripts/template_submit.py "c:\hobl\testplans\amd_hobl_prep.json" HPT1 3
```

脚本自动完成：读取 JSON → 构造 planRows（类型转换 Enabled bool→str, Iterations int→str, Meta 仅第 0 行）→ 按队列多轮提交（1 秒间隔）→ 输出所有 PlanID。

提交成功后，按 §5 启动监控。

---

## §5 完成监控

Ad-hoc 和模板提交共用本节流程。提交成功拿到 PlanID 后，**在后台终端中运行**（`mode=async`）监控脚本。

路径：`.claude/skills/hobl-task-creator/scripts/monitor.py`

```powershell
python .claude/skills/hobl-task-creator/scripts/monitor.py <wait_time秒> <plan_id_1> [plan_id_2 ...] [--base-url URL]
```

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `wait_time` | 是 | - | 总预估等待秒数（从提交脚本输出的 `WAIT_TIME=<seconds>` 提取） |
| `plan_id_N` | 是 | - | 要监控的 PlanID 列表（按提交顺序） |
| `--base-url` | 否 | `http://localhost` | Dashboard 地址 |

示例：

```powershell
python .claude/skills/hobl-task-creator/scripts/monitor.py 5760 8519 8520 8521
```

### 逐 plan 监控机制

脚本将 `wait_time` 均分到每个 plan（`per_plan_wait = wait_time / N`），然后**逐个 plan** 依序执行：

1. sleep `per_plan_wait` 秒
2. 轮询该 PlanID 直到所有 scenario `State=="Complete"`（最多 12 次，每次间隔 300s）
3. **立即输出该 plan 的结果**（RunDir + Status）
4. 若有 FAIL scenario，**立即输出 WARNING**
5. 继续监控下一个 plan

> 优势：3 轮任务各 3600s 时，第一轮完成后（~3600s）即可发现 FAIL，无需等待全部 10800s。

> Dashboard 中 `State` 表示执行阶段（Queued / Running / Complete），`Status` 表示执行结果（PASS / FAIL）。monitor.py 用 `State=="Complete"` 判断结束，用 `Status=="FAIL"` 统计失败。

---

## §6 wait_time 获取

提交脚本（`submit.py` / `template_submit.py`）在成功提交后会自动输出 `WAIT_TIME=<seconds>`。Agent 从脚本输出中提取该值，直接传给 §5 监控脚本，**无需手动计算**。

### 内部计算公式（仅供参考）

脚本内部按以下公式估算 wait_time：

**Ad-hoc 模式**：`num_scenarios × (setup_overhead + duration) × iterations`

**模板模式**：`rounds × num_enabled_rows × (setup_overhead + duration) × max_iterations`

| 常量 | 值 | 说明 |
|---|---|---|
| `setup_overhead` | 180s | 每个 scenario 的 HOBL 框架初始化开销，与 prep scenario 无关 |
| `duration` | 300s | scenario 默认执行时长。Ad-hoc 模式下若 parameters 中有 `duration=N`，取该值 |

> 宁可高估也不低估。高估只是 monitor 多等一会，低估会导致轮询窗口覆盖不到实际完成时间。

---

## §7 注意事项

1. **Dashboard 必须运行**：确保 Dashboard 地址可访问（默认 `http://localhost`，远程时用 `--base-url` 指定），否则所有 API 调用失败
2. **提交即执行**：`/plan/Create` 创建计划后，Dashboard 自动调度执行，无需额外触发
3. **必须通过 Dashboard 提交**：直接 `python hobl.py` 不会上报结果到 Web
4. **Prep scenario 放前面**：如 `amd_cinebench_prep` → `amd_cinebench_nt`
5. **多笔 nidata 用 `Iterations`**：`Iterations='6'` → 6 个独立 RunDir，不要用 `repeat=N` 参数替代
6. **Parameters 格式**：`module:key=value`，分隔符是 `:` 不是 `.`，多个参数用**空格**分隔
7. **Meta 仅第 0 行需要，其余行不传**
8. **模板 JSON 中 `Command` 字段被忽略**：API 不需要此字段，转换时直接跳过
9. **模板提交的 profile**：testplan JSON 中不含 profile 信息，必须由用户在调用时显式指定（见 §3 Profile 选择规则）
10. **Expand 与 StudyVars**：`Expand` 非空时表示该 scenario 行会在 Dashboard 端按 `StudyVars` 定义展开为多行。实际执行行数 = Scenarios 条数 × 展开组合数。Agent 原样透传 `Expand` 和 `StudyVars`，无需自行计算展开结果

### 错误恢复

| 错误场景 | Agent 行为 |
|---|---|
| Dashboard 不可达（脚本输出 `ERROR: Cannot connect`） | 提示用户确认 Dashboard 是否运行，确认 `--base-url` 是否正确 |
| `list_profiles.py` 返回 0 个 profile 或解析失败 | 提示用户手动输入 profile 名称（Dashboard 页面结构可能已变化） |
| Monitor timeout（脚本 exit code 1） | 提示用户在 Dashboard 网页上手动检查 Plan 状态 |
| 提交失败（脚本输出 `ERROR`） | 显示错误信息，不启动 monitor |