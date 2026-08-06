本反思报告由本人整理反思得出，由 glm5.2 进行了补充完善。

## 一、哪些 Superpowers 技能发挥了最大作用、哪些"形式大于实质"

**发挥最大作用：**

1. **`test-driven-development`** — 价值最高。本项目最终积累 137 个测试，每一次重大修复都靠 TDD 兜底：
   - 凭据重构为 keyring 时，RED 阶段发现 `cred_manager` fixture 的 `with patch(...)` 作用域 bug——fixture 返回后 patch 退出，后续操作会污染真实系统钥匙串。没有先写测试，这个 bug 会在测试中悄悄写入开发者的真实凭据。
   - 多轮轮数计数 bug 修复时，先写 `test_parse_error_does_not_consume_round` 等 5 个测试，设置 `max_rounds=1` + 一个失败动作 + 一个成功动作，断言最终 `success=True`。这个测试精确锁定了"非生产性迭代不应消耗轮数"的语义。

2. **`using-git-worktrees`** — 每个 task 在独立分支开发，main 始终可运行。`--no-ff` 合并保留完整分支历史，14 个 task 的 commit 链条可追溯。

3. **`requesting-code-review` 两阶段评审** — code-reviewer 在 Task 8 发现 timeout 字符串匹配偏差（只匹配 `"timed out"` 遗漏 `"timeout"`），在 Task 11 发现 `credential_manager` 死代码参数和 `execute()` 返回值被丢弃。这些是功能测试通过但行为不合规的典型。

4. **`brainstorming`** — 帮我把模糊想法逐步细化为可执行的设计；但它不会主动检查设计是否覆盖外部规范的所有要求，需人工对照 TASK.md 逐项核。

**"形式大于实质"：**

1. **`finishing-a-development-branch`** — 单人项目中每次都选 "merge with --no-ff"，决策过程价值较低。

## 二、TDD 是阻碍还是放大器

**是放大器，但有前提：测试本身必须足够简单、且被测代码是"机制代码"。**

放大效应：
- **接口先行**：Task 8 先写测试，明确输入 `TestResult`、输出 `ClassifiedFeedback`、5 种类型各有 `strategy_hint`。接口在测试中固化后，实现只需"让测试通过"。
- **回归保护**：14 个 task 串行合并，137 个测试在数秒内跑完，是 AI 协作中保持质量纪律的基础设施。
- **Bug 发现**：凭据 fixture 作用域 bug、`unlock()` 状态管理 bug，都是 GREEN 阶段失败暴露的。

阻碍的一面：
- Task 14（Dockerfile + CI YAML）不适合单测，"先写测试"退化为形式。
- Task 12 前端 HTML/CSS/JS 无法用 TDD 覆盖，只有后端 API 可测试。

**判据**：这段代码能否用 mock 输入产生确定性输出？能，TDD 价值极高；不能，TDD 退化为形式。这恰恰是 vibe coding 学习者最该内化的判据——它区分了"能被纪律守住的部分"和"只能靠人判断的部分"。

## 三、subagent 能自主运行多久不偏离

**约 15-25 分钟（一个 task 的完整 TDD 循环），超过后偏离风险显著增加。**

三种典型偏离模式（本项目实际发生）：
1. **接口膨胀**：Task 11 主 agent 自作主张添加 `credential_manager` 构造参数——SPEC 中没有，是"看到模块觉得应该用上"。
2. **架构走偏**：Task 12 WebSocket 事件被批量收集后发送，违背"实时流式"。测试只检查事件内容不检查时序，所以测试不失败。
3. **正则匹配偏差**：Task 8 只匹配 `"timed out"` 遗漏 `"timeout"`——SPEC 明确写了，agent 选了第一个想到的字符串。

**关键发现**：subagent 系统性偏向"更简单的实现"。TDD 的 RED 只能捕获"功能缺失"型偏离，"功能存在但行为偏差"型偏离需要 code-reviewer 的 spec 合规检查。对习惯凭感觉接受 AI 输出的学习者而言，这是最该警惕的：靠感觉会漏掉所有"看起来对、其实偏了"的情况。

