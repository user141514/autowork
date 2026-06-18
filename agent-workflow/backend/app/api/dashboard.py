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
    :root {
      --bg: #f4f6f8;
      --panel: #ffffff;
      --line: #d7dee7;
      --line-strong: #aab6c4;
      --text: #17202c;
      --muted: #5d6b7a;
      --accent: #0f766e;
      --accent-weak: #e6f4f1;
      --warn: #9a6700;
      --danger: #b42318;
      --code: #edf1f5;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, Segoe UI, sans-serif; }
    header { height: 56px; padding: 0 20px; display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid var(--line); }
    h1 { margin: 0; font-size: 18px; font-weight: 700; }
    h2 { margin: 0 0 10px; font-size: 14px; font-weight: 700; }
    h3 { margin: 14px 0 8px; font-size: 13px; font-weight: 700; color: var(--muted); }
    main { display: grid; grid-template-columns: minmax(300px, 360px) minmax(380px, 1fr) minmax(340px, 460px); gap: 1px; min-height: calc(100vh - 56px); background: var(--line); }
    section { min-width: 0; background: var(--panel); padding: 14px; overflow: auto; }
    label { display: block; margin: 8px 0 4px; color: var(--muted); font-size: 12px; }
    input, select, textarea { width: 100%; border: 1px solid var(--line-strong); border-radius: 6px; padding: 8px; color: var(--text); background: #fff; font: inherit; font-size: 13px; }
    textarea { min-height: 84px; resize: vertical; }
    button { min-height: 34px; border: 1px solid #1f2937; border-radius: 6px; background: #1f2937; color: #fff; padding: 7px 10px; font: inherit; font-size: 13px; cursor: pointer; }
    button.secondary { background: #fff; color: #1f2937; }
    button.accent { border-color: var(--accent); background: var(--accent); }
    button.warn { border-color: var(--warn); background: var(--warn); }
    button.danger { border-color: var(--danger); background: var(--danger); }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .row > * { flex: 1 1 120px; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }
    .toolbar button { flex: 0 0 auto; }
    .status { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border-radius: 999px; background: var(--accent-weak); color: var(--accent); font-size: 12px; font-weight: 700; }
    .muted { color: var(--muted); font-size: 12px; }
    .list { display: grid; gap: 8px; }
    .item { border: 1px solid var(--line); border-radius: 6px; padding: 9px; background: #fff; cursor: pointer; }
    .item:hover { border-color: var(--accent); background: #fbfefd; }
    .item-title { font-size: 13px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .item-meta { margin-top: 4px; color: var(--muted); font-size: 12px; }
    pre { margin: 0; border: 1px solid var(--line); border-radius: 6px; background: var(--code); padding: 10px; white-space: pre-wrap; overflow: auto; max-height: 360px; font-size: 12px; line-height: 1.45; }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .divider { height: 1px; background: var(--line); margin: 14px 0; }
    .mini { max-width: 110px; }
    @media (max-width: 1180px) { main { grid-template-columns: 340px 1fr; } section.audit { grid-column: 1 / -1; } }
    @media (max-width: 760px) { main { grid-template-columns: 1fr; } header { align-items: flex-start; height: auto; gap: 6px; padding: 12px; flex-direction: column; } .split { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Agent Workflow</h1>
    <div class="row" style="justify-content:flex-end;">
      <span id="healthBadge" class="status">ready</span>
      <span class="muted">/dashboard</span>
    </div>
  </header>
  <main>
    <section>
      <h2>Intake</h2>
      <label>Mock message</label>
      <textarea id="message">首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。</textarea>
      <div class="row">
        <div><label>Repo path</label><input id="repoPath" value="."></div>
        <div><label>Test command</label><input id="testCommand" placeholder="python -m pytest"></div>
      </div>
      <div class="toolbar">
        <button class="accent" onclick="importMessage()">Import</button>
        <button onclick="createWorkDoc()">Create WorkDoc</button>
      </div>

      <div class="divider"></div>
      <h2>WeChat</h2>
      <div class="row">
        <div><label>Room</label><input id="wechatRoom" value="dev-group"></div>
        <div><label>Context</label><input id="contextWindow" value="8"></div>
      </div>
      <label>Manual export path</label>
      <input id="exportPath" placeholder="F:\\path\\chat.txt">
      <label>Command message ID</label>
      <input id="commandMessageId">
      <div class="toolbar">
        <button onclick="wechatHealth()">Health</button>
        <button onclick="pollRoom()">Poll</button>
        <button onclick="manualExportImport()">Import file</button>
        <button onclick="processNewCommands()">Commands</button>
      </div>
      <div class="toolbar">
        <button class="secondary" onclick="loadMessages()">Messages</button>
        <button class="secondary" onclick="loadCommandLogs()">Command logs</button>
      </div>

      <div class="divider"></div>
      <h2>Queue</h2>
      <div class="split">
        <div><label>Status</label><input id="filterStatus" placeholder="WORKDOC_DRAFTED"></div>
        <div><label>Risk</label><select id="filterRisk"><option value="">any</option><option value="low">low</option><option value="medium">medium</option><option value="high">high</option></select></div>
      </div>
      <div class="split">
        <div><label>Repo</label><input id="filterRepo" placeholder="repo_name"></div>
        <div><label>Limit</label><input id="filterLimit" value="50"></div>
      </div>
      <div class="toolbar">
        <button class="secondary" onclick="loadWorkDocs()">Refresh</button>
        <button class="secondary" onclick="clearFilters()">Clear</button>
      </div>
      <div id="workdocList" class="list"></div>
    </section>

    <section>
      <h2>WorkDoc</h2>
      <div class="split">
        <div><label>ID</label><input id="workdocId"></div>
        <div><label>Runner</label><select id="agentType"><option value="mock">mock</option><option value="claude_cli">claude_cli</option><option value="gagent_desktop">gagent_desktop</option></select></div>
      </div>
      <label>Title</label>
      <input id="editTitle">
      <label>Problem summary</label>
      <textarea id="editProblem"></textarea>
      <label>Acceptance criteria, one per line</label>
      <textarea id="editCriteria"></textarea>
      <div class="split">
        <div><label>Risk</label><select id="editRisk"><option value="low">low</option><option value="medium">medium</option><option value="high">high</option></select></div>
        <div><label>Test required</label><select id="editTestRequired"><option value="false">false</option><option value="true">true</option></select></div>
      </div>
      <label>Test commands, one per line</label>
      <textarea id="editTestCommands"></textarea>
      <div class="toolbar">
        <button onclick="loadWorkDocDetail()">Load</button>
        <button class="accent" onclick="patchWorkDoc()">Save draft</button>
        <button onclick="validateWorkDoc()">Validate</button>
        <button onclick="approveWorkDoc()">Approve</button>
      </div>
      <div class="toolbar">
        <button onclick="createSegmentFromCommand()">Segment</button>
        <button onclick="createCandidate()">Candidate</button>
        <button onclick="updateCandidate()">Update candidate</button>
        <button onclick="convertCandidate()">Convert</button>
      </div>
      <div class="split">
        <div><label>Segment ID</label><input id="segmentId"></div>
        <div><label>Candidate ID</label><input id="candidateId"></div>
      </div>
      <label>Candidate repo path</label>
      <input id="candidateRepoPath" value=".">
      <label>Candidate criteria</label>
      <textarea id="candidateCriteria">Change satisfies the WorkBot request.</textarea>
      <pre id="detailOutput"></pre>
    </section>

    <section class="audit">
      <h2>Run</h2>
      <div class="split">
        <div><label>AgentRun ID</label><input id="agentRunId"></div>
        <div><label>GitOperation ID</label><input id="gitOperationId"></div>
      </div>
      <div class="toolbar">
        <button class="accent" onclick="runAgent()">Run agent</button>
        <button onclick="viewAgentRun()">Logs</button>
        <button onclick="viewDiff()">Diff</button>
        <button onclick="runTests()">Tests</button>
      </div>
      <div class="toolbar">
        <button onclick="commitDryRun()">Commit dry-run</button>
        <button class="warn" onclick="commitReal()">Commit local</button>
      </div>

      <div class="divider"></div>
      <h2>Audit</h2>
      <div class="toolbar">
        <button class="secondary" onclick="loadPolicyDecisions()">Policies</button>
        <button class="secondary" onclick="loadAgentRuns()">Runs</button>
        <button class="secondary" onclick="loadGitOperations()">Git ops</button>
        <button class="secondary" onclick="loadSegments()">Segments</button>
        <button class="secondary" onclick="loadCandidates()">Candidates</button>
      </div>
      <div class="toolbar">
        <button onclick="viewReport()">WorkDoc report</button>
        <button onclick="viewAgentReport()">Agent report</button>
        <button onclick="sendCandidateFeedback()">Feedback</button>
      </div>
      <pre id="auditOutput"></pre>
    </section>
  </main>
  <script>
    let lastMessageId = null;
    let selectedWorkDoc = null;
    async function request(url, options) {
      const res = await fetch(url, options);
      const text = await res.text();
      let data;
      try { data = JSON.parse(text); } catch { data = text; }
      return { ok: res.ok, status: res.status, data };
    }
    async function post(url, body) {
      return request(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    }
    async function patch(url, body) {
      return request(url, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    }
    function show(id, value) {
      document.getElementById(id).textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    }
    function badge(text) { document.getElementById('healthBadge').textContent = text; }
    function lines(id) { return document.getElementById(id).value.split('\\n').map(x => x.trim()).filter(Boolean); }
    function workdocId() { return document.getElementById('workdocId').value.trim(); }
    function setWorkDocForm(item) {
      selectedWorkDoc = item;
      document.getElementById('workdocId').value = item.id || '';
      document.getElementById('editTitle').value = item.title || '';
      document.getElementById('editProblem').value = item.problem_summary || '';
      document.getElementById('editCriteria').value = (item.acceptance_criteria || []).join('\\n');
      document.getElementById('editRisk').value = item.risk_level || 'low';
      document.getElementById('editTestRequired').value = String(Boolean((item.test || {}).required));
      document.getElementById('editTestCommands').value = ((item.test || {}).commands || []).join('\\n');
    }
    function workdocQuery() {
      const params = new URLSearchParams();
      const status = document.getElementById('filterStatus').value.trim();
      const risk = document.getElementById('filterRisk').value.trim();
      const repo = document.getElementById('filterRepo').value.trim();
      const limit = document.getElementById('filterLimit').value.trim();
      if (status) params.set('status', status);
      if (risk) params.set('risk_level', risk);
      if (repo) params.set('repo_name', repo);
      if (limit) params.set('limit', limit);
      return params.toString();
    }
    async function importMessage() {
      const result = await post('/messages/import', { messages: [{ room_id: 'mock-room', text: document.getElementById('message').value }] });
      if (result.ok && result.data[0]) lastMessageId = result.data[0].id;
      show('detailOutput', result.data);
      badge(result.ok ? 'imported' : 'error');
    }
    async function createWorkDoc() {
      if (!lastMessageId) await importMessage();
      const command = document.getElementById('testCommand').value.trim();
      const result = await post('/workdocs/from-messages', {
        message_ids: [lastMessageId],
        repo_path: document.getElementById('repoPath').value,
        test: { commands: command ? [command] : [], required: Boolean(command) }
      });
      if (result.ok) setWorkDocForm(result.data);
      show('detailOutput', result.data);
      await loadWorkDocs();
    }
    async function loadWorkDocs() {
      const query = workdocQuery();
      const result = await request(`/workdocs${query ? '?' + query : ''}`);
      const list = document.getElementById('workdocList');
      list.innerHTML = '';
      if (!Array.isArray(result.data)) { show('detailOutput', result.data); return; }
      for (const item of result.data) {
        const row = document.createElement('div');
        row.className = 'item';
        row.innerHTML = `<div class="item-title">#${item.id} ${item.title}</div><div class="item-meta">${item.status} · ${item.risk_level} · ${item.repo_name}</div>`;
        row.onclick = () => { setWorkDocForm(item); loadWorkDocDetail(); };
        list.appendChild(row);
      }
      badge(`${result.data.length} workdocs`);
    }
    function clearFilters() {
      document.getElementById('filterStatus').value = '';
      document.getElementById('filterRisk').value = '';
      document.getElementById('filterRepo').value = '';
      document.getElementById('filterLimit').value = '50';
      loadWorkDocs();
    }
    async function loadWorkDocDetail() {
      const result = await request(`/workdocs/${workdocId()}`);
      if (result.ok) setWorkDocForm(result.data);
      show('detailOutput', result.data);
    }
    async function patchWorkDoc() {
      const result = await patch(`/workdocs/${workdocId()}`, {
        title: document.getElementById('editTitle').value,
        problem_summary: document.getElementById('editProblem').value,
        acceptance_criteria: lines('editCriteria'),
        review: { risk_level: document.getElementById('editRisk').value },
        test: { commands: lines('editTestCommands'), required: document.getElementById('editTestRequired').value === 'true' }
      });
      if (result.ok) setWorkDocForm(result.data);
      show('detailOutput', result.data);
      await loadWorkDocs();
    }
    async function validateWorkDoc() {
      const result = await post(`/workdocs/${workdocId()}/validate`);
      show('detailOutput', result.data);
      await loadWorkDocs();
    }
    async function approveWorkDoc() {
      const result = await post(`/workdocs/${workdocId()}/approve`);
      if (result.ok) setWorkDocForm(result.data);
      show('detailOutput', result.data);
      await loadWorkDocs();
    }
    async function wechatHealth() { show('auditOutput', (await request('/wechat/health')).data); }
    async function pollRoom() {
      const result = await post('/wechat/poll-room', { room_id: document.getElementById('wechatRoom').value });
      if (result.ok && result.data.messages && result.data.messages[0]) document.getElementById('commandMessageId').value = result.data.messages.at(-1).id;
      show('auditOutput', result.data);
    }
    async function manualExportImport() {
      const result = await post('/wechat/manual-export/import', { room_id: document.getElementById('wechatRoom').value, file_path: document.getElementById('exportPath').value });
      if (result.ok && result.data[0]) document.getElementById('commandMessageId').value = result.data.at(-1).id;
      show('auditOutput', result.data);
    }
    async function processNewCommands() {
      const result = await post('/bot/process-new-messages');
      if (result.ok && result.data[0]) document.getElementById('commandMessageId').value = result.data.at(-1).message_id;
      show('auditOutput', result.data);
    }
    async function loadMessages() { show('auditOutput', (await request('/messages')).data); }
    async function loadCommandLogs() { show('auditOutput', (await request('/bot/commands')).data); }
    async function createSegmentFromCommand() {
      const result = await post(`/segments/from-command/${document.getElementById('commandMessageId').value}`, { context_window_size: Number(document.getElementById('contextWindow').value || '8') });
      if (result.ok) document.getElementById('segmentId').value = result.data.id;
      show('detailOutput', result.data);
    }
    async function createCandidate() {
      const result = await post(`/task-candidates/from-segment/${document.getElementById('segmentId').value}`);
      if (result.ok) document.getElementById('candidateId').value = result.data.id;
      show('detailOutput', result.data);
    }
    async function updateCandidate() {
      const result = await post(`/task-candidates/${document.getElementById('candidateId').value}/update`, {
        repo_path: document.getElementById('candidateRepoPath').value,
        acceptance_criteria: lines('candidateCriteria')
      });
      show('detailOutput', result.data);
    }
    async function convertCandidate() {
      const result = await post(`/task-candidates/${document.getElementById('candidateId').value}/convert-to-workdoc`);
      if (result.ok) setWorkDocForm(result.data);
      show('detailOutput', result.data);
      await loadWorkDocs();
    }
    async function runAgent() {
      const result = await post(`/agent-runs/from-workdoc/${workdocId()}`, { agent_type: document.getElementById('agentType').value });
      if (result.ok) document.getElementById('agentRunId').value = result.data.id;
      show('auditOutput', result.data);
    }
    async function viewAgentRun() { show('auditOutput', (await request(`/agent-runs/${document.getElementById('agentRunId').value}`)).data); }
    async function viewDiff() { show('auditOutput', (await post(`/git/diff/${document.getElementById('agentRunId').value}`)).data); }
    async function runTests() { show('auditOutput', (await post(`/tests/run-for-agent-run/${document.getElementById('agentRunId').value}`)).data); }
    async function commitDryRun() {
      const result = await post(`/git/commit-from-run/${document.getElementById('agentRunId').value}`, { dry_run: true });
      if (result.ok) document.getElementById('gitOperationId').value = result.data.id;
      show('auditOutput', result.data);
    }
    async function commitReal() {
      const result = await post(`/git/commit-from-run/${document.getElementById('agentRunId').value}`, { dry_run: false });
      if (result.ok) document.getElementById('gitOperationId').value = result.data.id;
      show('auditOutput', result.data);
      await loadWorkDocs();
    }
    async function loadPolicyDecisions() { show('auditOutput', (await request(`/policy-decisions?workdoc_id=${workdocId()}`)).data); }
    async function loadAgentRuns() { show('auditOutput', (await request(`/agent-runs?workdoc_id=${workdocId()}`)).data); }
    async function loadGitOperations() { show('auditOutput', (await request(`/git/operations?workdoc_id=${workdocId()}`)).data); }
    async function loadSegments() { show('auditOutput', (await request('/segments')).data); }
    async function loadCandidates() { show('auditOutput', (await request('/task-candidates')).data); }
    async function viewReport() { show('auditOutput', (await request(`/reports/workdoc/${workdocId()}/markdown`)).data); }
    async function viewAgentReport() { show('auditOutput', (await request(`/reports/agent-run/${document.getElementById('agentRunId').value}`)).data); }
    async function sendCandidateFeedback() {
      show('auditOutput', (await post(`/chat-feedback/task-candidate/${document.getElementById('candidateId').value}`, {
        room_id: document.getElementById('wechatRoom').value,
        adapter_type: 'mock'
      })).data);
    }
    loadWorkDocs();
  </script>
</body>
</html>
"""
