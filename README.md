# the-harness

A self-implemented Coding Agent Harness focused on the **feedback loop** mechanism. Given a failing test, the agent autonomously explores the codebase, modifies code, runs tests, classifies failures, and self-corrects through multiple rounds until tests pass.

## Features

- **Agent Main Loop**: Self-implemented orchestration (context → LLM → action → feedback → stop)
- **Feedback Loop (Core Contribution)**: Deterministic test validator → failure classifier (5 types) → feedback injector
- **Guardrails**: 5 categories of dangerous action interception with HITL approval
- **Memory**: Project context, session history, failure pattern accumulation
- **Credential Management**: AES-256 encrypted storage with master password
- **WebUI**: Terminal-style streaming output with session history sidebar
- **Mock LLM**: Deterministic unit testing without network or real LLM

## Installation

### Docker (Recommended)

```bash
# Build and run
make docker-build
make docker-run
# Or manually:
docker build -t the-harness .
docker run -p 8000:8000 -v ~/.the-harness:/root/.the-harness the-harness
```

First run will guide you through secure API key setup.

### From Source

```bash
git clone https://github.com/Levi-123a/theharness.git
cd the-harness
make install   # or: pip install -e ".[dev]"
```

## API Key Security Configuration

On first run, the harness will prompt you to:
1. Set a master password (hidden input via `getpass`)
2. Enter your OpenAI API key (hidden input)

Keys are encrypted with AES-256 and stored in `~/.the-harness/credentials.enc`.
- Master password is never persisted to disk
- `status` command shows "configured" without revealing the key
- Update/clear keys via the settings interface

**First-run guided setup (CLI):**

```bash
the-harness-creds setup
```

This will:
1. Prompt for a master password (hidden input, min 8 chars)
2. Create an encrypted credential store (`~/.the-harness/credentials.enc`)
3. Optionally store your OpenAI API key (hidden input)

**Credential management commands:**

| Command | Description |
|---------|-------------|
| `the-harness-creds setup` | First-run guided credential setup |
| `the-harness-creds status` | Show configured providers (no plaintext) |
| `the-harness-creds store` | Add/update an API key |
| `the-harness-creds delete` | Remove a provider's key |
| `the-harness-creds unlock` | Unlock credential store |

**Threat model**: See [SPEC.md](./SPEC.md) §4.2 for the full credential threat model.

## Usage

### WebUI

1. Open `http://localhost:8000` in your browser
2. Enter the path to your failing test
3. Click "Start Fix"
4. Watch the agent work in real-time

### CLI

```bash
python -m the_harness --test-path path/to/test_file.py --workspace ./project
```

## Mechanism Demo

```bash
python demo.py
```

Deterministically reproduces:
1. Guardrail intercepts a dangerous action
2. Feedback loop drives self-correction (failure → fix → pass)
3. Failure classification + strategy routing (4 failure types)

## Testing

```bash
make test
# or
pytest
```

All core mechanism tests use mock LLM — no network or real API key required.

## Distribution Commands

| Command | Description |
|---------|-------------|
| `make install` | Install package + dev dependencies |
| `make test` | Run all tests |
| `make run` | Start WebUI server (localhost:8000) |
| `make demo` | Run 3 mechanism demonstrations |
| `make docker-build` | Build Docker image |
| `make docker-run` | Run Docker container |
| `the-harness-creds setup` | First-run guided API key setup |

## Project Structure

```
the-harness/
├── the_harness/           # Main package
│   ├── agent_loop.py      # Agent main loop
│   ├── cli.py             # Credential management CLI
│   ├── llm/               # LLM abstraction layer
│   ├── tools/             # Tool dispatch
│   ├── guardrail/         # Guardrails
│   ├── feedback/          # Feedback loop (core)
│   ├── memory/            # Memory store
│   ├── credentials/       # Credential management
│   └── webui/             # WebUI (FastAPI)
├── tests/                 # TDD tests
├── demo.py                # Mechanism demo
├── Dockerfile
├── pyproject.toml
├── .github/workflows/    # GitHub Actions CI
├── .gitlab-ci.yml         # GitLab CI config
├── SPEC.md                # Design document
├── PLAN.md                # Implementation plan
├── SPEC_PROCESS.md        # Brainstorming process
├── AGENT_LOG.md           # Development log
└── REFLECTION.md          # Reflection report
```

## Deployment Architecture

### Local Development

```
Browser  ──HTTP/WS──>  uvicorn (FastAPI)  ──>  AgentLoop  ──>  LLM Provider
                                              │
                                    ┌─────────┴──────────┐
                                    │  ToolDispatcher    │
                                    │  Guardrail         │
                                    │  TestValidator     │
                                    │  FeedbackInjector  │
                                    │  MemoryStore       │
                                    └────────────────────┘
```

### Docker Container

The Docker image (`python:3.12-slim` base) packages the entire application:
- `docker build` produces a self-contained image
- `docker run -p 8000:8000` starts the WebUI server
- Credentials are mounted via volume (`~/.the-harness`)

### Cloud Deployment

Deploy to any container platform (Render / Railway / Fly.io / Alibaba Cloud):

```bash
# Example: Render.com
# 1. Connect GitHub repo
# 2. Set build command: docker build -t the-harness .
# 3. Set start command: docker run -p 8000:8000 the-harness
# 4. Set environment variable: OPENAI_API_KEY (or use credential CLI)
```

**Render.com one-click deploy:** The `render.yaml` file in the repo root provides a Render Blueprint for automatic deployment. Connect your GitHub repo to Render, and it will auto-detect the configuration.

### CI/CD Pipeline

| Platform | Config File | Jobs |
|----------|------------|------|
| GitHub Actions | `.github/workflows/ci.yml` | `unit-test` (pytest) → `docker-build` (build + push to GHCR) |
| GitLab CI | `.gitlab-ci.yml` | `unit-test` (pytest) → `docker-build` (build + push to registry) |

CI runs on every push to `main` and every pull request. The `unit-test` job must pass before `docker-build` runs.

## Security Boundaries

- All file operations are restricted to the workspace directory
- Dangerous shell commands are intercepted and require approval
- API keys are encrypted at rest (AES-256-GCM), never logged, never committed to git
- Shell execution is isolated to the workspace
- Path traversal prevention: second-layer check in ToolDispatcher ensures resolved paths stay within workspace

## Known Limitations

- **Platform**: Linux x86_64 (Docker); Python 3.12+ required for source install
- **Test framework**: Currently supports pytest only
- **LLM provider**: OpenAI by default; mock provider for testing
- **Concurrency**: Single fix task at a time

## License

MIT
