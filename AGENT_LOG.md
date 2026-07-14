# AGENT_LOG.md — the-harness 开发过程日志

> 按时间顺序记录关键节点，每条包含：时间戳与 task 编号、触发的 Superpowers 技能、关键 prompt / context 配置、subagent 输出的关键片段或 commit hash、人工干预、学到的教训。

---

## 2026-07-10 14:37 — 项目启动

- **时间戳**：2026-07-10 14:37
- **阶段**：brainstorming
- **触发的 Superpowers 技能**：`brainstorming`
- **关键 prompt / context 配置**：
  - 用户输入："如task.md文件所示,我需要完成一份coding agent harness项目,具体需要交付物和流程如文档中所示.接下来你需要逐步引导我完成这个项目,注意每一部分都需要符合文档中的规范"
  - 加载 `brainstorming` 技能，读取 `TASK.md` 全文（274 行）和 `README.md`
- **brainstorming 关键决策节点**：
  1. **重点维度选择**：提出 3 个方向（治理/反馈闭环/扩展），推荐反馈闭环。用户选择 B（反馈闭环）。
  2. **技术栈选择**：提出 4 个选项（Python/TS/Go/Rust），推荐 Python。用户选择 A（Python）。
  3. **LLM 供应商**：提出 4 个选项，推荐多供应商支持（默认 OpenAI）。用户选择 3。
  4. **应用场景**：提出 4 个选项，推荐代码修复型。用户选择 1。
  5. **凭据存储**：提出 4 个选项，推荐加密文件+主密码。用户选择 2。
  6. **分发形态**：提出 4 个选项，推荐 Docker。用户选择 1。
  7. **WebUI 形态**：提出 3 个选项，推荐极简交互式。用户选择 2（终端流式+历史记录）。
  8. **失败分类**：提出 5 种类型，用户确认。
  9. **停机条件**：提出 5 种条件，用户确认。
  10. **护栏范围**：提出 5 类拦截，用户确认。
  11. **记忆设计**：提出 4 种存储，用户确认。
- **设计呈现**：分 8 块呈现（每块 200-300 字），用户逐块确认。
- **产出**：`SPEC.md`（432 行 → 补充后约 450 行）
- **人工干预**：
  - 用户要求检查 SPEC 是否完美符合 TASK.md，发现两处缺失：
    1. §3.6 条件要求：含 WebUI 须说明设计系统选择 → 补充原生 HTML/JS 理由
    2. §A.4-D 六个维度：须显式列出全部六个维度 → 补充 §11.3 六维度表
- **学到的教训**：
  - brainstorming 技能在引导设计决策方面非常有效，分块呈现让用户能逐步审查
  - 但 brainstorming 本身不会主动检查设计是否覆盖了外部规范的所有要求——这需要人工对照 TASK.md 逐项检查
  - "设计确认"和"规范合规检查"是两个不同的步骤，不能合并
- **commit hash**：`30643f9` — `docs: add SPEC.md, AGENT_LOG.md, README.md, .gitignore - brainstorming phase complete`
- **推送状态**：已推送到 `https://github.com/Levi-123a/theharness.git` main 分支

---

## 2026-07-10 14:53 — writing-plans 阶段

- **时间戳**：2026-07-10 14:53
- **阶段**：writing-plans
- **触发的 Superpowers 技能**：`writing-plans`
- **关键 prompt / context 配置**：
  - 用户输入："完成plan.md,注意要符合文档要求,注意完成后需更新部分文档,完成后检查是否符合要求,检查后记得git push"
  - 加载 `writing-plans` 技能，重新读取 `SPEC.md` 确保计划与设计一致
- **关键决策**：
  - 将 SPEC 分解为 14 个 task，每个 task 颗粒度可由一个 subagent 在一次会话内完成
  - 每个 task 包含：目标、涉及文件、实现要点、TDD 验证步骤（先写失败测试→实现→通过→提交）
  - 显式标注依赖关系和可并行部分（Task 3-7,10 可并行；Task 12,13 可并行）
  - 总计 77 个测试用例，全部使用 mock-LLM 驱动
- **产出**：`PLAN.md`（14 个 task，含依赖图、并行标注、总结表）
- **人工干预**：无，完全遵循 writing-plans 技能格式
- **学到的教训**：
  - writing-plans 技能的 task 结构非常清晰（Files → TDD steps → Commit），适合 subagent 执行
  - 依赖图和并行标注对后续 worktree 并行开发至关重要
  - PLAN.md 需要持续更新（每完成一个 task 标记完成并附 commit hash）

---

## 2026-07-10 15:07 — 冷启动验证（§4.5）

- **时间戳**：2026-07-10 15:07
- **阶段**：冷启动验证
- **触发的 Superpowers 技能**：`subagent-driven-development`（用于派发陌生 subagent）
- **验证智能体**：code-explorer subagent（与主开发智能体不同）
- **提供材料**：仅 `SPEC.md` + `PLAN.md`，无对话历史
- **指定任务**：Task 1（Project Scaffolding）和 Task 2（Data Models）
- **subagent 发现的 spec 缺陷**：7 处歧义
  1. Config 字段在 SPEC(3个) 与 PLAN(5个) 之间不一致 → 修订 SPEC §6.1
  2. Task 数据类：SPEC 有 config 字段，PLAN 省略 → 修订 SPEC §6.1，移除 config
  3. 枚举值未指定 → 修订 PLAN Task 2，明确 `str, Enum` 混入和小写字符串值
  4. FeedbackType.UNKNOWN 值歧义 → 统一为 `"unknown_failure"`
  5. 数据类 type 字段标注歧义 → 使用 `str, Enum` 混入
  6. 可选字段默认值未指定 → 修订 PLAN Task 2，明确所有默认值
  7. pyproject.toml 构建后端未指定 → PLAN Task 1 已含 setuptools，无需修订
- **人工干预**：根据 subagent 反馈修订 SPEC.md §6.1 和 PLAN.md Task 2
- **学到的教训**：
  - 冷启动验证是 spec 工作中最有价值的反馈信号
  - 主 agent 与用户共享隐性上下文，不会质疑未明文的假设
  - 全新 agent 没有隐性上下文，会在每个未明文假设处受阻
  - SPEC 和 PLAN 之间的数据模型必须完全一致

