// the-harness WebUI 前端逻辑

const chatEl = document.getElementById('chat');
const chatWrap = document.getElementById('chat-wrap');
const sessionList = document.getElementById('session-list');
const sessionEmpty = document.getElementById('session-empty');
const startBtn = document.getElementById('start-btn');
const instructBtn = document.getElementById('instruct-btn');
const testPathInput = document.getElementById('test-path');
const workspaceInput = document.getElementById('workspace');
const workspaceFreeformInput = document.getElementById('workspace-freeform');
const instructionInput = document.getElementById('instruction');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const modalClose = document.getElementById('modal-close');
const connStatus = document.getElementById('conn-status');
const newChatBtn = document.getElementById('new-chat-btn');

let currentMode = 'fix';
// 对话历史：用于续接对话。每次用户发送消息时，将之前的对话作为上下文
// 传给后端。"新对话"按钮清空此数组。
let conversationHistory = [];
// 当前 WebSocket 回复气泡的最终文本（用于回复完成后记入历史）
let pendingReplyText = '';
// 当前数据库会话 ID — 用于续接对话时将新消息追加到同一会话
let currentDbSessionId = null;

// ── 状态指示 ──────────────────────────────────────────────

function setStatus(state, label) {
    connStatus.className = 'conn-status ' + state;
    connStatus.textContent = label;
}

// ── 聊天气泡辅助 ──────────────────────────────────────────

function pad2(n) { return String(n).padStart(2, '0'); }

function timestamp() {
    const d = new Date();
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function scrollToBottom() {
    chatWrap.scrollTop = chatWrap.scrollHeight;
}

// 用户消息（右侧蓝色气泡）
function addUserBubble(text, sub) {
    const row = document.createElement('div');
    row.className = 'msg-row user';
    const bubble = document.createElement('div');
    bubble.className = 'bubble user-bubble';
    bubble.textContent = text;
    if (sub) {
        const s = document.createElement('div');
        s.className = 'bubble-sub';
        s.textContent = sub;
        bubble.appendChild(s);
    }
    const t = document.createElement('div');
    t.className = 'msg-time';
    t.textContent = timestamp();
    row.appendChild(t);
    row.appendChild(bubble);
    chatEl.appendChild(row);
    scrollToBottom();
}

// agent 消息（左侧浅色气泡）
// headline: 大字主内容（AI 的实际回复 / 命令输出 / 测试输出 / 结束原因）
// type: 用于头像和色条
// meta: 小字标签（动作名/参数/状态摘要），显示在气泡顶部
// detail: 折叠详情（命令输出、stdout 等），可选
function addAgentBubble(text, type, detail, meta) {
    const row = document.createElement('div');
    row.className = 'msg-row agent';

    const avatar = document.createElement('div');
    avatar.className = 'avatar avatar-' + (type || 'info');
    avatar.textContent = AVATAR_ICON[type] || '·';

    const col = document.createElement('div');
    col.className = 'msg-col';

    const bubble = document.createElement('div');
    bubble.className = 'bubble agent-bubble b-' + (type || 'info');

    // 小字标签（动作名/状态摘要）—— 放在气泡顶部
    if (meta) {
        const m = document.createElement('div');
        m.className = 'bubble-meta';
        m.textContent = meta;
        bubble.appendChild(m);
    }

    // 大字主内容
    const body = document.createElement('div');
    body.className = 'bubble-headline';
    body.textContent = text;
    bubble.appendChild(body);

    // 详情子块（可选）
    if (detail) {
        const d = document.createElement('div');
        d.className = 'bubble-detail';
        d.textContent = detail;
        bubble.appendChild(d);
    }

    const t = document.createElement('div');
    t.className = 'msg-time';
    t.textContent = timestamp();

    col.appendChild(bubble);
    col.appendChild(t);
    row.appendChild(avatar);
    row.appendChild(col);
    chatEl.appendChild(row);
    scrollToBottom();
}

const AVATAR_ICON = {
    action: '▶',
    exec_ok: '✓',
    exec_err: '✗',
    feedback: '⟳',
    result: '★',
    error: '!',
    info: 'AI',
};

// 创建一个可累积的 agent 回复气泡。
// 一次用户输入只产生一个回复气泡：后续 action/execution/feedback
// 事件都更新或追加到这同一个气泡里，而不是各开一个新气泡。
function createReplyBubble() {
    const row = document.createElement('div');
    row.className = 'msg-row agent';
    const avatar = document.createElement('div');
    avatar.className = 'avatar avatar-action';
    avatar.textContent = AVATAR_ICON.action;
    const col = document.createElement('div');
    col.className = 'msg-col';
    const bubble = document.createElement('div');
    bubble.className = 'bubble agent-bubble b-action';
    const metaEl = document.createElement('div');
    metaEl.className = 'bubble-meta';
    metaEl.style.display = 'none';
    const headlineEl = document.createElement('div');
    headlineEl.className = 'bubble-headline';
    const detailEl = document.createElement('div');
    detailEl.className = 'bubble-detail';
    detailEl.style.display = 'none';
    bubble.appendChild(metaEl);
    bubble.appendChild(headlineEl);
    bubble.appendChild(detailEl);
    const t = document.createElement('div');
    t.className = 'msg-time';
    t.textContent = timestamp();
    col.appendChild(bubble);
    col.appendChild(t);
    row.appendChild(avatar);
    row.appendChild(col);
    chatEl.appendChild(row);
    scrollToBottom();
    return {
        row,
        setHeadline(text, type) {
            headlineEl.textContent = text;
            if (type) {
                bubble.className = 'bubble agent-bubble b-' + type;
                avatar.className = 'avatar avatar-' + type;
                avatar.textContent = AVATAR_ICON[type] || '·';
            }
            scrollToBottom();
        },
        setMeta(text) {
            metaEl.textContent = text || '';
            metaEl.style.display = text ? 'block' : 'none';
        },
        appendDetail(label, content) {
            const entry = document.createElement('div');
            entry.className = 'detail-entry';
            if (label) {
                const lbl = document.createElement('div');
                lbl.className = 'detail-label';
                lbl.textContent = label;
                entry.appendChild(lbl);
            }
            const cnt = document.createElement('div');
            cnt.className = 'detail-content';
            cnt.textContent = content;
            entry.appendChild(cnt);
            detailEl.appendChild(entry);
            detailEl.style.display = 'block';
            scrollToBottom();
        },
    };
}

// 低价值的成功原因 —— 不作为独立内容展示
const LOW_VALUE_REASONS = /^(done|task completed|all tests passed|任务完成|任务成功)$/i;

function addSystemNotice(text) {
    const row = document.createElement('div');
    row.className = 'msg-row system';
    const n = document.createElement('div');
    n.className = 'system-notice';
    n.textContent = text;
    row.appendChild(n);
    chatEl.appendChild(row);
    scrollToBottom();
}

function clearChat() {
    chatEl.innerHTML = '';
}

// ── 会话列表空状态 ────────────────────────────────────────

function toggleEmptyState(count) {
    sessionEmpty.style.display = count === 0 ? 'block' : 'none';
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
        clearChat();
        loadSessions();
    });
});

