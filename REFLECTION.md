# REFLECTION.md — the-harness 项目反思报告

> 本报告反思使用 Superpowers 方法论完成 AI4SE 期末项目（Coding Agent Harness）的全过程，涵盖 14 个 task 的 TDD 实现、两阶段代码评审、以及最终交付。

---

## 一、哪些 Superpowers 技能发挥了最大作用、哪些"形式大于实质"？

**发挥最大作用的技能：**

1. **`test-driven-development`**：这是整个项目中价值最高的技能。TDD 的 RED→GREEN→REFACTOR 循环在 AI 协作场景下产生了三重收益：首先，先写失败测试迫使我在写实现前就明确接口契约（输入、输出、边界条件），消除了"边写边想"导致的接口漂移；其次，RED 阶段的 `ModuleNotFoundError` 是一个客观的"测试确实在验证"的信号，避免了"写了测试但测试永远通过"的假绿问题；最后，GREEN 后的全量回归测试在每次合并前提供了"无回归"的客观证据。82 个测试在 2.5 秒内跑完，这种快速反馈循环是 AI 协作中保持质量纪律的核心基础设施。

2. **`using-git-worktrees`**：worktree 隔离让每个 task 在独立的分支上开发，main 分支始终保持可运行状态。这在实践中意味着：即使某个 task 的实现出了问题，也不会污染其他 task 的工作。`--no-ff` 合并保留了完整的分支历史，使得每个 task 的 commit 链条可追溯。

3. **`requesting-code-review`**（两阶段评审）：code-reviewer subagent 在多个 task 中发现了主 agent 遗漏的问题。最典型的案例是 Task 11 中发现的 `credential_manager` 死代码参数和 `execute()` 返回值被丢弃——这两个问题主 agent 在实现时完全没有注意到，因为功能测试通过了。评审的"spec 合规"阶段特别有效，因为它逐条对照 PLAN.md 的实现要点，而非泛泛而谈。

**"形式大于实质"的技能：**

1. **`finishing-a-development-branch`**：这个技能在每次 task 完成后提供合并/PR/保留/丢弃的选项。但在单人项目中，选择永远是"merge with --no-ff"，这个决策过程没有产生实际价值。它更适合团队协作场景，单人项目中可以简化为自动合并。

2. **`executing-plans`**：理论上这个技能用于在独立会话中执行计划，但由于可用的 subagent 不具备文件写入能力，实际执行仍由主 agent 完成。技能加载了但未真正"执行"——它更多是一个计划审查的框架，而非执行引擎。

---

## 二、TDD 强制在 AI 协作下是阻碍还是放大器？

**TDD 是放大器，但有一个前提条件：测试本身必须足够简单。**

在本项目中，TDD 的放大效应体现在三个层面：

**接口先行**：先写测试意味着先定义接口。例如 Task 8（Failure Classifier），测试先明确了输入是 `TestResult`、输出是 `ClassifiedFeedback`，且 5 种类型各有对应的 `strategy_hint`。这个接口定义在测试文件中固化后，实现只需要"让测试通过"，不需要再做接口设计决策。AI 在"填充实现"模式下比在"设计+实现"模式下产生的代码质量更高——因为前者消除了设计决策中的不确定性。

**回归保护**：14 个 task 串行合并到 main，每次合并前运行全量测试。如果没有 TDD 产生的测试套件，每次合并都需要手动验证"之前的 task 是否仍然正常"——这在 82 个测试的规模下是不可行的。TDD 将这种验证自动化了。

**Bug 发现**：Task 4（Credential Manager）的 `test_wrong_password_fails` 在 GREEN 阶段失败，暴露了 `unlock()` 未清除状态的 bug。如果没有先写这个测试，这个 bug 可能要到集成阶段才被发现，届时定位成本会高得多。

**阻碍的一面**：TDD 在某些 task 上增加了摩擦。Task 14（Docker + CI）本质上是配置文件编写，TDD 的价值有限——Dockerfile 和 CI YAML 不适合用单元测试验证。在这个 task 上，"先写测试"更多是形式而非实质。类似地，Task 12（WebUI）的前端 HTML/CSS/JS 部分无法用 TDD 覆盖，只有后端 API 可以测试。

**结论**：TDD 在"机制代码"（可确定性验证的逻辑）上是强放大器，在"配置/前端代码"上是弱阻碍。关键判据是：**这段代码能否用 mock 输入产生确定性输出？** 如果能，TDD 价值极高；如果不能，TDD 退化为形式。

---

## 三、subagent-driven 工作流让智能体能自主运行多久而不偏离主题？