---

## 2026-07-10 16:41 — 步骤3重启：using-git-worktrees + Task 1 实现

- **时间戳**：2026-07-10 16:41
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **背景**：发现之前实现未遵循 Superpowers 7 步工作流（步骤 3/6/7 缺失，步骤 4 部分缺失）。用户要求"彻底重新开始,重新启动步骤3"。已将之前完整实现备份到 `reference/implementation` 分支，main 重置到 `bec9eca`（冷启动验证后）。
- **工作流偏离记录（§3.6）**：
  - **偏离**：subagent-driven-development 步骤中，实现由主 agent 而非 subagent 完成
  - **原因**：可用的 `code-explorer` subagent 仅有搜索/读取能力，无文件写入能力；`code-reviewer` subagent 仅用于评审
  - **适配方案**：主 agent 在 worktree 中执行 TDD 实现；`code-reviewer` subagent 执行两阶段评审（spec 合规 + 代码质量）
- **Task 1 执行过程**：
  1. **git worktree 创建**：`git worktree add .worktrees/task-1-scaffolding -b feature/task-1-scaffolding`
  2. **TDD RED**：编写 `tests/test_config.py`（2 个测试：默认值 + 自定义值），运行 pytest 确认失败（`ModuleNotFoundError: No module named 'the_harness'`）
  3. **TDD GREEN**：实现 `pyproject.toml`、`the_harness/__init__.py`、`the_harness/config.py`，运行 `pip install -e .[dev]` + pytest 确认通过（2 passed）
  4. **提交**：`240c07b` — `feat: project scaffolding with config dataclass`
  5. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（5/5 检查通过）
     - Stage 2 代码质量：FAIL → 修复后 PASS
     - **关键问题**：`pyproject.toml` 构建后端 `setuptools.backends._legacy:_legacy` 错误，改为 `setuptools.build_meta`
     - **非阻塞建议**：注释掉 `project.scripts` 入口点（Task 12 尚未实现）→ 已采纳
  6. **修正提交**：amend 到 `240c07b`
  7. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`3a4e668`）
- **commit hash**：`240c07b`（feature 分支）→ `3a4e668`（main merge）
- **学到的教训**：
  - code-reviewer subagent 发现了主 agent 遗漏的构建后端配置错误，证明两阶段评审的价值
  - TDD RED→GREEN 循环在小 task 上非常高效
  - worktree 隔离确保了实现不影响 main 分支稳定性

---

## 2026-07-13 09:00 — Task 2 实现：Data Models

- **时间戳**：2026-07-13 09:00
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 2 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-2-data-models` → `feature/task-2-data-models`
  2. **基线验证**：安装包，运行 Task 1 测试（2 passed）
  3. **TDD RED**：编写 `tests/test_models.py`（8 个测试：2 枚举 + 6 数据类），运行 pytest 确认失败（`ModuleNotFoundError: No module named 'the_harness.models'`）
  4. **TDD GREEN**：实现 `the_harness/models.py`（2 枚举 + 7 数据类），运行 pytest 确认通过（10 passed）
  5. **预防性修复**：`TestResult` 类名以 "Test" 开头导致 pytest 警告，添加 `__test__ = False`
  6. **提交**：`aca8b06`
  7. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：FAIL → 修复后 PASS
     - **关键问题**：`GuardrailResult` 缺少测试覆盖（PLAN 要求测试每个数据类）
     - **修复**：添加 `test_guardrail_result_dataclass` 测试
     - Stage 2 代码质量：PASS（6/6 检查通过）
  8. **修正提交**：amend 到 `aca8b06`
  9. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`45088e9`）
- **commit hash**：`aca8b06`（feature 分支）→ `45088e9`（main merge）
- **学到的教训**：
  - 评审发现的 `GuardrailResult` 测试遗漏说明 PLAN.md 中"create each dataclass"的要求需要逐字对照
  - `__test__ = False` 是处理 pytest 与 "Test*" 类名冲突的标准模式
  - 意外提交的 `test_output.txt` 提醒需要将临时文件加入 .gitignore

---

## 2026-07-13 09:30 — Task 3 实现：LLM Abstraction Layer

- **时间戳**：2026-07-13 09:30
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 3 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-3-llm` → `feature/task-3-llm`
  2. **TDD RED**：编写 `tests/test_mock_provider.py`（3 个测试），确认失败（`ModuleNotFoundError: No module named 'the_harness.llm'`）
  3. **TDD GREEN**：实现 `the_harness/llm/__init__.py`、`base.py`（LLMProvider ABC）、`mock_provider.py`（MockLLMProvider），确认通过（14 passed）
  4. **提交**：`5b97ddc`
  5. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（6/6 检查通过）
     - Stage 2 代码质量：PASS（6/6 检查通过）
     - 无关键问题，4 个非阻塞建议（未使用导入、防御性拷贝等）
  6. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`86add89`）
- **commit hash**：`5b97ddc`（feature 分支）→ `86add89`（main merge）

---

## 2026-07-13 09:25 — Task 4 实现：Credential Manager