// ── 会话列表 ──────────────────────────────────────────────

// 批量删除状态
let selectionMode = false;
const selectedIds = new Set();
let currentWorkspace = '.';
let lastSessions = [];
const batchDeleteBtn = document.getElementById('batch-delete-btn');
const batchToolbar = document.getElementById('batch-toolbar');
const batchCount = document.getElementById('batch-count');
const batchConfirmBtn = document.getElementById('batch-confirm-btn');
const batchCancelBtn = document.getElementById('batch-cancel-btn');

async function loadSessions() {
    const ws = (currentMode === 'fix' ? workspaceInput.value : workspaceFreeformInput.value) || '.';
    currentWorkspace = ws;
    try {
        const resp = await fetch('/api/sessions?workspace=' + encodeURIComponent(ws));
        lastSessions = await resp.json();
        renderSessions();
    } catch (e) {
        console.error('加载会话列表失败:', e);
    }
}

function renderSessions() {
    const sessions = lastSessions;
    const ws = currentWorkspace;
    sessionList.innerHTML = '';
    toggleEmptyState(sessions.length);
    // "批量删除" 入口仅在非选择模式且有会话时可见
    batchDeleteBtn.style.display = (sessions.length > 0 && !selectionMode) ? 'block' : 'none';
    for (const s of sessions) {
        const li = document.createElement('li');
        if (selectionMode) li.classList.add('batch-mode');
        if (selectedIds.has(s.id)) li.classList.add('selected');

        if (selectionMode) {
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.className = 'session-checkbox';
            cb.checked = selectedIds.has(s.id);
            cb.onclick = (e) => e.stopPropagation();
            cb.onchange = () => toggleSelection(s.id);
            li.appendChild(cb);
        }

        const label = document.createElement('span');
        label.className = 'session-label';
        // Prefer AI-generated summary; fall back to test_path/description
        const displayText = s.summary || s.test_path || s.description || '';
        label.textContent = `#${s.id} ${displayText}`;
        label.title = displayText; // tooltip with full text on hover
        li.appendChild(label);

        const badge = document.createElement('span');
        badge.className = 'badge ' + (s.success ? 'success' : 'fail');
        badge.textContent = s.success ? '通过' : '失败';
        li.appendChild(badge);

        if (!selectionMode) {
            const delBtn = document.createElement('button');
            delBtn.className = 'del-btn';
            delBtn.textContent = '×';
            delBtn.title = '删除此会话';
            delBtn.onclick = (e) => { e.stopPropagation(); deleteSession(s.id); };
            li.appendChild(delBtn);
            li.onclick = () => loadSessionDetail(s.id, ws);
        } else {
            // 选择模式下点击整行切换选中状态
            li.onclick = () => toggleSelection(s.id);
        }

        sessionList.appendChild(li);
    }
    updateBatchCount();
}