## 四、什么样的 task 颗粒度最优

**一个 task = 一个模块 = 3-8 个测试 = 15-25 分钟。**

- 效果最好：Task 5（Guardrail，12 个测试）、Task 8（Classifier，9 个测试）——独立、可确定性测试、接口清晰。
- 颗粒度过大：Task 12（WebUI）含后端+WebSocket+前端，产生 2 个 Critical issue。应拆为"后端 API"和"前端"两个 task。
- 颗粒度过小：Task 1（Scaffolding）只有 2 个测试，TDD 价值有限，但作为奠基 task 必要。

串行依赖的 task（如 Classifier→Injector）应合并以减少 worktree 切换；可并行的 task（Task 3-7,10）可适当拆细。

## 五、SPEC/PLAN 质量如何影响实现质量

**案例：Task 8 timeout 字符串匹配偏差（规约清楚但仍偏离）**

SPEC.md 明确写了匹配 `"timeout"`，PLAN Task 8 实现要点也写了 `exit_code == -1 or "timeout" in stderr`。但 agent 实现的正则只匹配 `"timed out"`（pytest 实际输出），遗漏 `"timeout"`。

这说明：**SPEC 质量高不等于实现不偏离**——agent 实现时可能不逐条对照 SPEC。code-reviewer 的 spec 合规检查（逐条对照 PLAN 实现要点）是弥补这一差距的关键。

**反例：Task 12 "实时流式"需求（规约模糊导致偏离）**

SPEC 写了"实时流式输出"，PLAN 写了 `stream agent output events in real-time`。但 "real-time" 有多种合理解读——"每个事件产生后立即发送"还是"循环结束后批量发送"？agent 选了后者（更简单且测试不失败）。

**教训**：当 SPEC 存在多种合理解读时，agent 系统性选择更简单的解读。应在 SPEC 中加入**反例**——明确说明什么不算满足需求（如"事件不得在循环结束后批量发送"）。

## 六、最有效的 prompt/context 策略

**在 PLAN.md 中为每个 task 提供"实现要点列表" + "验证步骤列表"，并在实现前将两者都注入 agent 上下文。**

三个具体策略：
1. **实现要点列表**：每个 task 5-10 个一句话要点（如"14 个危险正则"、"5 种失败类型"）。这是实现检查清单，也是 reviewer 的评审依据。
2. **验证步骤列表**：TDD 步骤绑定实现，消除"先实现再补测试"的诱惑。
3. **HANDOFF.md 接口速查**：Task 11-14 实现时，HANDOFF.md 的"接口速查"提供所有组件签名，agent 不需重新阅读每个模块源码。

**为什么有效**：agent 上下文窗口有限。结构化的 PLAN/HANDOFF 上下文比让 agent 自己在源码中搜索更高效——后者容易"走神"（发现无关代码并产生不必要修改）。

**不有效**：prompt 中加"请注意代码质量"、"遵循最佳实践"等泛泛指导——对 agent 行为无可量化影响。具体的、可检查的要点（如"使用 try/finally 关闭 SQLite 连接"）才有效。

## 七、凭据与分发迫使想清楚的问题

**凭据管理：**
1. **部署环境的能力边界**：原 AES-256 + PBKDF2 + 主密码方案在开发机看似合理，部署到 Render 容器后致命——容器无 gnome-keyring，主密码无法交互输入，原方案根本无法运行。重构为 keyring + 环境变量降级才解决。**教训：凭据方案必须考虑目标部署环境，而非仅考虑开发机便利性。**
2. **跨平台异常差异**：keyring 在 Linux 桌面正常工作，但无桌面环境的容器抛 `RuntimeError` 而非返回 None——这与 macOS/Windows 行为不同。只在 Render 部署后才暴露。**教训：跨平台代码必须 catch 所有异常，且必须在目标部署环境实际测试。**
3. **TDD 的安全价值**：重构 keyring 时 RED 阶段发现 fixture 作用域 bug，避免了测试污染真实钥匙串。