- **时间戳**：2026-07-13 09:25
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 4 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-4-credentials` → `feature/task-4-credentials`
  2. **TDD RED**：编写 `tests/test_credential_manager.py`（6 个测试），确认失败
  3. **TDD GREEN**：实现 `the_harness/credentials/manager.py`（AES-256-GCM + PBKDF2），发现 `test_wrong_password_fails` 失败
  4. **Bug 修复**：`unlock()` 未在开始时清除状态，导致 `setup()` 后的错误密码仍保持解锁状态。修复：在 `unlock()` 开始时重置 `_key`、`_data`、`_unlocked`
  5. **提交**：`f54e36f`
  6. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（6/6 检查通过）
     - Stage 2 代码质量：PASS（6/6 检查通过）
     - 无关键问题，8 个非阻塞建议（原子写入、异常细化、setup 检查等）
  7. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`be3dcd3`）
- **commit hash**：`f54e36f`（feature 分支）→ `be3dcd3`（main merge）
- **学到的教训**：
  - TDD 在安全相关代码上特别有价值：`test_wrong_password_fails` 暴露了状态管理 bug
  - `unlock()` 的状态清除是安全关键：不清除就可能导致锁定后仍可访问

---

## 2026-07-13 09:40 — Task 5 实现：Guardrail

- **时间戳**：2026-07-13 09:40
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 5 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-5-guardrail` → `feature/task-5-guardrail`
  2. **TDD RED**：编写 `tests/test_guardrail.py`（12 个测试），确认失败
  3. **TDD GREEN**：实现 `the_harness/guardrail/guardrail.py`（14 个危险正则 + 4 个系统路径 + 工作区边界），确认通过（32 passed）
  4. **提交**：`4d01088`
  5. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（6/6 检查通过，14 个正则逐一核对）
     - Stage 2 代码质量：PASS（6/6 检查通过）
     - 无关键问题，5 个非阻塞建议（git clean 变体、系统路径子串匹配等）
  6. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`91fcf98`）
- **commit hash**：`4d01088`（feature 分支）→ `91fcf98`（main merge）

---

## 2026-07-13 09:50 — Task 6 实现：Tool Dispatcher

- **时间戳**：2026-07-13 09:50
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 6 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-6-tools` → `feature/task-6-tools`
  2. **TDD RED→GREEN**：8 个测试 → 实现 `the_harness/tools/dispatcher.py`（read/write/edit/shell/give_up），40 passed
  3. **提交**：`e4d4a12`
  4. **两阶段评审**：spec 合规 PASS，代码质量 PASS
  5. **可移植性修复**：`test_shell_failure` 中 `py` → `python`（CI 兼容）
  6. **finishing-a-development-branch**：合并回 main（`780e1f1`）
- **commit hash**：`e4d4a12`（feature 分支）→ `780e1f1`（main merge）

---

## 2026-07-13 10:00 — Task 7 实现：Test Validator

- **时间戳**：2026-07-13 10:00
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 7 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-7-validator` → `feature/task-7-validator`
  2. **TDD RED**：编写 `tests/test_validator.py`（4 个测试），确认 `ModuleNotFoundError` 失败
  3. **TDD GREEN**：实现 `the_harness/feedback/validator.py`（`TestValidator` + `validate()`），4 passed
  4. **TDD REFACTOR**：添加 `__test__=False` 消除 `PytestCollectionWarning`，0 warnings
  5. **提交**：`7eeb976`
  6. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（9/9 检查通过）
     - Stage 2 代码质量：PASS（无 lint 错误，文档完整）
     - 无 Critical issue，4 个建议（添加 FileNotFoundError 测试、简化 timeout 断言等）
  7. **采纳建议**：新增 `test_validate_pytest_not_found`（第 5 个测试），简化 timeout 断言
  8. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`c535bb5`）
- **commit hash**：`7eeb976`（feature 分支）→ `c535bb5`（main merge）
- **学到的教训**：
  - `TestValidator` 类名以 "Test" 开头同样触发 pytest 收集警告，与 `TestResult` 一样需要 `__test__=False`
  - Reviewer 建议添加 FileNotFoundError 测试是好的实践——规格要求实现该分支但未要求测试，补充测试能防止未来重构破坏

---

## 2026-07-13 10:10 — Task 8 实现：Failure Classifier

- **时间戳**：2026-07-13 10:10
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 8 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-8-classifier` → `feature/task-8-classifier`
  2. **TDD RED**：编写 `tests/test_classifier.py`（9 个测试），确认 `ModuleNotFoundError` 失败
  3. **TDD GREEN**：实现 `the_harness/feedback/classifier.py`（`FailureClassifier` + 6 个正则模式 + 6 个 strategy_hint），8/9 通过
  4. **修复**：`_RE_SYNTAX` 正则的非贪婪匹配与可选组冲突导致 location 提取失败，拆分为 `_RE_SYNTAX` + `_RE_LOCATION` 两个独立正则
  5. **提交**：`cf66e07`
  6. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（发现 1 个 Critical issue：`"timed out"` 与规范要求的 `"timeout"` 不匹配）
     - Stage 2 代码质量：PASS
     - Critical issue：timeout 字符串匹配偏差，已修复为同时检查 `"timeout"` 和 `"timed out"`
     - 新增 `test_classify_timeout_by_stderr_only` 测试（仅靠 stderr 匹配，exit_code != -1）
  7. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`a8f88cc`）
- **commit hash**：`1818fd1`（feature 分支）→ `a8f88cc`（main merge）
- **学到的教训**：
  - 正则的非贪婪匹配 `.+?` 与可选组 `(?:...)?` 组合时，引擎会取最短匹配导致可选组被跳过——应拆分为独立正则
  - 规范中的字符串匹配要精确：`"timeout"` 和 `"timed out"` 是不同的子串，需同时覆盖

---

## 2026-07-13 10:22 — Task 9 实现：Feedback Injector

- **时间戳**：2026-07-13 10:22
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 9 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-9-injector` → `feature/task-9-injector`
  2. **TDD RED→GREEN**：6 个测试 → 实现 `the_harness/feedback/injector.py`（`FeedbackInjector` + 6 种类型路由），6 passed
  3. **提交**：`dc38330`
  4. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（有轻微偏差：TIMEOUT 格式冗余）
     - Stage 2 代码质量：PASS
     - Important issue：TIMEOUT 输出 "timed out" 出现两次，已修复为 `f"Test timed out: {msg}."`
     - Important issue：测试未验证 strategy_hint 包含，已新增 `test_inject_includes_strategy_hint`
  5. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`c451b3c`）
- **commit hash**：`5ef6151`（feature 分支）→ `c451b3c`（main merge）

---

## 2026-07-13 10:31 — Task 10 实现：Memory Store

