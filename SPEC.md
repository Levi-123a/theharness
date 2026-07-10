# SPEC.md — the-harness: Coding Agent Harness

> 由 brainstorming 技能驱动的设计文档。本项目为 AI4SE 期末项目 · A · Coding Agent Harness。

---

## 1. 问题陈述

### 1.1 要解决什么问题

当开发者有一个 failing test 时，定位问题、修改代码、运行测试、根据反馈再修正的循环是重复且耗时的。`the-harness` 是一个自研 Coding Agent Harness，能自主完成这一反馈闭环：给定一个 failing test 路径，agent 自主探索代码库 → 定位问题 → 修改代码 → 运行测试 → 根据测试反馈分类失败 → 将结构化反馈回灌给 LLM → 据此调整下一步动作 → 多轮修正直到测试通过。

### 1.2 目标用户

- 有 failing test 但不想手动调试的开发者
- 学习 AI4SE 的学生（理解 agent harness 内部机制）
- 需要 agent 自主修复代码的 CI/CD 场景

### 1.3 为什么值得做

反馈闭环是 coding agent 最核心的机制——它有最清晰、最可编码、最难以用提示词规避的形态。实现它意味着真正理解了"agent 如何从客观反馈中学习并自我修正"，而非仅靠 LLM 的智能猜测。

---

## 2. 用户故事

遵循 INVEST 原则（Independent, Negotiable, Valuable, Estimable, Small, Testable）：

1. **[修复 Failing Test]** — 作为开发者，我给定一个 failing test 路径，harness 自主修复代码直到测试通过，这样我无需手动调试。
2. **[安全配置 Key]** — 作为用户，我首次运行时被引导安全录入 API key（隐藏输入），这样我的 key 不会泄露。
3. **[查看修复过程]** — 作为用户，我能在 WebUI 实时看到 agent 的每一步思考和动作，这样我能理解修复过程并建立信任。
4. **[拦截危险操作]** — 作为用户，当 agent 试图执行危险命令时，我收到审批请求并可以拒绝，这样我的系统不会被破坏。
5. **[查看历史会话]** — 作为用户，我能查看过去的修复会话记录，这样我能回顾哪些修复成功/失败及原因。

---

## 3. 功能规约

按模块拆分，每项描述输入 / 行为 / 输出 / 边界条件 / 错误处理。

### 3.1 Agent 主循环（AgentLoop）

- **输入**：`Task`（包含 failing test 路径、工作目录路径）、`Config`（最大轮次、LLM 供应商配置等）
- **行为**：组织上下文 → 调用 LLM → 解析动作 → 护栏检查 → 分发执行 → 校验器运行测试 → 分类器分类失败 → 回灌反馈 → 停机判断 → 循环或终止
- **输出**：`Result`（success: bool, rounds: int, reason: str, action_history: list）
- **边界条件**：最大轮次默认 5，可配置；工作目录外操作被拒绝
- **错误处理**：LLM 调用失败时重试 1 次，仍失败则停机；动作解析失败时回灌"请返回规范 JSON"

### 3.2 LLM 抽象层（LLMProvider）

- **输入**：`context`（系统提示 + 对话历史 + 结构化反馈）
- **输出**：结构化 JSON `{"action": "...", "params": {...}, "reasoning": "..."}`
- **行为**：`OpenAIProvider` 调用 OpenAI Chat Completions API；`MockLLMProvider` 返回预设的动作序列
- **边界条件**：上下文超限时截断最早的历史消息
- **错误处理**：API 超时/限流时重试 1 次；返回非 JSON 时回灌格式要求

### 3.3 工具分发（ToolDispatch）

- **输入**：`Action`（类型 + 参数）
- **行为**：根据动作类型执行对应操作
- **输出**：`ActionResult`（success, output, error）
- **边界条件**：所有文件操作限制在工作目录内；shell 命令在工作目录执行
- **错误处理**：文件不存在返回错误；shell 命令非零退出码返回 stderr

| 动作 | 输入 | 行为 | 输出 |
|-----|------|------|------|
| `read_file` | 文件路径 | 读取文件内容 | 文本内容 |
| `edit_file` | 路径 + 旧文本 + 新文本 | 精确字符串替换 | 成功/失败 |
| `write_file` | 路径 + 内容 | 创建/覆盖文件 | 成功/失败 |
| `run_shell` | 命令字符串 | 在工作目录执行 | stdout/stderr/exit_code |
| `run_tests` | 测试路径 | 调用 TestValidator | TestResult |
| `give_up` | 原因 | 触发停机 | - |