**在本项目的实践中，subagent 的自主运行时间约为 15-25 分钟（一个 task 的完整 TDD 循环），超过这个时间窗口后偏离风险显著增加。**

偏离的主要模式有三种：

1. **接口膨胀**：Task 11 的实现中，主 agent 在构造函数中添加了 `credential_manager` 参数——这个参数不在 SPEC 中，是 agent 在"看到 CredentialManager 模块后觉得应该用上"的自作主张。这种偏离在 15 分钟内就发生了，说明 agent 有"过度设计"的倾向。

2. **架构走偏**：Task 12 的初始实现中，WebSocket 事件被批量收集到列表中，循环结束后才发送——这违背了"实时流式"的需求。agent 在实现时选择了更简单的批量方案，而非正确的流式方案。这种偏离在实现过程中不会触发任何测试失败（因为测试只检查事件内容，不检查时序），只有 code-reviewer 才能发现。

3. **正则匹配偏差**：Task 8 中 classifier 的 timeout 检测只检查 `"timed out"` 而遗漏了 `"timeout"`——这是 SPEC 中明确要求的字符串。agent 在实现时选择了第一个想到的字符串，没有穷举 SPEC 中的所有变体。

**关键发现**：subagent 的偏离不是随机的，而是系统性地偏向"更简单的实现"。TDD 的 RED 阶段只能捕获"功能缺失"型偏离，无法捕获"功能存在但行为偏差"型偏离。后者需要 code-reviewer 的 spec 合规检查来捕获。

**延长自主运行时间的关键**：每个 task 的 PLAN.md 中包含明确的"实现要点"列表和"验证步骤"。当这些要点足够具体（如"14 个危险正则"、"5 种失败类型"）时，agent 的偏离率显著降低。当要点模糊（如"实现 WebUI"）时，偏离率上升。

---

## 四、什么样的 task 颗粒度最优？

**最优颗粒度：一个 task = 一个模块 = 3-8 个测试 = 15-25 分钟实现时间。**

本项目的 14 个 task 基本遵循了这个颗粒度，效果最好的是 Task 5（Guardrail，12 个测试）和 Task 8（Failure Classifier，9 个测试）——它们各自是一个独立的、可确定性测试的模块，接口清晰，实现要点明确。

**颗粒度过大的问题**：Task 12（WebUI）是最大的 task，包含后端 API + WebSocket + 前端三部分。这个 task 产生了最多的 Critical issue（2 个），原因正是颗粒度过大导致 agent 在多个关注点之间切换时丢失了上下文。如果拆分为"WebUI 后端"和"WebUI 前端"两个 task，偏离率会降低。

**颗粒度过小的问题**：Task 1（Scaffolding）只有 2 个测试，实现时间不到 5 分钟。这个 task 的 TDD 价值有限——`pyproject.toml` 的配置错误（构建后端写错）是 code-reviewer 发现的，不是 TDD 发现的。但作为项目结构的奠基 task，它的存在是必要的。

**依赖关系对颗粒度的影响**：Task 8→9（Classifier→Injector）是串行依赖，因为 Injector 的输入是 Classifier 的输出。这种依赖意味着即使两个 task 都很小，也不能并行。PLAN.md 中的依赖图在规划颗粒度时至关重要——可并行的 task（如 Task 3-7,10）可以适当拆细，串行依赖的 task 应该合并以减少 worktree 切换开销。

---

## 五、SPEC/PLAN 质量如何影响实现质量？

**案例：Task 8（Failure Classifier）的 timeout 字符串匹配偏差。**

SPEC.md 中明确写了 timeout 检测应匹配 `"timeout"` 字符串。PLAN.md Task 8 的实现要点中也写了 `exit_code == -1 or "timeout" in stderr`。但在实现时，agent 写的正则只匹配了 `"timed out"`（pytest 的实际输出），遗漏了 `"timeout"`。

这个案例说明：**SPEC 质量高（明确写了字符串）但实现仍偏离了**。问题不在 SPEC，而在于 agent 在实现时没有逐条对照 SPEC 的实现要点。code-reviewer 的 spec 合规检查阶段发现了这个偏差——因为它逐条对照 PLAN.md 的实现要点，而非泛泛检查代码质量。

**反例：Task 12（WebUI）的"实时流式"需求。**

SPEC.md 写了"实时流式输出"，PLAN.md Task 12 写了"WS /ws/fix/{session_id} — stream agent output events in real-time"。但"real-time"的定义是模糊的——是"每个事件产生后立即发送"还是"循环结束后批量发送"？agent 选择了后者，因为它更简单且测试不会失败。