function toggleSelection(id) {
    if (selectedIds.has(id)) {
        selectedIds.delete(id);
    } else {
        selectedIds.add(id);
    }
    renderSessions();
}

function updateBatchCount() {
    batchCount.textContent = `已选 ${selectedIds.size} 项`;
    batchConfirmBtn.disabled = selectedIds.size === 0;
}

function enterBatchMode() {
    selectionMode = true;
    selectedIds.clear();
    batchToolbar.style.display = 'flex';
    renderSessions();
}

function exitBatchMode() {
    selectionMode = false;
    selectedIds.clear();
    batchToolbar.style.display = 'none';
    renderSessions();
}

async function deleteSession(id) {
    if (!confirm(`确定删除会话 #${id} 吗？此操作不可撤销。`)) return;
    try {
        const resp = await fetch(
            `/api/sessions/${id}?workspace=${encodeURIComponent(currentWorkspace)}`,
            { method: 'DELETE' }
        );
        if (resp.status === 404) {
            addAgentBubble('会话不存在或已被删除', 'error');
        }
        loadSessions();
    } catch (e) {
        addAgentBubble('删除失败: ' + e.message, 'error');
    }
}

async function confirmBatchDelete() {
    if (selectedIds.size === 0) return;
    const ids = Array.from(selectedIds);
    if (!confirm(`确定删除选中的 ${ids.length} 个会话吗？此操作不可撤销。`)) return;
    try {
        const resp = await fetch(
            `/api/sessions/batch-delete?workspace=${encodeURIComponent(currentWorkspace)}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids }),
            }
        );
        const data = await resp.json();
        if (data.ok) {
            addSystemNotice(`已删除 ${data.deleted} 个会话`);
        }
        exitBatchMode();
        loadSessions();
    } catch (e) {
        addAgentBubble('批量删除失败: ' + e.message, 'error');
    }
}

batchDeleteBtn.addEventListener('click', enterBatchMode);
batchCancelBtn.addEventListener('click', exitBatchMode);
batchConfirmBtn.addEventListener('click', confirmBatchDelete);

async function loadSessionDetail(id, workspace) {
    try {
        const resp = await fetch(`/api/sessions/${id}?workspace=${encodeURIComponent(workspace)}`);
        const data = await resp.json();
        clearChat();
        // 设置当前 DB 会话 ID，使后续提问追加到同一会话
        currentDbSessionId = data.id;
        // 显示用户消息（freeform 用 description，fix 模式用 test_path）
        // description 可能包含多行（续接对话时追加的问题）
        const userMsg = data.description || data.test_path || '';
        if (userMsg) {
            const lines = userMsg.split('\n').filter(l => l.trim());
            for (const line of lines) {
                addUserBubble(line, `会话 #${data.id}`);
            }
        } else {
            addAgentBubble(`目标: 无`, 'info', null, `会话 #${data.id}`);
        }

        const actions = data.actions || [];

        // 渲染所有 actions，每个 action 独立一个气泡
        // 这样多轮任务的所有中间步骤都可见
        for (const a of actions) {
            const reply = createReplyBubble();
            const params = a.action_params || {};
            const paramsStr = Object.keys(params).length ? JSON.stringify(params) : '';
            reply.setMeta(a.action_type + (paramsStr ? ' ' + paramsStr : '') + ` · 第${a.round}轮`);
            const headline = a.reasoning || a.action_type || '';
            reply.setHeadline(headline, 'action');
            if (a.result) {
                reply.appendDetail('执行结果', a.result);
            }
        }

        // 显示 AI 最终回复文本（如果与最后一个 action 的 reasoning 不同）
        const lastAction = actions.length > 0 ? actions[actions.length - 1] : null;
        const lastReasoning = lastAction ? (lastAction.reasoning || '') : '';
        if (data.final_reply && data.final_reply !== lastReasoning) {
            const reply = createReplyBubble();
            reply.setHeadline(data.final_reply, data.success ? 'result' : 'error');
        }

        // 失败原因作为独立通知显示（不覆盖 action 内容）
        if (!data.success && data.reason && !LOW_VALUE_REASONS.test(data.reason.trim())) {
            addAgentBubble(data.reason, 'error');
        }
    } catch (e) {
        console.error('加载会话详情失败:', e);
    }
}