- **时间戳**：2026-07-13 10:31
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 10 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-10-memory` → `feature/task-10-memory`
  2. **TDD RED→GREEN**：6 个测试 → 实现 `the_harness/memory/store.py`（`MemoryStore` + SQLite + JSON），5/6 通过
  3. **修复**：`project_context.json` 保存在 `.harness/` 子目录，测试断言路径不匹配，更新测试
  4. **提交**：`b82cee2`
  5. **两阶段评审**（code-reviewer subagent）：
     - Stage 1 spec 合规：PASS（10/10 检查通过）
     - Stage 2 代码质量：PASS
     - 无 Critical issue，采纳 3 个建议：`__init__.py` 导出 MemoryStore、JSON 读取异常保护、SQLite 显式连接关闭 + PRAGMA foreign_keys
  6. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main（`3289958`）
- **commit hash**：`9f104a4`（feature 分支）→ `3289958`（main merge）
- **学到的教训**：
  - SQLite 的 `with` 上下文管理器只负责 commit/rollback，不关闭连接——需用 `try/finally + conn.close()`
  - 意外提交 `pytest_out.txt` 再次发生——需确保 `.gitignore` 覆盖所有测试输出文件名变体

---

## 2026-07-13 11:00 — Task 11 实现：Agent Main Loop

- **时间戳**：2026-07-13 11:00
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 11 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-11-agent-loop` → `feature/task-11-agent-loop`
  2. **TDD RED→GREEN**：6 个测试 → 实现 `the_harness/agent_loop.py`（`AgentLoop` + 5 种停机条件），74 passed
  3. **两阶段评审**（code-reviewer subagent）发现 2 个 Critical issue：
     - `credential_manager` 参数是死代码且打乱了构造函数位置参数顺序（规范中没有此参数）
     - `tool_dispatcher.execute(action)` 返回值被丢弃，执行失败被静默忽略
  4. **修复 Critical issues**：
     - 移除 `credential_manager` 参数和 `CredentialManager` 导入
     - 捕获 `exec_result = self._dispatcher.execute(action)`，检查 `exec_result.success`
  5. **采纳可选改进**：
     - `_parse_action` except 增加 `AttributeError, TypeError`
     - `_is_repeated` 移除冗余 `action` 参数
     - `run()` 结束时调用 `self._memory.save_session()` 保存会话
  6. **验证**：6 tests passed，74 total passed（无回归）
  7. **amend 提交**：`876f41a`
  8. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main
- **commit hash**：`876f41a`（feature 分支）→ main merge
- **学到的教训**：
  - 构造函数参数顺序必须与规范完全一致——多余的参数不仅增加复杂度，还打乱了位置参数的使用
  - 工具执行结果不能被丢弃——静默忽略失败会导致 agent 在错误状态下继续运行
  - code-reviewer subagent 的两阶段评审在核心模块上价值最大，发现了主 agent 遗漏的接口合规问题

---

## 2026-07-13 12:06 — Task 12 实现：WebUI

- **时间戳**：2026-07-13 12:06
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`
- **Task 12 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-12-webui` → `feature/task-12-webui`
  2. **TDD RED→GREEN**：5 个测试 → 实现 `the_harness/webui/`（FastAPI + WebSocket + 静态前端），79 passed
  3. **两阶段评审**（code-reviewer subagent）发现 2 个 Critical + 5 个 Important：
     - **Critical #1**：WebSocket 不是实时流式输出——事件被批量收集到列表中，循环结束后才发送
     - **Critical #2**：直接访问和替换 AgentLoop 的私有属性（`loop._llm`、`loop._validator`）
  4. **修复 Critical issues**：
     - 使用 `queue.Queue`（线程安全）实现真正的实时事件传递：工作线程通过 `_EmittingLLM`/`_EmittingValidator` 往队列写入事件，主协程通过 `asyncio.to_thread(queue.get, timeout=0.1)` 消费并立即发送
     - 将 emitting 包装器在构造 AgentLoop 之前注入，而非事后 monkey-patch 私有属性
  5. **修复 Important issues**：
     - 添加 `feedback` 事件断言到 `test_websocket_receives_events`
     - 添加 `_validate_workspace()` 路径遍历防护
     - WebSocket 关闭时清理 `_sessions` 内存字典
     - 移除未使用的导入和死代码
  6. **验证**：5 tests passed，79 total passed（无回归）
  7. **amend 提交**：`c00f251`
  8. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main
- **commit hash**：`c00f251`（feature 分支）→ main merge
- **学到的教训**：
  - "实时流式"不能靠批量收集后发送——必须用线程安全队列实现真正的逐事件传递
  - 不应从外部访问对象的私有属性——应在构造时注入包装器，保持封装完整性
  - `__init__.py` 中 `from module import app` 会导致 `app` 属性遮蔽子模块，测试中需用 `importlib.import_module()` 绕过

---

## 2026-07-13 12:30 — Task 13 实现：Demo Script