**分发：**
1. **入口点设计**：`pyproject.toml` 的 `project.scripts` 必须指向可调用对象（函数），不是 ASGI 对象。Task 14 直接写 `the_harness.webui.app:app` 是错的。
2. **CI job 命名约束**：TASK.md 要求 CI 中必须有一个名为 `unit-test` 的 job。自然倾向是叫 `test` 或 `pytest`。分发要求迫使从"外部规范"视角审视工作。
3. **GHCR 推送认证**：`docker/build-push-action` 的 `push: true` 不会自动登录 GHCR，需显式 `docker/login-action` + `permissions: packages: write`。

## 八、如果重做会改变什么

1. **拆分 Task 12**：WebUI 应拆为"后端 API + WebSocket"和"前端 HTML/CSS/JS"两个 task。
2. **SPEC 中加入反例**：对"实时流式"等易有多种解读的需求，明确写出什么不算满足。
3. **冷启动验证更早**：在 PLAN.md 完成后立即进行，而非等到实现阶段。
4. **并行执行更多 task**：Task 3-7,10 可并行，串行执行浪费了 40-50% 时间。
5. **TDD 加入"行为测试"**：当前只验证"功能存在"，不验证"行为正确"（如 WebSocket 实时性）。加入行为测试可更早发现 Task 12 的 Critical issue。
6. **更早创建真实 LLM Provider**：项目直到最终修复阶段才创建 `OpenAILLMProvider`。若 Task 3 就创建，Task 11 可用真实 LLM 做端到端验证。
7. **重大重构后立即检查文档一致性**：2026-08-05 凭据从 AES 重构为 keyring 后，SPEC 和 REFLECTION 中的旧描述未被清理，直到 2026-08-06 才修复。应在每次重大重构后 grep 全部文档中提及该方案的位置。

## 九、对 Superpowers 方法论的批判——它假设了什么

**假设 1：subagent 具备文件写入能力。** 不成立。可用 subagent（如 code-explorer）只有搜索/读取能力，迫使主 agent 兼任"subagent"角色，削弱了"subagent 驱动"的核心价值。

**假设 2：TDD 在所有 task 上都有价值。** 部分不成立。配置文件（Dockerfile、CI YAML）和前端代码不适合单测，强制 TDD 会产生"形式测试"。

**假设 3：code-reviewer 评审是客观的。** 大多数情况成立，但非绝对。reviewer 也是 LLM，若它的理解偏差与实现 agent 一致，偏离就不会被发现。

**假设 4：PLAN.md task 颗粒度可由一个 subagent 一次会话完成。** 多数 task 成立，但 Task 12（WebUI）不成立——太大导致 2 个 Critical issue。需要"颗粒度验证"机制。

**假设 5：worktree 隔离不会产生冲突。** 串行执行成立，并行执行（Task 3-7 同时修改 `pyproject.toml` 添加依赖）会产生冲突。

**假设 6：文档会自动与代码保持一致。** 不成立。本次发现 6 处文档与代码不一致（SPEC/REFLECTION 仍写 AES 方案，实际已是 keyring）。方法论未强调"重大重构后必须同步检查所有文档"。

**总体评价**：Superpowers 的核心价值在"纪律强制"——TDD、两阶段评审、worktree 隔离、文档同步。这些纪律在 AI 协作中确实减少了偏离和遗漏，也守住了 vibe coding 学习者最容易松懈的环节。但方法论对 subagent 能力的假设过于乐观，且未提供"假设不成立时的降级方案"。方法论应更明确标注哪些假设是"理想条件"，并提供降级路径。对我而言最深的体会是：当 LLM 能完成大部分编码工作时，工程师的真正价值不在"写得出代码"，而在能识别并挡住 AI 偷懒、跑偏、自作主张的地方——而纪律，是把这种判断力落到执行层面的唯一方式。