这个案例说明：**当 SPEC/PLAN 中的描述存在多种合理解读时，agent 会系统性地选择更简单的解读**。要避免这种偏离，SPEC 应该包含"反例"——明确说明什么不算"real-time"（如"事件不得在循环结束后批量发送"）。

**结论**：SPEC 质量是必要条件而非充分条件。高质量的 SPEC 能降低偏离率，但不能消除偏离——因为 agent 在实现时可能不逐条对照 SPEC。code-reviewer 的 spec 合规检查是弥补这一差距的关键环节。

---

## 六、最有效的 prompt/context 策略是什么？

**最有效的策略：在 PLAN.md 中为每个 task 提供"实现要点"列表 + "验证步骤"列表，并在实现前将两者都注入到 agent 的上下文中。**

具体来说：

1. **实现要点列表**：每个 task 的 PLAN.md 包含 5-10 个实现要点，每个要点是一句话（如"14 个危险正则"、"5 种失败类型"）。这些要点充当了"实现检查清单"——agent 在实现时可以逐条对照，code-reviewer 在评审时也可以逐条检查。

2. **验证步骤列表**：每个 task 的 PLAN.md 包含 TDD 验证步骤（先写什么测试、确认 RED、实现、确认 GREEN）。这些步骤将"实现"和"验证"绑定在一起，消除了"先实现再补测试"的诱惑。

3. **HANDOFF.md 的接口速查**：在 Task 11-14 的实现中，HANDOFF.md 中的"关键技术接口速查"部分提供了所有组件的签名（构造函数参数、方法签名、返回类型）。这使得 agent 在实现 AgentLoop 时不需要重新阅读每个模块的源码——接口速查提供了足够的上下文。

**为什么有效**：AI agent 的上下文窗口是有限的。将关键信息（接口签名、实现要点、验证步骤）压缩到 PLAN.md 和 HANDOFF.md 中，比让 agent 自己在源码中搜索更高效。agent 在搜索源码时容易"走神"（发现无关的代码并产生不必要的修改），而结构化的 PLAN/HANDOFF 上下文让 agent 保持聚焦。

**不有效的策略**：在 prompt 中加入"请注意代码质量"、"请遵循最佳实践"等泛泛的指导。这些指导对 agent 的行为没有可量化的影响——agent 不会因为看到"请注意代码质量"就突然写出更好的代码。具体的、可检查的要点（如"使用 try/finally 关闭 SQLite 连接"）才有效。

---

## 七、凭据与分发迫使你想清楚了哪些原本会忽略的问题？

**凭据管理迫使想清楚的问题：**

1. **威胁模型**：在实现 CredentialManager 之前，"API key 安全"是一个模糊的概念。实现 AES-256-GCM + PBKDF2 后，威胁模型变得具体：加密文件可以被复制，但没有主密码无法解密；主密码不持久化到磁盘；`status()` 方法不回显明文。这些设计决策不是"安全最佳实践"的模板套用，而是对具体威胁的工程回应。

2. **状态管理**：`unlock()` 方法在开始时必须清除之前的状态（`_key = None`, `_data = {}`, `_unlocked = False`）。如果不清除，错误密码尝试后仍可能保持解锁状态。这个 bug 是 TDD 发现的——`test_wrong_password_fails` 在 GREEN 阶段失败。如果没有凭据管理的安全要求，我不会想到测试"错误密码后的状态"。

3. **文件权限**：`os.chmod(self._file_path, 0o600)` 在 Windows 上可能不生效。这个跨平台问题在实现时才暴露，说明"安全存储"不仅是加密算法的选择，还包括操作系统层面的访问控制。

**分发迫使想清楚的问题：**

1. **入口点设计**：`pyproject.toml` 的 `project.scripts` 入口点必须指向一个可调用对象（函数），而非一个对象（如 FastAPI 实例）。这个问题在 Task 14 中被忽略（直接写了 `the_harness.webui.app:app`），最终在代码评审中被发现。分发要求迫使你思考"用户如何启动你的程序"——这不是实现问题，而是产品问题。

2. **CI job 命名**：TASK.md 要求 CI 中必须有一个名为 `unit-test` 的 job。这个命名约束在实现时容易被忽略（自然倾向是叫 `test` 或 `pytest`）。分发和 CI 要求迫使你从"外部规范"的视角审视自己的工作，而非仅从"内部实现"的视角。

