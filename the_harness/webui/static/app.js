// the-harness WebUI 前端逻辑

const terminal = document.getElementById('terminal');
const sessionList = document.getElementById('session-list');
const startBtn = document.getElementById('start-btn');
const instructBtn = document.getElementById('instruct-btn');
const testPathInput = document.getElementById('test-path');
const workspaceInput = document.getElementById('workspace');
const workspaceFreeformInput = document.getElementById('workspace-freeform');
const instructionInput = document.getElementById('instruction');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const modalClose = document.getElementById('modal-close');

let currentMode = 'fix';

// ── 终端辅助 ──────────────────────────────────────────────

function addLine(text, cls) {
    const div = document.createElement('div');
    div.className = 'terminal-line ' + (cls || '');
    div.textContent = text;
    terminal.appendChild(div);
    terminal.scrollTop = terminal.scrollHeight;
}

function clearTerminal() {
    terminal.innerHTML = '';
}

// ── 模式切换 ──────────────────────────────────────────────

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const mode = tab.dataset.mode;
        if (mode === currentMode) return;
        currentMode = mode;
        document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
        document.getElementById('input-bar-fix').style.display = mode === 'fix' ? 'flex' : 'none';
        document.getElementById('input-bar-freeform').style.display = mode === 'freeform' ? 'flex' : 'none';
        clearTerminal();
    });
});

// ── 会话列表 ──────────────────────────────────────────────

async function loadSessions() {
    const ws = (currentMode === 'fix' ? workspaceInput.value : workspaceFreeformInput.value) || '.';
    try {
        const resp = await fetch('/api/sessions?workspace=' + encodeURIComponent(ws));
        const sessions = await resp.json();
        sessionList.innerHTML = '';
        for (const s of sessions) {
            const li = document.createElement('li');
            li.textContent = `#${s.id} ${s.test_path || s.description || ''}`;
            const badge = document.createElement('span');
            badge.className = 'badge ' + (s.success ? 'success' : 'fail');
            badge.textContent = s.success ? '通过' : '失败';
            li.appendChild(badge);
            li.onclick = () => loadSessionDetail(s.id, ws);
            sessionList.appendChild(li);
        }
    } catch (e) {
        console.error('加载会话列表失败:', e);
    }
}

async function loadSessionDetail(id, workspace) {
    try {
        const resp = await fetch(`/api/sessions/${id}?workspace=${encodeURIComponent(workspace)}`);
        const data = await resp.json();
        clearTerminal();
        addLine(`会话 #${data.id}`, 'result');
        addLine(`测试: ${data.test_path || data.description || '无'}`);
        addLine(`成功: ${data.success}`);
        addLine(`轮次: ${data.rounds}`);
        addLine(`原因: ${data.reason}`);
    } catch (e) {
        console.error('加载会话详情失败:', e);
    }
}

// ── 修复测试模式 ──────────────────────────────────────────

startBtn.addEventListener('click', async () => {
    const testPath = testPathInput.value.trim();
    const workspace = workspaceInput.value.trim() || '.';
    if (!testPath) {
        alert('请输入测试文件路径');
        return;
    }

    startBtn.disabled = true;
    clearTerminal();
    addLine(`开始修复 ${testPath}...`, 'action');

    try {
        const resp = await fetch('/api/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ test_path: testPath, workspace: workspace }),
        });
        const data = await resp.json();
        if (data.detail) {
            addLine(`错误: ${data.detail}`, 'error');
            startBtn.disabled = false;
            return;
        }
        const sessionId = data.session_id;
        connectWebSocket('fix', sessionId);
    } catch (e) {
        addLine('错误: ' + e.message, 'error');
        startBtn.disabled = false;
    }
});

// ── 自由模式 ──────────────────────────────────────────────

instructBtn.addEventListener('click', async () => {
    const description = instructionInput.value.trim();
    const workspace = workspaceFreeformInput.value.trim() || '.';
    if (!description) {
        alert('请输入指令');
        return;
    }

    instructBtn.disabled = true;
    clearTerminal();
    addLine(`指令: ${description}`, 'action');
    addLine(`工作目录: ${workspace}`, 'action');
    addLine('---', 'result');

    try {
        const resp = await fetch('/api/instruct', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: description, workspace: workspace }),
        });
        const data = await resp.json();
        if (data.detail) {
            addLine(`错误: ${data.detail}`, 'error');
            instructBtn.disabled = false;
            return;
        }
        const sessionId = data.session_id;
        connectWebSocket('instruct', sessionId);
    } catch (e) {
        addLine('错误: ' + e.message, 'error');
        instructBtn.disabled = false;
    }
});

// ── WebSocket 连接 ────────────────────────────────────────

function connectWebSocket(mode, sessionId) {
    const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/${mode}/${sessionId}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'action') {
            addLine(`[操作] ${msg.data.action} ${JSON.stringify(msg.data.params)}`, 'action');
            if (msg.data.reasoning) {
                addLine(`  原因: ${msg.data.reasoning}`, 'action');
            }
        } else if (msg.type === 'execution') {
            const status = msg.data.success ? '成功' : '失败';
            addLine(`[执行 ${status}] ${msg.data.action}`, msg.data.success ? 'feedback' : 'error');
            if (msg.data.output) {
                addLine(msg.data.output, 'feedback');
            }
            if (msg.data.error) {
                addLine(`  错误: ${msg.data.error}`, 'error');
            }
        } else if (msg.type === 'feedback') {
            addLine(`[反馈] 通过=${msg.data.passed} 退出码=${msg.data.exit_code}`, 'feedback');
            if (msg.data.stdout) addLine(msg.data.stdout, 'feedback');
        } else if (msg.type === 'result') {
            addLine(`[结果] 成功=${msg.data.success} 轮次=${msg.data.rounds} 原因=${msg.data.reason}`, 'result');
        } else if (msg.type === 'error') {
            addLine(`[错误] ${msg.data.message}`, 'error');
        }
    };

    ws.onclose = () => {
        addLine('--- 会话已结束 ---', 'result');
        startBtn.disabled = false;
        instructBtn.disabled = false;
        loadSessions();
    };

    ws.onerror = () => {
        addLine('WebSocket 连接错误', 'error');
        startBtn.disabled = false;
        instructBtn.disabled = false;
    };
}