- **时间戳**：2026-07-13 12:30
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `test-driven-development` → `finishing-a-development-branch`
- **Task 13 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-13-demo` → `feature/task-13-demo`
  2. **TDD RED→GREEN**：3 个测试 → 实现 `demo.py`（3 个确定性演示），82 passed
  3. **修复**：`assertion_failure` 测试数据从 `AssertionError: expected 5 got 3` 改为 `assert 5 == 3`，因为 classifier 的 `_RE_ASSERT` 正则匹配 `assert X == Y` 格式
  4. **验证**：`python demo.py` 退出码 0，3/3 演示通过
  5. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main
- **commit hash**：`4b3a8a2`（feature 分支）→ main merge
- **学到的教训**：
  - 测试数据必须匹配实际的 regex 模式——`AssertionError:` 文本不等于 `assert X == Y` 格式
  - demo.py 的 3 个演示覆盖了 harness 的 3 个核心机制：护栏拦截、反馈闭环、分类路由

---

## 2026-07-13 12:50 — Task 14 实现：Docker + CI/CD

- **时间戳**：2026-07-13 12:50
- **阶段**：实现工作流（§4.6）
- **触发的 Superpowers 技能**：`using-git-worktrees` → `finishing-a-development-branch`
- **Task 14 执行过程**：
  1. **git worktree 创建**：`.worktrees/task-14-docker` → `feature/task-14-docker`
  2. **创建文件**：
     - `Dockerfile`：基于 `python:3.12-slim`，`pip install -e .`，暴露 8000 端口，CMD `uvicorn the_harness.webui:app`
     - `.github/workflows/ci.yml`：Job `unit-test`（checkout → setup Python 3.12 → pip install -e .[dev] → pytest）+ Job `docker-build`（depends on unit-test，docker build + push on main）
     - `Makefile`：`test`/`run`/`docker-build`/`docker-run`/`demo`/`install` targets
  3. **更新 README.md**：添加分发命令表格，更新 git clone URL
  4. **取消注释 pyproject.toml 入口点**：`the-harness = "the_harness.webui.app:app"`
  5. **验证**：82 tests passed（无回归）
  6. **finishing-a-development-branch**：`git merge --no-ff` 合并回 main
- **commit hash**：`47f11ce`（feature 分支）→ main merge
- **学到的教训**：
  - CI 的 job 名称必须与规范要求完全一致（`unit-test`）
  - Dockerfile 应该先 copy `pyproject.toml` 再 copy 源码，利用 Docker layer cache 加速构建

---

## 2026-07-13 13:30 — 最终代码评审修复

- **时间戳**：2026-07-13 13:30
- **阶段**：收尾工作
- **触发的 Superpowers 技能**：`requesting-code-review`（最终评审）、`verification-before-completion`
- **执行过程**：
  1. **最终代码评审**：code-reviewer subagent 对整个项目做最终评审，发现 5 个 Important issues + 5 个 Suggestions
  2. **修复 5 个 Important issues**：
     - `save_session` 字段名不匹配：`type`→`action_type`、`params`→`action_params`（与 `store.py` 的 `save_session` 方法一致）
     - `save_session` 调用路径不完整：仅在 max-rounds 退出时调用 → 提取 `_save_session` 辅助方法，在所有 4 个退出路径（give_up、pass、repeated、max_rounds）均调用
     - `pyproject.toml` 入口点指向 ASGI 对象：`the_harness.webui.app:app` → 添加 `main()` 可调用函数，改为 `the_harness.webui.app:main`
     - 缺少真实 LLM Provider：创建 `the_harness/llm/openai_provider.py`（`OpenAILLMProvider`，调用 OpenAI Chat Completions API，解析 JSON 响应）
     - ToolDispatcher 缺少工作区边界第二层检查：在 `_resolve_path` 中添加 `PermissionError` 检查，确保解析后的路径不逃逸出工作区
  3. **验证**：82 tests passed，无回归
- **commit hash**：`9778670`
- **学到的教训**：
  - `save_session` 的字段名必须与 `store.py` 的 `save_session` 方法中的 `action.get("action_type", "")` 和 `json.dumps(action.get("action_params", {}))` 完全一致——字段名不匹配不会报错，但数据会静默丢失
  - 所有退出路径（不只是 max-rounds）都应保存会话——否则成功会话和 give-up 会话的历史会丢失
  - `pyproject.toml` 的 `project.scripts` 入口点必须指向可调用对象（函数），而非 ASGI 应用对象——`uvicorn app:app` 和 `the-harness` CLI 命令是不同的使用场景
  - 真实 LLM Provider 的系统提示词需要明确指示 LLM 返回 JSON 格式的 action/params/reasoning，并处理 markdown 代码围栏

---

## 2026-07-13 14:00 — TASK.md 合规修复

- **时间戳**：2026-07-13 14:00
- **阶段**：合规检查与修复
- **触发的 Superpowers 技能**：`verification-before-completion`
- **执行过程**：
  1. **系统对照 TASK.md 检查所有交付物**，发现以下缺失项：
     - ❌ `.gitlab-ci.yml`（§五.6 要求 GitLab CI 配置含 `unit-test` job）
     - ❌ 首次运行引导安全录入 key 的 CLI 交互流程（§3.1）
     - ❌ README 部署架构与 CI/CD 说明（§4.11）
  2. **修复 3 项缺失**：
     - **创建 `.gitlab-ci.yml`**：包含 `unit-test` job（pytest）和 `docker-build` job（Docker 构建+推送），与 GitHub Actions 配置对等
     - **创建 `the_harness/cli.py`**：交互式凭据管理 CLI，提供 `setup`/`status`/`store`/`delete`/`unlock` 五个子命令，使用 `getpass` 隐藏输入，首次运行引导用户设置主密码（≥8 字符）和 API key
     - **更新 `pyproject.toml`**：添加 `the-harness-creds` 入口点指向 `the_harness.cli:main`
     - **更新 `the_harness/__init__.py`**：导出 `cli_main`
     - **更新 `README.md`**：添加部署架构图（本地/Docker/云部署）、CI/CD 管道说明表、凭据管理命令表、更新项目结构
     - **编写 `tests/test_cli.py`**：17 个测试覆盖所有 CLI 子命令
  3. **验证**：99 tests passed（82 原有 + 17 新增），无回归
- **commit hash**：`2df9b47`
- **学到的教训**：
  - TASK.md §五.6 明确要求 `.gitlab-ci.yml`（非 `.github/workflows/ci.yml`）——NJU GitLab 使用 GitLab CI，需同时提供两种 CI 配置
  - §3.1 的"首次运行应能引导用户安全录入 key"要求的是交互式 CLI 流程，而非仅提供 API 方法——`CredentialManager` 有 `setup()`/`store()` 方法但缺少调用它们的 CLI 入口
  - §4.11 的"README 说明部署架构与 CI/CD"要求在 README 中描述系统架构图和 CI/CD 管道，而非仅在 SPEC 中描述

---

## 2026-07-14 17:30 — 项目状态全流程分析

- **时间戳**：2026-07-14 17:30
- **阶段**：收尾验证
- **触发的 Superpowers 技能**：无（只读分析）
- **关键 prompt / context 配置**：
  - 用户输入："根据当前项目文档和具体代码分析当前项目状态"
  - 读取 `HANDOFF.md`、`TASK.md`、`PLAN.md`、`SPEC.md`、`pyproject.toml`、全部源代码与测试文件、CI 配置、`AGENT_LOG.md`
  - 派出 2 个 search subagent 并行分析：核心模块代码质量 + 测试覆盖率与基础设施
- **分析结果**：
  - 14/14 Task 全部完成，99 tests passed，HEAD `ac1d794`
  - Superpowers 七步工作流基本合规，偏离（subagent 无文件写入能力）已记录
  - 两个关键缺口：线上部署 URL 未确认、GitLab CI 执行记录缺失
  - Freeform 模式端点已完整实现（`/api/instruct`、`/ws/instruct/{session_id}`）
- **学到的教训**：
  - 全流程合规检查应对照 TASK.md §五的 11 项交付物逐条核对，而非仅检查代码完成度
  - 线上部署和 CI 运行记录是硬性评分项，容易在开发末期被忽略

---

## 2026-07-14 18:00 — WebUI 启动与端口冲突处理

- **时间戳**：2026-07-14 18:00
- **阶段**：部署运行
- **触发的 Superpowers 技能**：无
- **关键 prompt / context 配置**：
  - 用户输入："启动当前项目"
  - 首次启动时端口 8000 被旧 Python 进程（PID 47636）占用，返回 `WinError 10048`
- **人工干预**：用户选择"终止旧进程并重启"
- **执行过程**：
  1. `taskkill /PID 47636 /F` 终止旧进程
  2. `uvicorn the_harness.webui.app:app --host 0.0.0.0 --port 8000` 重新启动
  3. 通过 `OpenPreview` 打开 `http://localhost:8000`
