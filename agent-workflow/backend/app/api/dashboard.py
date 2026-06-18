from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Workflow Dashboard</title>
  <style>
    body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #18212f; background: #f5f7fb; }
    header { background: #fff; border-bottom: 1px solid #d9e0ea; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
    h1 { font-size: 21px; margin: 0; }
    main { display: grid; grid-template-columns: 380px 1fr; gap: 16px; padding: 16px 24px; }
    section { background: #fff; border: 1px solid #d9e0ea; border-radius: 8px; padding: 14px; }
    h2 { margin: 0 0 12px; font-size: 15px; }
    label { display: block; font-size: 12px; color: #526070; margin-top: 8px; }
    textarea, input, select { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; margin-top: 4px; }
    textarea { min-height: 92px; }
    button { border: 1px solid #243044; background: #243044; color: #fff; border-radius: 6px; padding: 8px 10px; cursor: pointer; margin: 4px 4px 4px 0; }
    button.secondary { background: #fff; color: #243044; }
    pre { background: #eef2f7; border-radius: 6px; padding: 10px; white-space: pre-wrap; overflow: auto; max-height: 460px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
    .workdoc-row { border: 1px solid #d9e0ea; border-radius: 6px; padding: 8px; margin-bottom: 8px; cursor: pointer; }
    .muted { color: #64748b; font-size: 12px; }
    @media (max-width: 900px) { main { grid-template-columns: 1fr; padding: 12px; } }
  </style>
</head>
<body>
  <header>
    <h1>Agent Workflow</h1>
    <span class="muted">Phase 9 intake and execution console</span>
  </header>
  <main>
    <section>
      <h2>Input</h2>
      <label>Mock chat message</label>
      <textarea id="message">首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。</textarea>
      <label>Repo path</label>
      <input id="repoPath" value=".">
      <label>Test command</label>
      <input id="testCommand" placeholder="optional, e.g. python -m pytest">
      <button onclick="importMessage()">Import Message</button>
      <button onclick="createWorkDoc()">Create WorkDoc</button>
      <button class="secondary" onclick="loadWorkDocs()">Refresh WorkDocs</button>
      <pre id="inputOutput"></pre>
      <h2>WeChat Intake</h2>
      <label>Room ID</label>
      <input id="wechatRoom" value="dev-group">
      <label>Manual export file path</label>
      <input id="exportPath" placeholder="F:\\path\\chat.txt">
      <label>Command Message ID</label>
      <input id="commandMessageId">
      <label>Context window</label>
      <input id="contextWindow" value="8">
      <button onclick="wechatHealth()">Health</button>
      <button onclick="pollRoom()">Poll Room</button>
      <button onclick="manualExportImport()">Import Export</button>
      <button onclick="processNewCommands()">Process Commands</button>
      <button class="secondary" onclick="loadMessages()">ChatMessages</button>
      <button class="secondary" onclick="loadCommandLogs()">Command Logs</button>
      <pre id="wechatOutput"></pre>
      <h2>Segments / Candidates</h2>
      <label>Segment ID</label>
      <input id="segmentId">
      <label>TaskCandidate ID</label>
      <input id="candidateId">
      <label>Candidate repo path</label>
      <input id="candidateRepoPath" value=".">
      <label>Acceptance criteria, one per line</label>
      <textarea id="candidateCriteria">Change satisfies the WorkBot request.</textarea>
      <button onclick="createSegmentFromCommand()">Segment From Command</button>
      <button onclick="createCandidate()">Create Candidate</button>
      <button onclick="updateCandidate()">Update Candidate</button>
      <button onclick="convertCandidate()">Convert To WorkDoc</button>
      <button onclick="sendCandidateFeedback()">Mock Feedback</button>
      <button class="secondary" onclick="loadSegments()">Segments</button>
      <button class="secondary" onclick="loadCandidates()">Candidates</button>
      <pre id="candidateOutput"></pre>
      <h2>WorkDocs</h2>
      <div id="workdocList"></div>
    </section>
    <section>
      <h2>Selected WorkDoc</h2>
      <div class="grid">
        <div>
          <label>WorkDoc ID</label>
          <input id="workdocId">
        </div>
        <div>
          <label>Agent runner</label>
          <select id="agentType">
            <option value="mock">mock</option>
            <option value="claude_cli">claude_cli</option>
            <option value="gagent_desktop">gagent_desktop</option>
          </select>
        </div>
        <div>
          <label>AgentRun ID</label>
          <input id="agentRunId">
        </div>
        <div>
          <label>GitOperation ID</label>
          <input id="gitOperationId">
        </div>
      </div>
      <button onclick="loadWorkDocDetail()">View Detail</button>
      <button onclick="validateWorkDoc()">Validate</button>
      <button onclick="approveWorkDoc()">Approve</button>
      <button onclick="runAgent()">Run Agent</button>
      <button onclick="viewAgentRun()">View Agent Logs</button>
      <button onclick="viewDiff()">View Git Diff</button>
      <button onclick="runTests()">Run Tests</button>
      <button onclick="commitDryRun()">Commit Dry-run</button>
      <button onclick="commitReal()">Commit Real</button>
      <button onclick="viewReport()">View Report</button>
      <button onclick="viewAgentReport()">View Agent Report</button>
      <pre id="detailOutput"></pre>
    </section>
  </main>
  <script>
    let lastMessageId = null;
    async function request(url, options) {
      const res = await fetch(url, options);
      const text = await res.text();
      try { return { ok: res.ok, status: res.status, data: JSON.parse(text) }; }
      catch { return { ok: res.ok, status: res.status, data: text }; }
    }
    function show(id, value) {
      document.getElementById(id).textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    }
    async function post(url, body) {
      return await request(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    }
    async function wechatHealth() {
      show('wechatOutput', (await request('/wechat/health')).data);
    }
    async function pollRoom() {
      const room = document.getElementById('wechatRoom').value;
      const result = await post('/wechat/poll-room', { room_id: room });
      if (result.ok && result.data.messages && result.data.messages[0]) {
        document.getElementById('commandMessageId').value = result.data.messages[result.data.messages.length - 1].id;
      }
      show('wechatOutput', result.data);
    }
    async function manualExportImport() {
      const result = await post('/wechat/manual-export/import', {
        room_id: document.getElementById('wechatRoom').value,
        file_path: document.getElementById('exportPath').value
      });
      if (result.ok && result.data[0]) document.getElementById('commandMessageId').value = result.data[result.data.length - 1].id;
      show('wechatOutput', result.data);
    }
    async function processNewCommands() {
      const result = await post('/bot/process-new-messages');
      if (result.ok && result.data[0]) document.getElementById('commandMessageId').value = result.data[result.data.length - 1].message_id;
      show('wechatOutput', result.data);
    }
    async function loadMessages() {
      show('wechatOutput', (await request('/messages')).data);
    }
    async function loadCommandLogs() {
      show('wechatOutput', (await request('/bot/commands')).data);
    }
    async function createSegmentFromCommand() {
      const messageId = document.getElementById('commandMessageId').value;
      const contextWindow = Number(document.getElementById('contextWindow').value || '8');
      const result = await post(`/segments/from-command/${messageId}`, { context_window_size: contextWindow });
      if (result.ok) document.getElementById('segmentId').value = result.data.id;
      show('candidateOutput', result.data);
    }
    async function createCandidate() {
      const segmentId = document.getElementById('segmentId').value;
      const result = await post(`/task-candidates/from-segment/${segmentId}`);
      if (result.ok) document.getElementById('candidateId').value = result.data.id;
      show('candidateOutput', result.data);
    }
    async function updateCandidate() {
      const candidateId = document.getElementById('candidateId').value;
      const criteria = document.getElementById('candidateCriteria').value.split('\\n').map(x => x.trim()).filter(Boolean);
      show('candidateOutput', (await post(`/task-candidates/${candidateId}/update`, {
        repo_path: document.getElementById('candidateRepoPath').value,
        acceptance_criteria: criteria
      })).data);
    }
    async function convertCandidate() {
      const candidateId = document.getElementById('candidateId').value;
      const result = await post(`/task-candidates/${candidateId}/convert-to-workdoc`);
      if (result.ok) document.getElementById('workdocId').value = result.data.id;
      show('candidateOutput', result.data);
      await loadWorkDocs();
    }
    async function sendCandidateFeedback() {
      const candidateId = document.getElementById('candidateId').value;
      show('candidateOutput', (await post(`/chat-feedback/task-candidate/${candidateId}`, {
        room_id: document.getElementById('wechatRoom').value,
        adapter_type: 'mock'
      })).data);
    }
    async function loadSegments() {
      show('candidateOutput', (await request('/segments')).data);
    }
    async function loadCandidates() {
      show('candidateOutput', (await request('/task-candidates')).data);
    }
    async function importMessage() {
      const result = await post('/messages/import', { messages: [{ room_id: 'mock-room', text: document.getElementById('message').value }] });
      if (result.ok && result.data[0]) lastMessageId = result.data[0].id;
      show('inputOutput', result.data);
    }
    async function createWorkDoc() {
      if (!lastMessageId) await importMessage();
      const command = document.getElementById('testCommand').value.trim();
      const body = {
        message_ids: [lastMessageId],
        repo_path: document.getElementById('repoPath').value,
        test: { commands: command ? [command] : [], required: Boolean(command) }
      };
      const result = await post('/workdocs/from-messages', body);
      if (result.ok) document.getElementById('workdocId').value = result.data.id;
      show('inputOutput', result.data);
      await loadWorkDocs();
    }
    async function loadWorkDocs() {
      const result = await request('/workdocs');
      const list = document.getElementById('workdocList');
      list.innerHTML = '';
      if (!Array.isArray(result.data)) return;
      for (const item of result.data) {
        const row = document.createElement('div');
        row.className = 'workdoc-row';
        row.textContent = `#${item.id} ${item.status} ${item.title}`;
        row.onclick = () => { document.getElementById('workdocId').value = item.id; loadWorkDocDetail(); };
        list.appendChild(row);
      }
    }
    async function loadWorkDocDetail() {
      const id = document.getElementById('workdocId').value;
      show('detailOutput', (await request(`/workdocs/${id}`)).data);
    }
    async function validateWorkDoc() {
      const id = document.getElementById('workdocId').value;
      show('detailOutput', (await post(`/workdocs/${id}/validate`)).data);
      await loadWorkDocs();
    }
    async function approveWorkDoc() {
      const id = document.getElementById('workdocId').value;
      show('detailOutput', (await post(`/workdocs/${id}/approve`)).data);
      await loadWorkDocs();
    }
    async function runAgent() {
      const id = document.getElementById('workdocId').value;
      const result = await post(`/agent-runs/from-workdoc/${id}`, { agent_type: document.getElementById('agentType').value });
      if (result.ok) document.getElementById('agentRunId').value = result.data.id;
      show('detailOutput', result.data);
    }
    async function viewAgentRun() {
      const id = document.getElementById('agentRunId').value;
      show('detailOutput', (await request(`/agent-runs/${id}`)).data);
    }
    async function viewDiff() {
      const id = document.getElementById('agentRunId').value;
      show('detailOutput', (await post(`/git/diff/${id}`)).data);
    }
    async function runTests() {
      const id = document.getElementById('agentRunId').value;
      show('detailOutput', (await post(`/tests/run-for-agent-run/${id}`)).data);
    }
    async function commitDryRun() {
      const id = document.getElementById('agentRunId').value;
      const result = await post(`/git/commit-from-run/${id}`, { dry_run: true });
      if (result.ok) document.getElementById('gitOperationId').value = result.data.id;
      show('detailOutput', result.data);
    }
    async function commitReal() {
      const id = document.getElementById('agentRunId').value;
      const result = await post(`/git/commit-from-run/${id}`, { dry_run: false });
      if (result.ok) document.getElementById('gitOperationId').value = result.data.id;
      show('detailOutput', result.data);
      await loadWorkDocs();
    }
    async function viewReport() {
      const id = document.getElementById('workdocId').value;
      show('detailOutput', (await request(`/reports/workdoc/${id}/markdown`)).data);
    }
    async function viewAgentReport() {
      const id = document.getElementById('agentRunId').value;
      show('detailOutput', (await request(`/reports/agent-run/${id}`)).data);
    }
    loadWorkDocs();
  </script>
</body>
</html>
"""
