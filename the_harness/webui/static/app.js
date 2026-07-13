// the-harness WebUI frontend logic

const terminal = document.getElementById('terminal');
const sessionList = document.getElementById('session-list');
const startBtn = document.getElementById('start-btn');
const testPathInput = document.getElementById('test-path');
const workspaceInput = document.getElementById('workspace');

function addLine(text, cls) {
    const div = document.createElement('div');
    div.className = 'terminal-line ' + (cls || '');
    div.textContent = text;
    terminal.appendChild(div);
    terminal.scrollTop = terminal.scrollHeight;
}

async function loadSessions() {
    const ws = workspaceInput.value || '.';
    try {
        const resp = await fetch('/api/sessions?workspace=' + encodeURIComponent(ws));
        const sessions = await resp.json();
        sessionList.innerHTML = '';
        for (const s of sessions) {
            const li = document.createElement('li');
            li.textContent = `#${s.id} ${s.test_path}`;
            const badge = document.createElement('span');
            badge.className = 'badge ' + (s.success ? 'success' : 'fail');
            badge.textContent = s.success ? 'PASS' : 'FAIL';
            li.appendChild(badge);
            li.onclick = () => loadSessionDetail(s.id, ws);
            sessionList.appendChild(li);
        }
    } catch (e) {
        console.error('Failed to load sessions:', e);
    }
}

async function loadSessionDetail(id, workspace) {
    try {
        const resp = await fetch(`/api/sessions/${id}?workspace=${encodeURIComponent(workspace)}`);
        const data = await resp.json();
        terminal.innerHTML = '';
        addLine(`Session #${data.id}`, 'result');
        addLine(`Test: ${data.test_path}`);
        addLine(`Success: ${data.success}`);
        addLine(`Rounds: ${data.rounds}`);
        addLine(`Reason: ${data.reason}`);
    } catch (e) {
        console.error('Failed to load session:', e);
    }
}

startBtn.addEventListener('click', async () => {
    const testPath = testPathInput.value.trim();
    const workspace = workspaceInput.value.trim() || '.';
    if (!testPath) {
        alert('Please enter a test path');
        return;
    }

    startBtn.disabled = true;
    terminal.innerHTML = '';
    addLine(`Starting fix for ${testPath}...`, 'action');

    try {
        const resp = await fetch('/api/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ test_path: testPath, workspace: workspace }),
        });
        const data = await resp.json();
        const sessionId = data.session_id;

        const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/fix/${sessionId}`);

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'action') {
                addLine(`[Action] ${msg.data.action} ${JSON.stringify(msg.data.params)}`, 'action');
            } else if (msg.type === 'feedback') {
                addLine(`[Feedback] passed=${msg.data.passed} exit_code=${msg.data.exit_code}`, 'feedback');
            } else if (msg.type === 'result') {
                addLine(`[Result] success=${msg.data.success} rounds=${msg.data.rounds} reason=${msg.data.reason}`, 'result');
            } else if (msg.type === 'error') {
                addLine(`[Error] ${msg.data.message}`, 'error');
            }
        };

        ws.onclose = () => {
            addLine('--- Session ended ---', 'result');
            startBtn.disabled = false;
            loadSessions();
        };

        ws.onerror = () => {
            addLine('WebSocket error', 'error');
            startBtn.disabled = false;
        };
    } catch (e) {
        addLine('Error: ' + e.message, 'error');
        startBtn.disabled = false;
    }
});

loadSessions();