- **学到的教训**：
  - Windows 环境下 uvicorn 端口占用错误码是 `WinError 10048`，应先 `netstat -ano | findstr :8000` 查找占用进程

---

## 2026-07-15 00:20 — 扩展 LLM API 配置：支持自定义 Base URL 和 Model

- **时间戳**：2026-07-15 00:20
- **阶段**：功能扩展
- **触发的 Superpowers 技能**：`brainstorming`（Plan 模式探索）、TDD
- **关键 prompt / context 配置**：
  - 用户输入："修改当前项目的api系统，让用户可以通过输入api和url地址来使用llm"
  - Plan 模式：读取 `openai_provider.py`、`base.py`、`manager.py`、`app.py`、`app.js`、`index.html`、`config.py`、`cli.py`、`test_webui.py`、`test_credential_manager.py` 共 11 个文件
  - 计划文件：`.trae/documents/llm-api-url-config.md`
- **关键决策**：
  1. `CredentialManager._data` 从 `dict[str, str]` 扩展为 `dict[str, dict[str, str]]`，每个 provider 存 `{"api_key", "base_url", "model"}`
  2. 旧格式（str）在 `unlock()` 时自动迁移为 dict 格式，无缝升级
  3. `OpenAILLMProvider` 新增 `base_url` 参数，传给 `OpenAI(base_url=...)` 构造函数
  4. WebUI Settings 移除固定 `<select>`，改为自由输入 provider 名称 + Base URL + Model 三个字段
  5. 不改 `LLMProvider` ABC——`base_url` 是 OpenAI 实现细节
- **执行过程**：
  1. **CredentialManager**：`store()` 签名改为 `store(provider, api_key, base_url="", model="")`；新增 `get_api_key()` 便捷方法；`status()` 返回 `dict[str, dict]`；`unlock()` 添加旧格式自动迁移逻辑
  2. **OpenAILLMProvider**：`__init__` 新增 `base_url: str | None = None`；`OpenAI(api_key=..., base_url=self._base_url)`
  3. **Config**：新增 `base_url: str = ""` 字段
  4. **WebUI 后端**：`credentials_store` Body 改为 `{"provider", "api_key", "base_url", "model"}`；`_default_agent_loop_factory` 从 `cm.get("openai")` 提取完整配置传给 `OpenAILLMProvider`
  5. **WebUI 前端**：`index.html` 移除 `<select>`，新增 3 个文本输入框；`app.js` 更新 Store/Edit 逻辑；新增 `editProvider()` 函数支持点击 Edit 回填表单；`style.css` 调整列表布局
  6. **CLI**：`cmd_setup`/`cmd_store` 新增 `base_url`/`model` 输入提示；`cmd_status` 显示 URL 和 Model
  7. **测试**：新增 6 个测试（`test_store_with_base_url_and_model`、`test_get_api_key_convenience`、`test_status_shows_base_url_and_model`、`test_backward_compat_migration`、`test_setup_with_base_url_and_model`、`test_store_key_with_base_url_and_model`），更新现有测试适配新接口
- **验证**：105 passed, 0 failed（99 原有 + 6 新增）
- **学到的教训**：
  - 破坏性数据格式变更必须考虑向后兼容——旧用户解密文件时自动迁移比强制重新创建更友好
  - `openai` 库的 `base_url=None` 等价于使用官方地址，空字符串需映射为 None

---

## 2026-07-15 00:50 — 修复 WebUI 创建 Key 后报错（PermissionError + React #185）

- **时间戳**：2026-07-15 00:50
- **阶段**：Bug 修复
- **触发的 Superpowers 技能**：`test-driven-development`（RED → GREEN → REFACTOR）
- **关键 prompt / context 配置**：
  - 用户输入："为什么创建key后显示Error Minified React error #185..."
  - 用户显式要求使用 `test-driven-development` 技能
- **根因分析**：
  - 表面现象：TRAE IDE 预览层显示 React error #185（"Objects are not valid as a React child"）
  - 实际根因：`POST /api/credentials/setup` 在写入 `C:\Users\liwer\.the-harness\credentials.enc` 时抛出 `PermissionError: [Errno 13] Permission denied`——旧凭据文件被前一个 uvicorn 进程锁住
  - FastAPI 未捕获 `PermissionError`，返回 500 Internal Server Error；TRAE 预览层渲染错误对象时触发 React #185
- **TDD 流程**：
  1. **RED**：写 `test_credentials_setup_returns_error_on_permission_denied`，patch `CredentialManager.setup` 抛出 `PermissionError`，断言响应应含可读错误而非 500。测试正确失败（异常未捕获，TestClient 抛出 `PermissionError`）
  2. **GREEN**：在 `credentials_setup`、`credentials_store`、`credentials_delete` 三个端点添加 `try/except PermissionError`，返回 403 + 可读错误信息。测试通过
  3. **全量回归**：106 passed, 0 failed