// ── 设置弹窗 ──────────────────────────────────────────────

settingsBtn.addEventListener('click', () => {
    settingsModal.style.display = 'flex';
    refreshCredStatus();
});

modalClose.addEventListener('click', () => {
    settingsModal.style.display = 'none';
});

settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
        settingsModal.style.display = 'none';
    }
});

async function refreshCredStatus() {
    const statusText = document.getElementById('cred-status-text');
    const setupSection = document.getElementById('cred-setup-section');
    const unlockSection = document.getElementById('cred-unlock-section');
    const manageSection = document.getElementById('cred-manage-section');

    try {
        const resp = await fetch('/api/credentials/status');
        const data = await resp.json();

        if (!data.exists) {
            statusText.textContent = '未找到凭据存储，请在下方创建。';
            setupSection.style.display = 'block';
            unlockSection.style.display = 'none';
            manageSection.style.display = 'none';
        } else if (!data.unlocked) {
            statusText.textContent = '凭据存储已存在但已锁定。';
            setupSection.style.display = 'none';
            unlockSection.style.display = 'block';
            manageSection.style.display = 'none';
        } else {
            statusText.textContent = '已解锁，请在下方管理您的 API 密钥。';
            setupSection.style.display = 'none';
            unlockSection.style.display = 'none';
            manageSection.style.display = 'block';
            renderProviderList(data.providers);
        }
    } catch (e) {
        statusText.textContent = '检查状态出错: ' + e.message;
    }
}

function renderProviderList(providers) {
    const list = document.getElementById('cred-provider-list');
    list.innerHTML = '';
    const providerNames = Object.keys(providers);
    if (providerNames.length === 0) {
        list.innerHTML = '<li>暂无已存储的密钥。</li>';
        return;
    }
    for (const name of providerNames) {
        const info = providers[name];
        const li = document.createElement('li');
        const urlStr = info.base_url ? ` | 地址: ${info.base_url}` : '';
        const modelStr = info.model ? ` | 模型: ${info.model}` : '';
        li.innerHTML = `<span><strong>${name}</strong>: ******${urlStr}${modelStr}</span>`;
        const delBtn = document.createElement('button');
        delBtn.textContent = '删除';
        delBtn.className = 'btn-small btn-danger';
        delBtn.onclick = () => deleteProvider(name);
        const editBtn = document.createElement('button');
        editBtn.textContent = '编辑';
        editBtn.className = 'btn-small';
        editBtn.onclick = () => editProvider(name, info);
        li.appendChild(editBtn);
        li.appendChild(delBtn);
        list.appendChild(li);
    }
}

function editProvider(name, info) {
    document.getElementById('cred-provider-name').value = name;
    document.getElementById('cred-key-input').value = '';
    document.getElementById('cred-base-url').value = info.base_url || '';
    document.getElementById('cred-model').value = info.model || '';
    document.getElementById('cred-key-input').focus();
}

async function deleteProvider(name) {
    try {
        await fetch(`/api/credentials/${name}`, { method: 'DELETE' });
        refreshCredStatus();
    } catch (e) {
        alert('删除失败: ' + e.message);
    }
}

// 创建凭据存储
document.getElementById('setup-btn').addEventListener('click', async () => {
    const password = document.getElementById('setup-password').value;
    if (!password) { alert('请输入密码'); return; }
    try {
        const resp = await fetch('/api/credentials/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_password: password }),
        });
        const data = await resp.json();
        if (data.detail) { alert(data.detail); return; }
        document.getElementById('setup-password').value = '';
        refreshCredStatus();
    } catch (e) {
        alert('创建失败: ' + e.message);
    }
});

// 解锁
document.getElementById('unlock-btn').addEventListener('click', async () => {
    const password = document.getElementById('unlock-password').value;
    if (!password) { alert('请输入密码'); return; }
    try {
        const resp = await fetch('/api/credentials/unlock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_password: password }),
        });
        const data = await resp.json();
        if (data.detail) { alert(data.detail); return; }
        document.getElementById('unlock-password').value = '';
        refreshCredStatus();
    } catch (e) {
        alert('解锁失败: ' + e.message);
    }
});

// 保存密钥
document.getElementById('cred-store-btn').addEventListener('click', async () => {
    const provider = document.getElementById('cred-provider-name').value.trim();
    const apiKey = document.getElementById('cred-key-input').value.trim();
    const baseUrl = document.getElementById('cred-base-url').value.trim();
    const model = document.getElementById('cred-model').value.trim();
    if (!provider) { alert('请输入服务商名称'); return; }
    if (!apiKey) { alert('请输入 API 密钥'); return; }
    try {
        const resp = await fetch('/api/credentials/store', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: provider, api_key: apiKey, base_url: baseUrl, model: model }),
        });
        const data = await resp.json();
        if (data.detail) { alert(data.detail); return; }
        document.getElementById('cred-provider-name').value = '';
        document.getElementById('cred-key-input').value = '';
        document.getElementById('cred-base-url').value = '';
        document.getElementById('cred-model').value = '';
        refreshCredStatus();
    } catch (e) {
        alert('保存失败: ' + e.message);
    }
});

// ── 初始化 ────────────────────────────────────────────────

loadSessions();
