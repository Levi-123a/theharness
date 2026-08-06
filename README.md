# the-harness

一个自研的 Coding Agent Harness，聚焦于**反馈闭环**机制。给定一个失败的测试，agent 自主探索代码库、修改代码、运行测试、分类失败原因、并通过多轮自我修正直到测试通过。

## GitHub 项目网站

本项目托管在 GitHub 上，包含完整的源代码、CI/CD 配置、文档和发布历史。

- **仓库地址**：[https://github.com/Levi-123a/theharness](https://github.com/Levi-123a/theharness)
- **克隆命令**：`git clone https://github.com/Levi-123a/theharness.git`
- **Docker 镜像**：`ghcr.io/levi-123a/theharness:latest`（由 GitHub Actions 自动构建并推送到 GHCR）

### 仓库内容概览

| 目录/文件 | 说明 |
|-----------|------|
| `the_harness/` | 主源码包（agent 主循环、工具分发、护栏、反馈闭环、记忆、凭据管理、WebUI） |
| `tests/` | 全部单元测试（109 个，使用 mock-LLM，无需网络） |
| `demo.py` | 机制演示脚本（确定性复现 3 种核心行为） |
| `Dockerfile` | Docker 容器构建文件 |
| `.github/workflows/ci.yml` | GitHub Actions CI 配置（单元测试 + Docker 镜像构建推送） |
| `.gitlab-ci.yml` | GitLab CI 配置 |
| `SPEC.md` | 设计文档 |
| `PLAN.md` | 实现计划（14 个 task） |
| `SPEC_PROCESS.md` | 规约生成过程文档 |
| `AGENT_LOG.md` | 开发过程日志 |
| `REFLECTION.md` | 反思报告 |

### CI/CD 状态

每次推送到 `main` 分支时，GitHub Actions 会自动执行：
1. **unit-test**：安装依赖 → 运行 pytest 全量测试
2. **docker-build**：构建 Docker 镜像 → 推送到 GHCR（`ghcr.io/levi-123a/theharness:latest`）

## 功能特性

- **Agent 主循环**：自研编排（组织上下文 → 调用 LLM → 解析动作 → 执行 → 回灌反馈 → 停机判断）
- **自由模式**：用户用自然语言描述任务，agent 自主读写代码、执行命令来完成
- **反馈闭环（核心贡献）**：确定性测试校验器 → 失败分类器（5 种类型）→ 反馈回灌器
- **护栏**：5 类危险动作拦截，支持 HITL 人工审批
- **记忆**：项目上下文、会话历史、失败模式积累
- **凭据管理**：通过 OS 钥匙串（Windows Credential Manager / macOS Keychain / Linux Secret Service）安全存储，无需主密码；支持 `.env` 文件预配置
- **WebUI**：终端风格流式输出，会话历史侧边栏，模式切换（修复测试 / 自由模式），内置 API 密钥设置
- **Mock LLM**：确定性单元测试，无需网络或真实 LLM

## 安装

### Docker（推荐）

```bash
# 构建并运行
make docker-build
make docker-run
# 或手动：
docker build -t the-harness .
docker run -p 8000:8000 -v ~/.the-harness:/root/.the-harness the-harness
```

容器内默认无 OS 钥匙串，建议通过环境变量注入 API 密钥（见下方「API 密钥安全配置」）。

### 从源码安装

```bash
git clone https://github.com/Levi-123a/theharness.git
cd the-harness
make install   # 或: pip install -e ".[dev]"
```

## API 密钥安全配置

harness 提供两种 API 密钥配置方式，**查找优先级：OS 钥匙串 > 环境变量**。当钥匙串中已存储某 provider 的凭据时，环境变量将被忽略。

### 方式一：OS 钥匙串（推荐，最安全）

通过 `keyring` 库将密钥存入操作系统原生凭据存储：
- **Windows**：Credential Manager
- **macOS**：Keychain
- **Linux**：Secret Service（需安装 `gnome-keyring` 或 `kwallet`）

无需主密码，密钥由操作系统加密保护，不写入任何文件。

**通过 CLI 录入（隐藏输入）：**

```bash
the-harness-creds store
# 依次输入：provider 名称（如 openai）、API key（隐藏）、base_url、model
```

**通过 WebUI 录入：**

打开 `http://localhost:8000` → 点击右上角"设置"按钮 → 填入 provider、API key、base URL、model → 保存。

**凭据管理命令：**

| 命令 | 说明 |
|------|------|
| `the-harness-creds status` | 查看已配置的供应商（不显示明文） |
| `the-harness-creds store` | 添加/更新 API 密钥（存入 OS 钥匙串） |
| `the-harness-creds delete` | 删除某个供应商的密钥 |

### 方式二：环境变量（开发便利，明文）

通过 `.env` 文件预配置。**注意：`.env` 是明文文件，任何能读取该文件的进程/用户都能看到你的密钥；进程环境变量对子进程可见。** 仅建议用于本地开发或 Docker 容器。

**使用步骤：**

1. 复制模板文件：

```bash
cp .env.example .env
```

2. 编辑 `.env`，填入你自己的 API 密钥（不要使用引号）：

```ini
# OpenAI 兼容供应商配置（支持 OpenAI 官方、DeepSeek、Moonshot 等兼容端点）
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# DeepSeek 示例（取消注释并填入你的 DeepSeek key）
# OPENAI_API_KEY=sk-your-deepseek-key-here
# OPENAI_BASE_URL=https://api.deepseek.com/v1
# OPENAI_MODEL=deepseek-chat
```

3. `.env` 已被 `.gitignore` 排除，**绝不会**被提交到 Git。应用启动时会自动加载。

### 安全说明

- `status` 命令和 WebUI 状态接口只显示"已配置"，**从不回显明文**
- 密钥绝不记录日志、绝不提交 Git、绝不写入明文配置文件（`.env` 除外，作为开发便利，已明确标注风险）
- 首次运行无需引导——可直接通过 CLI、WebUI 录入，或配置 `.env`
- **威胁模型**：完整的凭据威胁模型见 [SPEC.md](./SPEC.md) §4.2

## 使用方法

### WebUI

1. 在浏览器中打开 `http://localhost:8000`
2. **配置 API 密钥**（首次使用）：点击"设置" → 填入 provider、API key、base URL、model → 保存（存入 OS 钥匙串，无需主密码）
3. **修复测试模式**：输入失败测试路径和工作目录 → 点击"开始修复" → 实时观看 agent 工作
4. **自由模式**：切换到"自由模式"标签 → 输入文字描述（如"给 main.py 添加一个 hello() 函数"）→ 输入工作目录 → 点击"发送" → Agent 自主读、写代码并执行命令完成您的请求

### CLI

```bash
python -m the_harness --test-path path/to/test_file.py --workspace ./project
```

## 机制演示

```bash
python demo.py
```

确定性复现以下行为：
1. 护栏拦截危险动作
2. 反馈闭环驱动自我修正（失败 → 修复 → 通过）
3. 失败分类 + 策略路由（4 种失败类型）

## 测试

```bash
make test
# 或
pytest
```

所有核心机制测试使用 mock LLM，无需网络或真实 API 密钥。

## 分发命令

| 命令 | 说明 |
|------|------|
| `make install` | 安装包 + 开发依赖 |
| `make test` | 运行全部测试 |
| `make run` | 启动 WebUI 服务（localhost:8000） |
| `make demo` | 运行 3 个机制演示 |
| `make docker-build` | 构建 Docker 镜像 |
| `make docker-run` | 运行 Docker 容器 |
| `the-harness-creds store` | 通过 OS 钥匙串配置 API 密钥 |

## 项目结构

```
the-harness/
├── the_harness/           # 主包
│   ├── agent_loop.py      # Agent 主循环
│   ├── cli.py             # 凭据管理 CLI
│   ├── llm/               # LLM 抽象层
│   ├── tools/             # 工具分发
│   ├── guardrail/         # 护栏
│   ├── feedback/          # 反馈闭环（核心）
│   ├── memory/            # 记忆存储
│   ├── credentials/       # 凭据管理
│   └── webui/             # WebUI（FastAPI）
├── tests/                 # TDD 测试
├── demo.py                # 机制演示
├── Dockerfile
├── pyproject.toml
├── .github/workflows/    # GitHub Actions CI
├── .gitlab-ci.yml         # GitLab CI 配置
├── SPEC.md                # 设计文档
├── PLAN.md                # 实现计划
├── SPEC_PROCESS.md        # 规约生成过程
├── AGENT_LOG.md           # 开发日志
└── REFLECTION.md          # 反思报告
```

## 部署架构

### 本地开发

```
浏览器  ──HTTP/WS──>  uvicorn (FastAPI)  ──>  AgentLoop  ──>  LLM 供应商
                                        │
                              ┌─────────┴──────────┐
                              │  工具分发器         │
                              │  护栏               │
                              │  测试校验器         │
                              │  反馈回灌器         │
                              │  记忆存储           │
                              └────────────────────┘
```

### Docker 容器

Docker 镜像（基于 `python:3.12-slim`）打包了完整应用：
- `docker build` 生成自包含镜像
- `docker run -p 8000:8000` 启动 WebUI 服务
- 容器内无 OS 钥匙串，通过环境变量注入 API 密钥（`-e OPENAI_API_KEY=...` 或 `--env-file .env`）

### 云部署

可部署到任意容器平台（Render / Railway / Fly.io / 阿里云）：

```bash
# 示例：Render.com
# 1. 连接 GitHub 仓库
# 2. 设置构建命令: docker build -t the-harness .
# 3. 设置启动命令: docker run -p 8000:8000 the-harness
# 4. 设置环境变量: OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL（见 .env.example）
```

**Render.com 一键部署：** 仓库根目录的 `render.yaml` 文件提供了 Render Blueprint 用于自动部署。将 GitHub 仓库连接到 Render 后，它会自动检测配置。

**线上部署地址：** https://the-harness.onrender.com/ （Render 免费层，首次访问需等 30-60 秒冷启动）

### CI/CD 管道

| 平台 | 配置文件 | Jobs |
|------|----------|------|
| GitHub Actions | `.github/workflows/ci.yml` | `unit-test`（pytest）→ `docker-build`（构建 + 推送到 GHCR） |
| GitLab CI | `.gitlab-ci.yml` | `unit-test`（pytest）→ `docker-build`（构建 + 推送到 registry） |

CI 在每次推送到 `main` 和每个 Pull Request 时运行。`unit-test` job 必须通过后才会运行 `docker-build`。

## 安全边界

- 所有文件操作限制在工作目录内
- 危险 shell 命令被拦截并需要审批
- API 密钥存入 OS 钥匙串（由操作系统加密保护），从不记录日志，从不提交到 Git
- Shell 执行隔离在工作目录内
- 路径遍历防护：工具分发器中的第二层检查确保解析后的路径不超出工作目录

## 已知限制

- **平台**：Linux x86_64（Docker）；源码安装需 Python 3.12+
- **测试框架**：目前仅支持 pytest
- **LLM 供应商**：默认 OpenAI；测试使用 mock 供应商；自由模式使用可配置的系统提示词
- **并发**：同时只能运行一个任务（修复或自由模式）

## 许可证

MIT