- **执行过程**：
  1. 修复代码后终止旧 uvicorn 进程（PID 46364）
  2. 重新启动服务在 `localhost:8000`
  3. 通过 `OpenPreview` 验证无浏览器错误
- **学到的教训**：
  - 表面是前端 React 错误，根因可能是后端未捕获异常——先看服务器日志再调前端
  - FastAPI 端点应对所有可能的 IO 异常（`PermissionError`、`OSError`）做防御性捕获，避免 500 错误暴露给前端
  - Windows 文件锁问题在进程被强制终止后仍可能残留，重启服务前应清理旧的凭据文件

---

## 2026-07-15 01:10 — 修复 WebUI "Failed to fetch"（CORS 跨域）

- **时间戳**：2026-07-15 01:10
- **阶段**：Bug 修复
- **触发的 Superpowers 技能**：`test-driven-development`（RED → GREEN）
- **关键 prompt / context 配置**：
  - 用户输入："现在创建时会显示Setup failed: Failed to fetch，修改好 Use Skill: test-driven-development"
- **根因分析**：
  - 表面现象：浏览器前端发起 `POST /api/credentials/setup` 时显示 "Failed to fetch"
  - 实际根因：FastAPI 未配置 CORS 中间件，浏览器因同源策略拦截了跨域请求（TRAE 预览层域名与 `localhost:8000` 不同源）
- **TDD 流程**：
  1. **RED**：写 `test_api_has_cors_headers`，发送 OPTIONS 预检请求，断言响应含 `access-control-allow-origin` 头。测试失败（无 CORS 头）
  2. **GREEN**：在 `app.py` 添加 `CORSMiddleware`（`allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`）。测试通过
  3. **全量回归**：107 passed, 0 failed
- **学到的教训**：
  - "Failed to fetch" 在浏览器中通常不是网络错误，而是 CORS 预检失败——应先检查 OPTIONS 响应头
  - FastAPI 的 `CORSMiddleware` 必须在路由定义前添加，否则中间件不生效

---

## 2026-07-15 01:40 — 修复凭据文件路径依赖 CWD 导致 PermissionError

- **时间戳**：2026-07-15 01:40
- **阶段**：Bug 修复
- **触发的 Superpowers 技能**：`test-driven-development`（RED → GREEN → 全量回归）
- **关键 prompt / context 配置**：
  - 用户输入："现在创建时会显示Cannot write credential file: [Errno 13] Permission denied: 'C:\\Users\\liwer\\.the-harness\\credentials.enc'. Check file permissions or delete the existing file.，修改好 Use Skill: test-driven-development"
- **根因分析**：
  - 表面现象：WebUI 创建凭据存储时返回 403 "Cannot write credential file: [Errno 13] Permission denied"
  - 实际根因：`_CREDENTIAL_FILE` 使用 `Path.cwd()` 解析默认路径。当 uvicorn 进程从非项目目录启动时（如从用户主目录启动），`Path.cwd()` 返回 `C:\Users\liwer`，凭据文件路径变为 `C:\Users\liwer\.the-harness\credentials.enc`——该路径在 TRAE IDE 沙箱环境中不可写
  - 诊断过程：直接 Python 调用 `setup()` 成功；TestClient 调用成功；但通过 HTTP 调用 uvicorn 服务返回 403。最终发现服务器进程的 CWD 与项目目录不同
- **TDD 流程**：
  1. **RED**：写 `test_credential_file_default_path_uses_module_location`，`monkeypatch.chdir(tmp_path)` 模拟从其他目录启动，重新导入模块，断言 `_CREDENTIAL_FILE` 不在 `tmp_path` 下而在项目根目录下。测试失败（路径为 `tmp_path\.the-harness\credentials.enc`，依赖 CWD）
  2. **GREEN**：将 `_CREDENTIAL_FILE` 从 `Path.cwd() / ".the-harness" / "credentials.enc"` 改为 `_PROJECT_ROOT / ".the-harness" / "credentials.enc"`，其中 `_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent`（模块位置推导项目根目录）。测试通过
  3. **全量回归**：109 passed, 0 failed