// ── 修复测试模式 ──────────────────────────────────────────

startBtn.addEventListener('click', async () => {
    const testPath = testPathInput.value.trim();
    const workspace = workspaceInput.value.trim() || '.';
    if (!testPath) {
        addAgentBubble('请输入测试文件路径', 'error');
        testPathInput.focus();
        return;
    }

    startBtn.disabled = true;
    setStatus('running', '运行中');
    clearChat();
    addUserBubble('修复测试 ' + testPath, '工作目录: ' + workspace);

    try {
        const resp = await fetch('/api/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ test_path: testPath, workspace: workspace }),
        });
        const data = await resp.json();
        if (data.detail) {
            addAgentBubble('请求失败: ' + data.detail, 'error');
            startBtn.disabled = false;
            setStatus('error', '错误');
            return;
        }
        testPathInput.value = '';
        testPathInput.focus();
        const sessionId = data.session_id;
        connectWebSocket('fix', sessionId);
    } catch (e) {
        addAgentBubble('请求异常: ' + e.message, 'error');
        startBtn.disabled = false;
        setStatus('error', '错误');
    }
});

// ── 自由模式 ──────────────────────────────────────────────

instructBtn.addEventListener('click', async () => {
    const description = instructionInput.value.trim();
    const workspace = workspaceFreeformInput.value.trim() || '.';
    if (!description) {
        addAgentBubble('请输入指令', 'error');
        instructionInput.focus();
        return;
    }

    instructBtn.disabled = true;
    setStatus('running', '运行中');
    // 不清空聊天 —— 续接对话时保留之前的消息
    addUserBubble(description, '工作目录: ' + workspace);
    pendingReplyText = '';

    try {
        const resp = await fetch('/api/instruct', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                description: description,
                workspace: workspace,
                history: conversationHistory,
                session_id: currentDbSessionId,
            }),
        });
        const data = await resp.json();
        if (data.detail) {
            addAgentBubble('请求失败: ' + data.detail, 'error');
            instructBtn.disabled = false;
            setStatus('error', '错误');
            return;
        }
        instructionInput.value = '';
        instructionInput.focus();
        const sessionId = data.session_id;
        connectWebSocket('instruct', sessionId, description);
    } catch (e) {
        addAgentBubble('请求异常: ' + e.message, 'error');
        instructBtn.disabled = false;
        setStatus('error', '错误');
    }
});

// Ctrl+Enter 发送
instructionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        instructBtn.click();
    }
});

// ── WebSocket 连接 ────────────────────────────────────────