3. **Docker layer cache**：Dockerfile 应该先 `COPY pyproject.toml` 再 `COPY 源码`，利用 layer cache 加速重建。这个优化在"能跑就行"的心态下不会做，但分发要求迫使你考虑"别人构建你的镜像时的体验"。

---

## 八、如果重做会改变什么？

1. **拆分 Task 12**：WebUI task 过大，应拆分为"后端 API + WebSocket"和"前端 HTML/CSS/JS"两个 task。后端可以用 TDD 覆盖，前端用手动验证。拆分后每个 task 的偏离率会降低。

2. **在 SPEC 中加入反例**：对于"实时流式"等容易有多种解读的需求，SPEC 应该明确写出什么不算满足需求（如"事件不得在循环结束后批量发送"）。这比正面描述更有效。

3. **冷启动验证应更早**：冷启动验证（§4.5）发现了 7 处 spec 缺陷，这些缺陷在实现前就被修复了。如果冷启动验证更早（在 PLAN.md 完成后立即进行），可以避免更多的返工。

4. **并行执行更多 task**：Task 3-7,10 是可并行的，但实际执行是串行的。如果有多个 worktree 并行开发，总时间可以缩短 40-50%。但需要确保每个 worktree 的 agent 有独立的上下文，避免相互干扰。

5. **在 TDD 中加入"行为测试"**：当前的测试只验证"功能存在"，不验证"行为正确"（如 WebSocket 的实时性）。如果 TDD 中加入行为测试（如"事件必须在产生后 100ms 内发送"），可以更早发现 Task 12 的 Critical issue。

6. **更早创建真实 LLM Provider**：项目直到最终修复阶段才创建 `OpenAILLMProvider`。如果在 Task 3 就创建，可以在 Task 11（Agent Loop）的测试中用真实 LLM 做端到端验证，而不仅限于 mock。

---

## 九、对 Superpowers 方法论的批判——它假设了什么，这些假设成立吗？

**假设 1：subagent 具备文件写入能力。**

Superpowers 的 `subagent-driven-development` 假设 subagent 可以独立完成实现工作。但在实际环境中，可用的 subagent（如 `code-explorer`）可能只有搜索/读取能力，没有文件写入能力。这迫使主 agent 兼任"subagent"角色，削弱了"subagent 驱动"的核心价值——即让主 agent 从实现细节中抽身，专注于规划和评审。**这个假设在本项目中不成立。**

**假设 2：TDD 在所有 task 上都有价值。**

Superpowers 的 `test-driven-development` 假设所有实现都适合 TDD。但配置文件（Dockerfile、CI YAML、Makefile）和前端代码（HTML/CSS/JS）不适合用单元测试验证。强制在这些 task 上执行 TDD 会产生"形式测试"——测试存在但不提供实际价值。**这个假设在配置/前端 task 上不成立。**

**假设 3：code-reviewer subagent 的评审是客观的。**

Superpowers 假设 code-reviewer subagent 能提供客观的 spec 合规检查。但 code-reviewer 本身也是 LLM，它的"合规检查"依赖于它对 SPEC 的理解——如果 SPEC 有歧义，reviewer 可能不会发现。例如 Task 12 的"实时流式"问题，reviewer 在第一次评审时确实发现了（因为它理解"real-time"的含义），但如果 reviewer 的理解偏差与实现 agent 一致，偏离就不会被发现。**这个假设在大多数情况下成立，但不是绝对的。**

**假设 4：PLAN.md 的 task 颗粒度可以由一个 subagent 在一次会话内完成。**

这个假设在大多数 task 上成立（Task 2-11），但在 Task 12（WebUI）上不成立——这个 task 太大，一次会话内完成导致了 2 个 Critical issue。**这个假设需要"颗粒度验证"机制——在 PLAN 完成后评估每个 task 的复杂度，对过大的 task 进行拆分。**

**假设 5：worktree 隔离不会产生冲突。**

在串行执行的工作流中，这个假设成立。但如果并行执行多个 worktree（如 Task 3-7 同时开发），它们都修改 `pyproject.toml`（添加依赖），合并时会产生冲突。**这个假设在并行场景下不成立，需要额外的冲突解决策略。**

**总体评价**：Superpowers 方法论的核心价值在于"纪律强制"——TDD、两阶段评审、worktree 隔离、文档同步。这些纪律在 AI 协作中确实减少了偏离和遗漏。但方法论对 subagent 能力的假设过于乐观——在 subagent 能力受限的现实下，主 agent 需要承担更多实现工作，这削弱了"subagent 驱动"的自主性。方法论应该更明确地标注哪些假设是"理想条件"，并提供假设不成立时的降级方案。
