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
