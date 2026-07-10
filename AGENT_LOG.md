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