function connectWebSocket(mode, sessionId, userMessage) {
    const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/${mode}/${sessionId}`;
    const ws = new WebSocket(wsUrl);

    setStatus('connected', '已连接');
    // 每一轮 action 产生一个新的回复气泡，这样多轮任务的所有
    // 中间结果都可见，而非仅显示最后一轮。
    let reply = null;
    function newReply() {
        reply = createReplyBubble();
        return reply;
    }
    function ensureReply() {
        if (!reply) reply = newReply();
        return reply;
    }

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'action') {
            // 每个 action 事件代表一轮新的尝试 → 创建新气泡
            newReply();
            const params = msg.data.params;
            const paramsStr = Object.keys(params).length ? JSON.stringify(params) : '';
            // reasoning 是 AI 的实际思考 → 作为气泡主内容
            const headline = msg.data.reasoning || msg.data.action;
            reply.setHeadline(headline, 'action');
            reply.setMeta(msg.data.action + (paramsStr ? ' ' + paramsStr : ''));
            // 记录回复文本用于对话历史
            if (msg.data.reasoning) pendingReplyText = msg.data.reasoning;
        } else if (msg.type === 'execution') {
            // 执行输出折叠到当前气泡的详情区
            const output = msg.data.error
                ? '错误: ' + msg.data.error + (msg.data.output ? '\n' + msg.data.output : '')
                : (msg.data.output || (msg.data.success ? '完成' : '失败'));
            const label = msg.data.action + (msg.data.success ? ' · 成功' : ' · 失败');
            ensureReply().appendDetail(label, output);
        } else if (msg.type === 'feedback') {
            // 测试输出折叠到当前气泡的详情区
            const verdict = msg.data.passed ? '通过' : '未通过';
            const output = msg.data.stdout || (msg.data.passed ? '测试通过' : '测试失败');
            ensureReply().appendDetail('测试 ' + verdict, output);
        } else if (msg.type === 'result') {
            // 捕获数据库会话 ID（用于续接对话时追加到同一会话）
            if (msg.data.session_id) {
                currentDbSessionId = msg.data.session_id;
            }
            // 抑制低价值的成功信息；仅失败时更新主内容
            const reason = (msg.data.reason || '').trim();
            if (!msg.data.success) {
                if (!LOW_VALUE_REASONS.test(reason)) {
                    ensureReply().setHeadline(reason || '任务失败', 'error');
                }
                if (reason) pendingReplyText = reason;
            }
        } else if (msg.type === 'error') {
            ensureReply().setHeadline(msg.data.message, 'error');
        }
    };

    ws.onclose = () => {
        startBtn.disabled = false;
        instructBtn.disabled = false;
        setStatus('idle', '就绪');
        // 将本次对话记入历史，供下次续接
        if (userMessage && pendingReplyText) {
            conversationHistory.push({ role: 'user', content: userMessage });
            conversationHistory.push({ role: 'assistant', content: pendingReplyText });
        }
        pendingReplyText = '';
        loadSessions();
    };

    ws.onerror = () => {
        ensureReply().setHeadline('WebSocket 连接错误', 'error');
        startBtn.disabled = false;
        instructBtn.disabled = false;
        setStatus('error', '连接错误');
    };
}

// ── 新对话 ────────────────────────────────────────────────

newChatBtn.addEventListener('click', () => {
    conversationHistory = [];
    pendingReplyText = '';
    currentDbSessionId = null;
    clearChat();
    addAgentBubble('已开始新对话，请输入您的需求。', 'info');
});

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

// Esc 关闭弹窗
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && settingsModal.style.display === 'flex') {
        settingsModal.style.display = 'none';
    }
});

async function refreshCredStatus() {
    const statusText = document.getElementById('cred-status-text');

    try {
        const resp = await fetch('/api/credentials/status');
        const data = await resp.json();

        const count = Object.keys(data.providers || {}).length;
        if (count === 0) {
            statusText.textContent = '暂无已存储的密钥，请在下方添加。';
        } else {
            statusText.textContent = `已配置 ${count} 个服务商。`;
        }
        renderProviderList(data.providers || {});
    } catch (e) {
        statusText.textContent = '检查状态出错: ' + e.message;
    }
}

function renderProviderList(providers) {
    const list = document.getElementById('cred-provider-list');
    list.innerHTML = '';
    const providerNames = Object.keys(providers);
    if (providerNames.length === 0) {
        const li = document.createElement('li');
        li.innerHTML = '<span style="color: var(--text-faint)">暂无已存储的密钥</span>';
        list.appendChild(li);
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
        addLine('删除失败: ' + e.message, 'error');
    }
}

// 保存密钥
document.getElementById('cred-store-btn').addEventListener('click', async () => {
    const provider = document.getElementById('cred-provider-name').value.trim();
    const apiKey = document.getElementById('cred-key-input').value.trim();
    const baseUrl = document.getElementById('cred-base-url').value.trim();
    const model = document.getElementById('cred-model').value.trim();
    if (!provider) { addLine('请输入服务商名称', 'error'); return; }
    if (!apiKey) { addLine('请输入 API 密钥', 'error'); return; }
    try {
        const resp = await fetch('/api/credentials/store', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: provider, api_key: apiKey, base_url: baseUrl, model: model }),
        });
        const data = await resp.json();
        if (data.detail) { addLine(data.detail, 'error'); return; }
        document.getElementById('cred-provider-name').value = '';
        document.getElementById('cred-key-input').value = '';
        document.getElementById('cred-base-url').value = '';
        document.getElementById('cred-model').value = '';
        refreshCredStatus();
    } catch (e) {
        addLine('保存失败: ' + e.message, 'error');
    }
});

// ── 初始化 ────────────────────────────────────────────────

toggleEmptyState(0);
loadSessions();
setStatus('idle', '就绪');