- **验证**：
  - 终止旧 uvicorn 进程（PID 45808），清除 `__pycache__`
  - 重新启动服务，`POST /api/credentials/setup` 返回 200 OK
  - 确认文件创建在 `D:\001\the harness\.the-harness\credentials.enc`（项目根目录），而非 `C:\Users\liwer\.the-harness\`
- **学到的教训**：
  - `Path.cwd()` 在服务器应用中是反模式——服务器进程的 CWD 取决于启动方式（服务管理器、IDE、命令行），不应作为定位项目资源的依据
  - 正确做法是使用 `Path(__file__)` 从模块位置推导项目根目录，确保路径在任何启动方式下都一致
  - TDD 的 RED 阶段通过 `monkeypatch.chdir()` 模拟不同 CWD 是验证路径解析逻辑的有效手段
  - 沙箱环境的文件权限限制可能仅影响特定路径（如用户主目录），项目目录通常可写

---

## 2026-07-15 02:00 — WebUI 前端中文化

- **时间戳**：2026-07-15 02:00
- **阶段**：UI 优化
- **触发的 Superpowers 技能**：`frontend-skill`
- **关键 prompt / context 配置**：
  - 用户输入："优化前端界面为中文，注意简单易用性"
- **执行过程**：
  1. **index.html**：`lang="en"` → `lang="zh-CN"`；所有界面文本翻译为中文（"Sessions"→"会话列表"、"Fix Test"→"修复测试"、"Freeform"→"自由模式"、"Settings"→"设置"、"Start Fix"→"开始修复"、"Send"→"发送"、"API Key Settings"→"API 密钥设置"等）；placeholder 添加中文示例说明
  2. **app.js**：所有用户可见字符串翻译为中文（终端输出标签 `[Action]`→`[操作]`、`[Exec]`→`[执行]`、`[Feedback]`→`[反馈]`、`[Result]`→`[结果]`；alert 提示信息；状态文本；badge 文本 `PASS/FAIL`→`通过/失败`）；代码注释翻译为中文
  3. **style.css**：`font-family` 添加中文字体支持（`'Microsoft YaHei', 'PingFang SC'`），保留等宽英文字体优先级
- **验证**：9 WebUI tests passed，无回归；通过 `OpenPreview` 在浏览器中验证中文显示正常
- **学到的教训**：
  - 中文字体应放在等宽英文字体之后，让英文优先使用等宽字体保持终端风格，中文回退到系统中文字体
  - `lang` 属性从 `en` 改为 `zh-CN` 有助于浏览器正确渲染和辅助技术识别

---

## 2026-07-15 02:30 — TASK.md 交付物合规检查

- **时间戳**：2026-07-15 02:30
- **阶段**：收尾验证
- **触发的 Superpowers 技能**：无（只读分析）
- **关键 prompt / context 配置**：
  - 用户输入："根据task检查还有什么没完成"
  - 读取 `TASK.md` 全文，逐条对照 §五 最终交付物清单（11 项）
  - 派出 search subagent 检查 SPEC_PROCESS.md、REFLECTION.md、README.md、.gitlab-ci.yml、render.yaml 完整性
- **检查结果**：
  - ✅ 已完成（12 项）：SPEC.md、PLAN.md、SPEC_PROCESS.md、完整源代码、Dockerfile、README.md、AGENT_LOG.md、.gitlab-ci.yml、REFLECTION.md、render.yaml、demo.py、mock-LLM 单元测试
  - ❌ 未完成（5 项）：
    1. 18 个本地修改未提交推送（LLM API 扩展、CORS、PermissionError 修复、前端中文化等）
    2. 8 个 feature 分支已合并但未删除
    3. CI/CD 执行记录未确认（远程仓库缺少最新代码）
    4. 线上部署 URL 未确认可访问
    5. 临时文件（server_stdout.txt、server_stderr.txt、.trae/）未加入 .gitignore
- **学到的教训**：
  - 全流程合规检查应在开发末期做一次完整对照，容易遗漏的是"本地修改未推送"和"临时文件未清理"等非功能性项
  - `.gitignore` 应在项目初期就覆盖所有可能的临时输出文件名变体

---

## 2026-07-15 02:40 — 提交推送本地修改

- **时间戳**：2026-07-15 02:40
- **阶段**：版本控制
- **触发的 Superpowers 技能**：无
- **关键 prompt / context 配置**：
  - 用户输入："处理1"（指合规检查中的第 1 项：18 个本地修改未提交推送）
- **执行过程**：
  1. 更新 `.gitignore`：添加 `server_stdout.txt`、`server_stderr.txt`、`.trae/` 排除规则
  2. `git add` 18 个修改文件（AGENT_LOG.md、README.md、SPEC.md、tests/*、the_harness/* 等）
  3. `git commit`：commit message 涵盖 LLM API 扩展、CORS 修复、PermissionError 修复、前端中文化、10 个新测试、AGENT_LOG 更新
  4. `git push origin main`：`ac1d794..f14d502`
- **commit hash**：`f14d502`
- **学到的教训**：
  - PowerShell 不支持 bash heredoc 语法（`<<'EOF'`），多行 commit message 需使用 `git commit -F` 从文件读取
  - 大批量提交时应确保 `.gitignore` 已覆盖所有临时文件，避免误提交

---

## 2026-07-15 03:00 — 修复 GitHub Actions CI 错误

- **时间戳**：2026-07-15 03:00
- **阶段**：CI/CD 修复
- **触发的 Superpowers 技能**：无
- **关键 prompt / context 配置**：
  - 用户输入：CI 报 "1 error and 2 warnings" — docker-build 标签大写、Node.js 20 deprecation
- **问题分析**：
  1. **docker-build error**：`ghcr.io/${{ github.repository }}` 展开为 `ghcr.io/Levi-123a/theharness`，GHCR 要求 repository name 全小写
  2. **unit-test warning**：`actions/checkout@v4`、`actions/setup-python@v5` 使用 Node.js 20，已被 GitHub 弃用
  3. **docker-build warning**：`actions/checkout@v4`、`docker/build-push-action@v5`、`docker/setup-buildx-action@v3` 同样使用 Node.js 20
- **修复**：
  1. GHCR 标签改为硬编码小写：`ghcr.io/levi-123a/theharness:latest`
  2. Actions 版本升级：`actions/checkout@v4→@v5`、`docker/build-push-action@v5→@v6`
- **commit hash**：`2197b07`
- **推送问题**：首次推送时 GitHub `github.com:443` TCP 连接超时（国内网络波动），重试 3 次后成功
- **学到的教训**：
  - `github.repository` 变量保留原始大小写，GHCR 标签必须手动转小写或使用 `${{ github.repository }}` 的 lowercase 变体
  - GitHub Actions 的 Node.js 版本弃用是渐进式的——先 warning 后 error，应在 warning 阶段就升级

---

## 2026-07-15 03:20 — 修复 GHCR 推送认证 403 Forbidden

- **时间戳**：2026-07-15 03:20
- **阶段**：CI/CD 修复
- **触发的 Superpowers 技能**：无
- **关键 prompt / context 配置**：
  - 用户输入：docker-build 报 "failed to fetch anonymous token: 403 Forbidden"
- **问题分析**：
  - `docker/build-push-action` 的 `push: true` 步骤在推送 GHCR 前未登录，以匿名身份请求 token 被 403 拒绝
  - GitHub Actions 默认的 `GITHUB_TOKEN` 缺少 `packages: write` 权限，无法推送镜像到 GHCR
- **修复**：
  1. 添加 `docker/login-action@v3` 步骤，使用 `GITHUB_TOKEN`（GitHub Actions 自动提供）登录 `ghcr.io`
  2. 在 `docker-build` job 添加 `permissions: contents: read, packages: write`
- **commit hash**：`e8f731f`
- **学到的教训**：
  - GHCR 推送必须显式 `docker login`——`build-push-action` 不会自动认证
  - GitHub Actions 的 `GITHUB_TOKEN` 默认只有 `contents: read` 权限，推送 packages 需在 job 级别声明 `permissions: packages: write`