### 3.4 护栏（Guardrail）

- **输入**：`Action`
- **行为**：正则匹配危险模式 + 路径越界检查
- **输出**：`GuardrailResult`（blocked: bool, reason: str）
- **边界条件**：仅检查 `run_shell` 和文件操作动作
- **错误处理**：拦截后通过 HITL 请求用户审批

拦截规则：
1. 文件删除类：`rm -rf`、`del /s`、`git clean -fd`
2. Git 危险操作：`git push --force`、`git reset --hard`、`git push` 到远程
3. 网络外发类：`curl|sh`、`wget|sh`、`scp`、`rsync`
4. 系统级操作：`sudo`、`chmod 777`、修改 `/etc/`、`C:\Windows\`
5. 工作目录越界：任何访问工作目录之外的文件系统操作

### 3.5 反馈闭环（FeedbackLoop）— 重点深入维度

#### 3.5.1 确定性校验器（TestValidator）

- **输入**：测试文件路径
- **行为**：执行 `pytest --tb=short`，捕获 stdout/stderr/exit_code
- **输出**：`TestResult`（exit_code, stdout, stderr, passed）
- **边界条件**：测试超时默认 30 秒
- **错误处理**：pytest 不存在时返回环境错误

#### 3.5.2 失败分类器（FailureClassifier）

- **输入**：`TestResult`
- **行为**：正则匹配输出文本，分类为 5 种类型之一
- **输出**：`ClassifiedFeedback`（type, location, message, expected, actual, strategy_hint）
- **边界条件**：纯确定性，同输入每次同输出
- **错误处理**：无法匹配任何模式时归类为 `unknown_failure`

| 失败类型 | 匹配模式 | 提取字段 | 策略提示 |
|---------|---------|---------|---------|
| `compile_error` | `SyntaxError\|IndentationError` | location, message | "修复语法错误" |
| `assertion_failure` | `AssertionError\|assert` | expected, actual | "检查逻辑是否正确" |
| `environment_error` | `ModuleNotFoundError\|ImportError\|FileNotFoundError` | missing_module | "检查依赖是否安装" |
| `timeout` | 超时标志 | timeout_limit | "检查死循环或性能" |
| `pass` | exit_code == 0 | - | - |

#### 3.5.3 反馈回灌器（FeedbackInjector）

- **输入**：`ClassifiedFeedback`
- **行为**：将分类结果转为结构化 prompt 片段，注入下一轮上下文
- **输出**：结构化文本片段
- **边界条件**：每轮只注入当前失败的摘要，不累积历史失败全文

### 3.6 记忆（MemoryStore）

- **输入**：`Task`、当前失败类型
- **行为**：按需查询相关记忆片段，注入上下文
- **输出**：上下文片段
- **边界条件**：不预加载整个代码库；跨会话只保留摘要

存储内容：
1. `project_context.json`：项目元信息（语言、测试框架、目录布局）
2. `session_history.db`（SQLite）：每会话动作序列和结果摘要
3. `failure_patterns.json`：跨会话失败→成功策略映射

### 3.7 凭据管理（CredentialManager）

- **输入**：主密码、API key
- **行为**：AES 加密存储、解密读取、状态查看（不回显）、清除
- **输出**：存储/读取/状态/删除结果
- **边界条件**：主密码不持久化；加密文件权限 600
- **错误处理**：主密码错误时拒绝解密；文件不存在时引导首次设置

### 3.8 WebUI（FastAPI）

- **输入**：HTTP 请求（新建修复任务、查询历史、WebSocket 连接）
- **行为**：接收 test 路径 → 启动 agent → WebSocket 推送实时输出 → 存储会话历史
- **输出**：流式 JSON 事件、历史会话列表
- **边界条件**：同时只运行一个修复任务
- **错误处理**：agent 异常时推送错误事件并记录

---

## 4. 非功能性需求

### 4.1 性能

- 单轮 LLM 调用 + 工具执行 + 测试运行 < 60 秒
- WebUI WebSocket 延迟 < 1 秒推送
- 完整修复任务（5 轮上限）< 5 分钟

### 4.2 安全（含凭据威胁模型）

**凭据威胁模型与对策：**

| 威胁 | 对策 |
|------|------|
| 明文存储 | AES-256 加密存储，密文落盘 |
| 主密码暴力破解 | PBKDF2 迭代 100,000 次 + 随机 salt |
| 主密码持久化 | 不写入磁盘，仅存进程内存，退出即清除 |
| 肩窥攻击 | 录入时隐藏输入（`getpass`），status 不回显明文 |
| 文件权限过宽 | 加密文件权限 600（仅 owner 可读写） |
| 进程内存 dump | key 使用后尽快从局部变量清除；不写入日志 |
| Git 提交泄露 | `.gitignore` 排除凭据文件；提交前自查 |

**动作安全：**
- 工作目录围栏：所有文件操作限制在工作目录内
- 危险命令拦截：护栏正则匹配 + HITL 审批
- Shell 执行隔离：在工作目录内执行，不暴露系统环境

### 4.3 可用性

- WebUI 界面简洁：左侧历史会话，右侧终端流式输出
- 首次运行引导：交互式录入 API key
- 错误信息清晰：agent 每步动作和结果都可见

### 4.4 可观测性

- 每轮动作记录到 `session_history.db`
- WebUI 实时展示 agent 思考过程、执行动作、测试结果
- 完整修复日志可导出

---

## 5. 系统架构

### 5.1 组件图

```
┌─────────────────────────────────────────────────┐
│                   WebUI (FastAPI)                │
│         终端流式 + 历史会话侧边栏                  │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Agent Main Loop                     │
│  组织上下文 → 调用LLM → 解析动作 → 分发执行       │
│  → 回灌结果 → 停机判断                           │
└──┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │
┌──▼───┐ ┌──▼────┐ ┌───▼───┐ ┌───▼────┐
│ Tool │ │ Guard │ │Feed-  │ │Memory  │
│Dis-  │ │rail  │ │back   │ │Store   │
│patch │ │      │ │Loop   │ │        │
└──────┘ └──────┘ └───────┘ └────────┘
   │                        │
┌──▼──────────┐    ┌───────▼────────┐
│ LLM Provider │    │ Test Validator │
│ (OpenAI/Mock)│    │ (pytest runner)│
└─────────────┘    └────────────────┘
```

### 5.2 数据流

1. 用户通过 WebUI 提交 failing test 路径
2. Agent Main Loop 启动
3. MemoryStore 组织上下文（注入项目约定 + 相关代码片段）
4. LLMProvider 调用 LLM 获取动作
5. Guardrail 检查动作安全性
6. 安全 → ToolDispatch 执行动作；危险 → HITL 审批
7. TestValidator 运行测试
8. FailureClassifier 解析结果并分类
9. FeedbackInjector 将结构化反馈回灌给 LLM
10. 停机判断：通过/超轮次/重复动作/放弃/危险拒绝
11. 未停机 → 回到步骤 3；停机 → 结果返回 WebUI

### 5.3 外部依赖

- **LLM 供应商**：OpenAI Chat Completions API（默认），可扩展 Anthropic 等
- **测试框架**：pytest（harness 内部测试 + 用户项目测试执行）
- **Python 库**：`openai`、`cryptography`、`fastapi`、`uvicorn`、`websockets`、`pytest`

---

## 6. 数据模型

### 6.1 主要实体

```
Task
├── test_path: str          # failing test 文件路径
├── workspace: str          # 工作目录路径
└── config: Config

Config
├── max_rounds: int         # 默认 5
├── llm_provider: str       # "openai" | "mock"
└── model: str              # "gpt-4o-mini" 等

Action
├── type: str               # "read_file" | "edit_file" | "run_shell" | ...
├── params: dict            # 动作参数
└── reasoning: str          # LLM 的推理过程

TestResult
├── exit_code: int
├── stdout: str
├── stderr: str
└── passed: bool

ClassifiedFeedback
├── type: str               # "compile_error" | "assertion_failure" | ...
├── location: str | None
├── message: str | None
├── expected: str | None
├── actual: str | None
└── strategy_hint: str

Result
├── success: bool
├── rounds: int
├── reason: str
└── action_history: list[Action]

GuardrailResult
├── blocked: bool
└── reason: str
```

### 6.2 存储实体

```
project_context.json
├── language: str           # "python"
├── test_framework: str     # "pytest"
├── lint_tool: str | None   # "ruff" | "flake8" | None
└── structure: dict         # 目录布局摘要

session_history.db (SQLite)
├── sessions
│   ├── id: int
│   ├── test_path: str
│   ├── success: bool
│   ├── rounds: int
│   ├── created_at: datetime
│   └── reason: str
└── actions
    ├── id: int
    ├── session_id: int (FK)
    ├── round: int
    ├── action_type: str
    ├── action_params: str (JSON)
    └── result: str (JSON)

failure_patterns.json
├── failure_type: str
├── successful_strategy: str
└── occurrence_count: int
```

---

## 7. 凭据与分发设计

### 7.1 Key 存储方案

- **存储方式**：AES-256 加密文件，`~/.the-harness/credentials.enc`
- **密钥派生**：PBKDF2（主密码 + 随机 salt，100,000 次迭代）
- **录入流程**：首次运行 → 提示设置主密码（`getpass` 隐藏输入）→ 输入 API key → 加密存储
- **查看流程**：输入主密码解锁 → 显示 `{"openai": "configured"}`（不回显明文）
- **更新流程**：输入主密码解锁 → 输入新 key → 重新加密
- **清除流程**：输入主密码解锁 → 删除指定 provider 的 key

### 7.2 分发形态

- **形态**：Docker 容器镜像
- **构建**：`docker build -t the-harness .`
- **运行**：`docker run -p 8000:8000 -v ~/.the-harness:/root/.the-harness the-harness`
- **Registry**：推送到 Docker Hub（公开）
- **CI 构建**：GitHub Actions 中 `docker build` + `docker push`
- **目标平台**：Linux x86_64（Docker 跨平台）
- **Key 在目标机的安全配置**：首次 `docker run` 时交互式引导录入，加密存储在挂载的 volume 中

---

## 8. 技术选型与理由

| 决策 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12 | LLM SDK 生态最成熟；pytest 测试体系完善；文本处理能力强；开发效率高 |
| LLM 供应商 | 多供应商（默认 OpenAI） | 抽象层设计为可切换接口；满足"可接任意供应商"要求；mock 实现用于确定性测试 |
| Web 框架 | FastAPI | 轻量、原生 WebSocket 支持、自动文档；Python 生态内最佳选择 |
| 测试框架 | pytest | 成熟稳定；fixture 体系适合 mock 注入；CI 友好 |
| 加密库 | cryptography | 成熟稳定；AES + PBKDF2 支持完善 |
| 数据库 | SQLite | 无需额外服务；适合单机场景；Python 内置支持 |
| 分发 | Docker | 单命令启动；环境隔离；CI 自动构建；WebUI 部署友好 |
| 部署平台 | Render / Fly.io | 免费额度；支持 Docker 部署；公网可访问 URL |
| 前端设计系统 | 原生 HTML/JS + CSS | WebUI 为终端流式界面，交互简单（WebSocket 推送 + 历史列表），无需复杂组件库。经评估 Open Design 适用于组件丰富的 UI 场景，本项目 UI 复杂度低，使用原生技术栈更轻量、减少依赖。若后续 UI 复杂度提升，可引入 Open Design。 |

---

## 9. 验收标准

| 功能 | 完成标准 |
|-----|---------|
| Agent 主循环 | mock-LLM 下走完成功/放弃/超轮次/重复动作 4 条分支，测试全绿 |
| 反馈闭环 | 5 种失败分类各有测试覆盖，分类器确定性验证通过（同输入同输出） |
| 护栏 | 5 类危险动作各被拦截，安全动作放行，确定性验证通过 |
| 凭据管理 | 加密存储→读取→状态不回显→清除，全链路测试通过 |
| WebUI | 输入 test 路径→开始修复→实时流式输出→历史记录可查 |
| 分发 | `docker build` + `docker run` 一条命令启动 |
| 机制演示 | `python demo.py` 确定性复现 3 种行为 |
| CI | `unit-test` job 通过；Docker 镜像构建成功 |
| 部署 | 公网 URL 可访问 WebUI |

---

## 10. 风险与未决问题

1. **LLM 输出格式不稳定** — LLM 可能不总是返回规范 JSON。对策：解析器有容错处理，解析失败时回灌"请返回规范 JSON 格式"。
2. **pytest 输出格式差异** — 不同 pytest 版本输出格式可能不同。对策：分类器正则覆盖常见格式，CI 固定 pytest 版本。
3. **上下文窗口膨胀** — 多轮修正后上下文可能超限。对策：每轮只注入结构化反馈摘要，不保留完整对话历史。
4. **WebUI 部署成本** — 需要公网可访问 URL。对策：使用免费部署平台（Render / Fly.io）。
5. **Docker 内 pytest 依赖** — 容器内需要能运行用户的项目测试。对策：容器预装常见 Python 工具链，用户项目通过 volume 挂载。
6. **真实 LLM 成本** — 开发阶段频繁调用 OpenAI API 产生费用。对策：开发用 mock-LLM，只在最终集成测试时用真实 LLM。

---

## 11. 领域与机制设计（§A.5 额外要求）

### 11.1 领域：Coding

本 harness 面向 coding 场景：读写代码、执行命令、运行测试、根据测试结果自我修正。

### 11.2 四类机制设计

#### 动作 / 工具

agent 能执行的操作：`read_file`、`edit_file`、`write_file`、`run_shell`、`run_tests`、`give_up`。全部为确定性代码实现，受工作目录围栏限制。

#### 客观反馈信号

**测试运行结果**是核心反馈信号——客观、确定、可回灌。`TestValidator` 运行 pytest，`FailureClassifier` 将结果分类为 5 种类型，`FeedbackInjector` 将结构化反馈回灌给 agent 驱动自我修正。这是本项目的重点深入维度。

#### 危险动作

护栏拦截 5 类危险操作（文件删除、git 危险操作、网络外发、系统操作、工作目录越界），拦截后触发 HITL 审批。护栏是纯正则 + 路径检查的确定性代码。

#### 记忆

跨会话存储项目约定、历史决策摘要、失败模式经验。按需注入：主循环根据当前失败类型查询相关记忆片段，不全量载入。

### 11.3 六个维度的最低实现（§A.4-D）

| 维度 | 最低实现 | 代码位置 |
|------|---------|---------|
| 决策 | Agent 主循环的停机判断与动作路由 | `agent_loop.py` |
| 工具 | 6 种动作的分发执行 + 工作目录围栏 | `tools/dispatcher.py` |
| 记忆 | 项目约定存储 + 按需查询注入 | `memory/store.py` |
| 治理 | 5 类危险动作拦截 + HITL 审批 | `guardrail/guardrail.py` |
| 反馈 | 校验器 → 分类器 → 回灌器三段链路（**重点深入**） | `feedback/` |
| 配置 | Config 数据类 + CredentialManager 加密存储 | `config.py`, `credentials/manager.py` |

六个维度均有可运行的最低实现，其中 **反馈** 维度作为主要贡献深入实现。

### 11.4 重点维度：反馈闭环

选择 **反馈闭环** 作为主要贡献，理由：
- 最契合 coding 场景的核心价值（运行测试 → 解析 → 自我修正）
- 机制链路完整：校验器 → 分类器 → 回灌器，三段全部是确定性代码
- 天然串联"工具执行"和"治理"两个维度
- mock-LLM 下可完整测试，满足 §A.4-C 的"移除 LLM 后仍可验证"判据
- 深度体现：5 条分类分支 + 5 种策略路由 + 停机判断逻辑，每条可独立单测

### 11.5 机制编码实现（呼应 §A.4）

| 机制 | 代码实现 | 可确定性测试 |
|------|---------|-------------|
| 主循环 | `agent_loop.py` — 编排上下文/LLM/动作/反馈/停机 | ✓ mock-LLM 驱动所有分支 |
| 工具分发 | `tools/dispatcher.py` — 动作执行 | ✓ 传入构造动作验证 |
| 护栏 | `guardrail/guardrail.py` — 正则匹配 + 路径检查 | ✓ 传入危险动作断言拦截 |
| 校验器 | `feedback/validator.py` — 运行 pytest 解析结果 | ✓ mock pytest 输出 |
| 分类器 | `feedback/classifier.py` — 正则分类 5 种类型 | ✓ 传入 TestResult 验证分类 |
| 回灌器 | `feedback/injector.py` — 结构化反馈转 prompt | ✓ 验证不同类型注入不同策略 |
| 记忆 | `memory/store.py` — 按需查询注入 | ✓ mock 存储验证查询逻辑 |
| 停机判断 | `agent_loop.py` — 5 种停机条件 | ✓ mock-LLM 触发各条件 |

所有机制移除真实 LLM 后，仍可用 mock-LLM 驱动的确定性单元测试验证。
