from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.schemas.demand_radar import DemandRadarExtractRequest, DemandRadarExtractResponse
from app.services.demand_radar import DemandRadar
from app.services.llm_client import LLMConfigurationError, LLMRequestError
from app.services.llm_demand_radar import LLMDemandRadar


router = APIRouter(prefix="/demand-radar", tags=["demand-radar"])


@router.post("/extract", response_model=DemandRadarExtractResponse, response_model_by_alias=True)
def extract_demand_candidates(request: DemandRadarExtractRequest):
    return DemandRadarExtractResponse(candidates=DemandRadar().extract(request.messages))


@router.post("/extract-llm", response_model=DemandRadarExtractResponse, response_model_by_alias=True)
def extract_demand_candidates_with_llm(request: DemandRadarExtractRequest):
    try:
        candidates = LLMDemandRadar().extract(request.messages)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (LLMRequestError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return DemandRadarExtractResponse(candidates=candidates)


@router.get("/demo", response_class=HTMLResponse)
def demand_radar_demo() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>需求雷达 Demo</title>
  <style>
    :root {
      --bg: #f5f7fa;
      --panel: #ffffff;
      --line: #d9e0e8;
      --text: #17202a;
      --muted: #667085;
      --accent: #0f766e;
      --accent-soft: #e7f5f2;
      --warn: #a15c07;
      --danger: #b42318;
      --code: #eef2f6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      height: 60px;
      padding: 0 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #fff;
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0; font-size: 20px; }
    h2 { margin: 0 0 12px; font-size: 15px; }
    main {
      display: grid;
      grid-template-columns: minmax(360px, 460px) minmax(480px, 1fr);
      gap: 1px;
      min-height: calc(100vh - 60px);
      background: var(--line);
    }
    section {
      min-width: 0;
      padding: 18px;
      background: var(--panel);
      overflow: auto;
    }
    textarea {
      width: 100%;
      min-height: 410px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      resize: vertical;
      color: var(--text);
      background: #fbfcfd;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    button {
      min-height: 36px;
      padding: 8px 12px;
      border: 1px solid #1f2937;
      border-radius: 7px;
      background: #1f2937;
      color: #fff;
      font: inherit;
      font-size: 13px;
      cursor: pointer;
    }
    button.secondary { background: #fff; color: #1f2937; }
    button.accent { border-color: var(--accent); background: var(--accent); }
    button.ghost { border-color: var(--line); background: #fff; color: var(--muted); }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
    .hint { margin: 0 0 12px; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .statbar { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 12px; }
    .stat {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfd;
    }
    .stat strong { display: block; font-size: 18px; }
    .stat span { color: var(--muted); font-size: 12px; }
    .cards { display: grid; gap: 10px; }
    .card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 13px;
    }
    .card.pending_review { border-left: 5px solid var(--accent); }
    .card.suspect { border-left: 5px solid var(--warn); }
    .card.expired { border-left: 5px solid var(--muted); opacity: .88; }
    .title { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
    .title strong { font-size: 15px; }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .badge.suspect { background: #fff4e5; color: var(--warn); }
    .badge.expired { background: #eef2f6; color: var(--muted); }
    .meta { margin-top: 6px; color: var(--muted); font-size: 12px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
    .review-form {
      display: none;
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfd;
    }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    label { display: block; margin: 8px 0 4px; color: var(--muted); font-size: 12px; }
    input, select {
      width: 100%;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 7px 9px;
      color: var(--text);
      background: #fff;
      font: inherit;
      font-size: 13px;
    }
    .box { border: 1px solid var(--line); border-radius: 7px; padding: 9px; background: #fbfcfd; }
    .box h3 { margin: 0 0 7px; font-size: 12px; color: var(--muted); }
    .preview {
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
    }
    .preview.empty { display: none; }
    .preview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .kv {
      display: grid;
      grid-template-columns: 130px 1fr;
      gap: 6px;
      margin: 5px 0;
      font-size: 13px;
    }
    .kv span:first-child { color: var(--muted); }
    .preview pre { max-height: 320px; }
    ul { margin: 0; padding-left: 18px; }
    li { margin: 4px 0; font-size: 13px; line-height: 1.45; }
    pre {
      margin: 0;
      padding: 10px;
      border-radius: 7px;
      background: var(--code);
      white-space: pre-wrap;
      max-height: 230px;
      overflow: auto;
      font-size: 12px;
    }
    @media (max-width: 920px) {
      main { grid-template-columns: 1fr; }
      .statbar, .grid { grid-template-columns: 1fr; }
      header { height: auto; padding: 14px; align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <h1>需求雷达</h1>
    <span class="hint">从混杂群聊里提取可审阅的候选需求卡片，不创建 WorkDoc，不运行 Agent。</span>
  </header>
  <main>
    <section>
      <h2>输入消息</h2>
      <p class="hint">可以先点样例，再点“运行提取”。输入格式是 DemandMessage 数组。</p>
      <div class="toolbar">
        <button class="secondary" onclick="loadSample('hundred')">100 条混合样例</button>
        <button class="secondary" onclick="loadSample('bug')">Bug 片段</button>
        <button class="secondary" onclick="loadSample('feature')">功能需求片段</button>
      </div>
      <textarea id="input"></textarea>
      <div class="toolbar">
        <button class="secondary" onclick="analyzeContext()">判断上下文</button>
        <button class="accent" onclick="runExtract()">运行提取</button>
        <button class="secondary" onclick="formatInput()">格式化 JSON</button>
      </div>
      <pre id="raw"></pre>
      <div id="contextPreview" class="preview empty">
        <h2>上下文置信度预览</h2>
        <div id="contextSummary" class="box"></div>
        <h2>直接回答草稿</h2>
        <pre id="directAnswerPreview"></pre>
      </div>
    </section>
    <section>
      <h2>候选需求卡片</h2>
      <div class="statbar">
        <div class="stat"><strong id="messageCount">0</strong><span>输入消息</span></div>
        <div class="stat"><strong id="candidateCount">0</strong><span>候选需求</span></div>
        <div class="stat"><strong id="pendingCount">0</strong><span>待确认</span></div>
        <div class="stat"><strong id="expiredCount">0</strong><span>已取消/过期</span></div>
      </div>
      <div id="cards" class="cards"></div>
      <div id="reviewForm" class="review-form">
        <h2>确认并补全</h2>
        <p class="hint" id="selectedCandidateHint">请选择一张候选卡片。</p>
        <div class="form-grid">
          <div><label>projectOrRepo</label><input id="projectOrRepo" value="agent-workflow"></div>
          <div><label>workingDir</label><input id="workingDir" value="F:/autowork/agent-workflow/backend"></div>
          <div><label>branch</label><input id="branch" value="main"></div>
          <div><label>module</label><input id="module"></div>
          <div><label>page</label><input id="page"></div>
          <div><label>targetObject</label><input id="targetObject"></div>
        </div>
        <label>actualBehavior</label><textarea id="actualBehavior"></textarea>
        <label>expectedBehavior</label><textarea id="expectedBehavior"></textarea>
        <label>desiredBehavior</label><textarea id="desiredBehavior"></textarea>
        <label>scope</label><input id="scope" value="只处理本候选需求涉及的范围">
        <label>constraints，每行一条</label><textarea id="constraints">不要修改无关模块</textarea>
        <label>acceptanceCriteria，每行一条</label><textarea id="acceptanceCriteria"></textarea>
        <label>outOfScope，每行一条</label><textarea id="outOfScope">不部署，不 push，不自动提交</textarea>
        <label>humanNotes</label><textarea id="humanNotes"></textarea>
        <div class="toolbar">
          <label><input id="allowAgent" type="checkbox" checked style="width:auto; min-height:auto;"> allowAgent</label>
          <label><input id="writeInbox" type="checkbox" style="width:auto; min-height:auto;"> 写入 agent_inbox</label>
        </div>
        <div class="toolbar">
          <button class="accent" onclick="promoteSelected()">生成 WorkDoc 草稿和 Agent 输入包</button>
        </div>
      </div>
      <div id="promotionPreview" class="preview empty">
        <h2>WorkDoc 草稿预览</h2>
        <div id="workdocSummary" class="box"></div>
        <div class="preview-grid">
          <div>
            <h2>WorkDoc JSON</h2>
            <pre id="workdocPreview"></pre>
          </div>
          <div>
            <h2>Agent 输入包预览</h2>
            <div id="agentPackSummary" class="box"></div>
            <pre id="agentPackPreview"></pre>
          </div>
        </div>
        <h2>Agent Brief Markdown</h2>
        <pre id="agentBriefPreview"></pre>
      </div>
    </section>
  </main>
  <script>
    const baseTime = new Date('2026-06-19T09:00:00+08:00');
    let currentCandidates = [];
    let selectedCandidate = null;
    function msg(id, minute, text, sender = '成员', type = 'text') {
      const t = new Date(baseTime.getTime() + minute * 60000);
      return {
        id: `m-${id}`,
        chatId: 'project-room-a',
        chatName: '项目A工作群',
        sender,
        timestamp: t.toISOString(),
        text,
        msgType: type,
        source: 'demo'
      };
    }
    function hundredMessages() {
      const demand = {
        10: '设置页保存接口 500，页面一直转圈，发版前要修',
        11: '期望保存成功后提示已保存',
        35: '工作台需要加一个导入聊天记录按钮',
        36: '先只支持本地 txt，验收是能看到解析结果',
        60: '权限页新增用户失败，提示 403，今天发版前要修',
        61: '这个影响演示，优先处理',
        85: '报表导出文件名不对，应该带日期',
        86: '不用改了，是测试数据问题'
      };
      const filler = ['收到', '好的', '我看看', '午饭订了吗', '这个后面再聊'];
      return Array.from({ length: 100 }, (_, i) => msg(i + 1, i, demand[i] || filler[i % filler.length], `成员${i % 6}`));
    }
    const samples = {
      hundred: hundredMessages,
      bug: () => [
        msg(1, 1, '早'),
        msg(2, 2, '设置页点保存以后接口 500，页面一直转圈', '测试'),
        msg(3, 3, '日志里是 /api/settings/save 报错，发版前要修一下', '开发'),
        msg(4, 4, '期望是保存成功后提示已保存，并回到设置页', '产品'),
        msg(5, 5, '收到')
      ],
      feature: () => [
        msg(1, 1, '工作台这里能不能加一个导入按钮，直接导入聊天 txt', '产品'),
        msg(2, 2, '先只做本地文件，不要接真实微信', '产品'),
        msg(3, 3, '验收：上传后能看到解析出的消息列表', '产品')
      ]
    };
    function loadSample(name) {
      document.getElementById('input').value = JSON.stringify(samples[name](), null, 2);
      document.getElementById('raw').textContent = '';
      clearContextPreview();
      render([]);
    }
    function formatInput() {
      const data = JSON.parse(document.getElementById('input').value);
      document.getElementById('input').value = JSON.stringify(data, null, 2);
    }
    async function runExtract() {
      const messages = JSON.parse(document.getElementById('input').value);
      const response = await fetch('/demand-radar/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages })
      });
      const body = await response.json();
      document.getElementById('raw').textContent = JSON.stringify(body, null, 2);
      if (!response.ok) {
        render([]);
        return;
      }
      render(body.candidates || [], messages.length);
    }
    async function analyzeContext() {
      const messages = JSON.parse(document.getElementById('input').value);
      const response = await fetch('/context-confidence/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages })
      });
      let body;
      try {
        body = await response.json();
      } catch {
        body = { detail: await response.text() };
      }
      document.getElementById('raw').textContent = JSON.stringify(body, null, 2);
      if (response.ok) {
        renderContextPreview(body);
      }
    }
    function render(candidates, messageCount = 0) {
      currentCandidates = candidates;
      selectedCandidate = null;
      document.getElementById('reviewForm').style.display = 'none';
      clearPromotionPreview();
      clearContextPreview();
      const pending = candidates.filter(c => c.status === 'pending_review').length;
      const expired = candidates.filter(c => c.status === 'expired').length;
      document.getElementById('messageCount').textContent = messageCount;
      document.getElementById('candidateCount').textContent = candidates.length;
      document.getElementById('pendingCount').textContent = pending;
      document.getElementById('expiredCount').textContent = expired;
      const root = document.getElementById('cards');
      root.innerHTML = '';
      if (!candidates.length) {
        root.innerHTML = '<div class="card"><div class="meta">还没有候选。选择样例并运行提取。</div></div>';
        return;
      }
      for (const c of candidates) {
        const context = c.contextAssessment;
        const card = document.createElement('article');
        card.className = `card ${c.status}`;
        card.innerHTML = `
          <div class="title">
            <strong>${escapeHtml(c.title)}</strong>
            <span class="badge ${c.status}">${labelStatus(c.status)} · ${c.confidence}</span>
          </div>
          <div class="meta">${c.requirementType} · 分数 ${c.confidenceScore} · 证据 ${c.evidenceMessageIds.length} 条 · ${context ? contextLabel(context) : '未判断上下文'}</div>
          <p>${escapeHtml(c.hypothesis)}</p>
          <div class="toolbar">
            <button class="accent" onclick="selectCandidate('${c.id}')">确认并补全</button>
            <button class="ghost" onclick="recordDecision('${c.id}', 'reject')">忽略</button>
            <button class="ghost" onclick="recordDecision('${c.id}', 'merge')">合并</button>
            <button class="ghost" onclick="recordDecision('${c.id}', 'expire')">过期</button>
          </div>
          <div class="grid">
            <div class="box">
              <h3>证据消息</h3>
              <ul>${c.evidence.map(e => `<li>${escapeHtml(e.role)}：${escapeHtml(e.text)}</li>`).join('')}</ul>
            </div>
            <div class="box">
              <h3>缺失字段</h3>
              <ul>${(c.missingFields.length ? c.missingFields : ['无明显缺失']).map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>
            </div>
            <div class="box">
              <h3>事实</h3>
              <ul>${c.facts.map(f => `<li>${escapeHtml(f.text)}</li>`).join('')}</ul>
            </div>
            <div class="box">
              <h3>推断</h3>
              <ul>${c.inferences.map(i => `<li>${escapeHtml(i.text)}</li>`).join('')}</ul>
            </div>
            <div class="box">
              <h3>上下文判断</h3>
              ${context ? `
                <ul>
                  <li>${escapeHtml(contextLabel(context))}</li>
                  <li>建议动作：${escapeHtml(context.suggestedAction)}</li>
                  <li>原因：${escapeHtml((context.reasons || []).join('，') || '无')}</li>
                  <li>缺失：${escapeHtml((context.missingFields || []).join('，') || '无')}</li>
                </ul>
              ` : '<ul><li>未判断</li></ul>'}
            </div>
          </div>
        `;
        root.appendChild(card);
      }
    }
    function selectCandidate(candidateId) {
      selectedCandidate = currentCandidates.find(item => item.id === candidateId);
      if (!selectedCandidate) return;
      document.getElementById('reviewForm').style.display = 'block';
      document.getElementById('selectedCandidateHint').textContent = `正在补全：${selectedCandidate.title}`;
      document.getElementById('module').value = inferModule(selectedCandidate);
      document.getElementById('page').value = inferPage(selectedCandidate);
      document.getElementById('targetObject').value = selectedCandidate.title;
      document.getElementById('actualBehavior').value = selectedCandidate.requirementType === 'bug' ? selectedCandidate.hypothesis.replace(/^可能的 bug：/, '') : '';
      document.getElementById('expectedBehavior').value = selectedCandidate.requirementType === 'bug' ? (firstAcceptanceHint(selectedCandidate) || '修复后不再出现该问题') : '';
      document.getElementById('desiredBehavior').value = selectedCandidate.requirementType === 'feature' ? selectedCandidate.hypothesis.replace(/^可能的功能\\/改动需求：/, '') : '';
      document.getElementById('acceptanceCriteria').value = firstAcceptanceHint(selectedCandidate) || '人工确认后满足该需求';
      document.getElementById('humanNotes').value = `候选置信度：${selectedCandidate.confidence}，证据 ${selectedCandidate.evidenceMessageIds.length} 条`;
      document.getElementById('reviewForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function recordDecision(candidateId, decision) {
      const candidate = currentCandidates.find(item => item.id === candidateId);
      const payload = {
        candidateId,
        decision,
        reviewer: 'demo-user',
        reviewedAt: new Date().toISOString(),
        reason: decision === 'merge' ? '需要与其他候选合并后再处理' : '人工审阅决定',
        mergeTargetCandidateId: decision === 'merge' ? '待选择目标候选' : undefined
      };
      document.getElementById('raw').textContent = JSON.stringify({ candidate: candidate?.title, decision: payload }, null, 2);
    }
    async function promoteSelected() {
      if (!selectedCandidate) {
        document.getElementById('raw').textContent = '请先点击候选卡片上的“确认并补全”。';
        return;
      }
      const decision = {
        candidateId: selectedCandidate.id,
        decision: 'confirm',
        reviewer: 'demo-user',
        reviewedAt: new Date().toISOString(),
        humanFields: {
          projectOrRepo: document.getElementById('projectOrRepo').value,
          workingDir: document.getElementById('workingDir').value,
          branch: document.getElementById('branch').value,
          module: document.getElementById('module').value,
          page: document.getElementById('page').value,
          targetObject: document.getElementById('targetObject').value,
          actualBehavior: document.getElementById('actualBehavior').value,
          expectedBehavior: document.getElementById('expectedBehavior').value,
          desiredBehavior: document.getElementById('desiredBehavior').value,
          scope: document.getElementById('scope').value,
          constraints: lines('constraints'),
          acceptanceCriteria: lines('acceptanceCriteria'),
          outOfScope: lines('outOfScope'),
          humanNotes: document.getElementById('humanNotes').value,
          allowAgent: document.getElementById('allowAgent').checked
        }
      };
      const response = await fetch('/requirement-promotion/promote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate: selectedCandidate,
          decision,
          writeInbox: document.getElementById('writeInbox').checked
        })
      });
      let body;
      try {
        body = await response.json();
      } catch {
        body = { detail: await response.text() };
      }
      document.getElementById('raw').textContent = JSON.stringify(body, null, 2);
      if (response.ok) {
        renderPromotionPreview(body);
      } else {
        clearPromotionPreview();
      }
    }
    function renderPromotionPreview(result) {
      const workdoc = result.workdocDraft;
      const pack = result.agentInputPack;
      const preview = document.getElementById('promotionPreview');
      preview.classList.remove('empty');
      document.getElementById('workdocSummary').innerHTML = `
        <div class="kv"><span>workdocId</span><strong>${escapeHtml(workdoc.workdocId)}</strong></div>
        <div class="kv"><span>candidateId</span><span>${escapeHtml(workdoc.candidateId)}</span></div>
        <div class="kv"><span>标题</span><span>${escapeHtml(workdoc.title)}</span></div>
        <div class="kv"><span>类型</span><span>${escapeHtml(workdoc.type)}</span></div>
        <div class="kv"><span>项目</span><span>${escapeHtml(workdoc.projectOrRepo)}</span></div>
        <div class="kv"><span>状态</span><span>${escapeHtml(workdoc.status)}</span></div>
        <div class="kv"><span>验收标准</span><span>${escapeHtml((workdoc.acceptanceCriteria || []).join('；'))}</span></div>
      `;
      document.getElementById('agentPackSummary').innerHTML = `
        <div class="kv"><span>packId</span><strong>${escapeHtml(pack.packId)}</strong></div>
        <div class="kv"><span>目标目录</span><span>${escapeHtml(pack.target.workingDir || '未指定')}</span></div>
        <div class="kv"><span>允许改代码</span><span>${pack.executionPolicy.allowCodeEdit}</span></div>
        <div class="kv"><span>允许测试</span><span>${pack.executionPolicy.allowTestRun}</span></div>
        <div class="kv"><span>允许提交</span><span>${pack.executionPolicy.allowGitCommit}</span></div>
        <div class="kv"><span>允许 push</span><span>${pack.executionPolicy.allowPush}</span></div>
        <div class="kv"><span>inbox</span><span>${escapeHtml(result.inboxPath || '未写入，仅预览')}</span></div>
      `;
      document.getElementById('workdocPreview').textContent = JSON.stringify(workdoc, null, 2);
      document.getElementById('agentPackPreview').textContent = JSON.stringify(pack, null, 2);
      document.getElementById('agentBriefPreview').textContent = result.agentBriefMarkdown || '';
      preview.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function clearPromotionPreview() {
      document.getElementById('promotionPreview').classList.add('empty');
      document.getElementById('workdocSummary').innerHTML = '';
      document.getElementById('agentPackSummary').innerHTML = '';
      document.getElementById('workdocPreview').textContent = '';
      document.getElementById('agentPackPreview').textContent = '';
      document.getElementById('agentBriefPreview').textContent = '';
    }
    function renderContextPreview(result) {
      const assessment = result.assessment;
      document.getElementById('contextPreview').classList.remove('empty');
      document.getElementById('contextSummary').innerHTML = `
        <div class="kv"><span>判断</span><strong>${escapeHtml(contextLabel(assessment))}</strong></div>
        <div class="kv"><span>建议动作</span><span>${escapeHtml(assessment.suggestedAction)}</span></div>
        <div class="kv"><span>置信度</span><span>${escapeHtml(assessment.confidence)} / ${assessment.confidenceScore}</span></div>
        <div class="kv"><span>原因</span><span>${escapeHtml((assessment.reasons || []).join('，') || '无')}</span></div>
        <div class="kv"><span>缺失字段</span><span>${escapeHtml((assessment.missingFields || []).join('，') || '无')}</span></div>
        <div class="kv"><span>建议回看</span><span>${assessment.suggestedLookbackMessages || 0} 条</span></div>
      `;
      if (result.directAnswerDraft) {
        document.getElementById('directAnswerPreview').textContent = JSON.stringify(result.directAnswerDraft, null, 2);
      } else {
        document.getElementById('directAnswerPreview').textContent = '不是直接回答场景。';
      }
      document.getElementById('contextPreview').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function clearContextPreview() {
      document.getElementById('contextPreview').classList.add('empty');
      document.getElementById('contextSummary').innerHTML = '';
      document.getElementById('directAnswerPreview').textContent = '';
    }
    function contextLabel(assessment) {
      const resolution = {
        self_contained: '可直接回答',
        local_context_enough: '上下文足够',
        needs_more_history: '需要继续翻上文',
        needs_user_input: '需要用户补充'
      }[assessment.resolution] || assessment.resolution;
      return `${resolution} · ${assessment.confidence}`;
    }
    function lines(id) {
      return document.getElementById(id).value.split('\\n').map(item => item.trim()).filter(Boolean);
    }
    function firstAcceptanceHint(candidate) {
      const evidence = candidate.evidence.map(item => item.text).join(' ');
      const match = evidence.match(/(期望|验收|应该)[^。；;]*/);
      return match ? match[0] : '';
    }
    function inferModule(candidate) {
      const text = candidate.evidence.map(item => item.text).join(' ');
      if (text.includes('设置')) return 'settings';
      if (text.includes('权限')) return 'permission';
      if (text.includes('工作台')) return 'dashboard';
      if (text.includes('报表')) return 'report';
      return '';
    }
    function inferPage(candidate) {
      const text = candidate.evidence.map(item => item.text).join(' ');
      if (text.includes('设置')) return '设置页';
      if (text.includes('权限')) return '权限页';
      if (text.includes('工作台')) return '工作台';
      if (text.includes('报表')) return '报表页';
      return '';
    }
    function labelStatus(status) {
      if (status === 'pending_review') return '待确认';
      if (status === 'suspect') return '可疑';
      if (status === 'expired') return '已过期';
      return status;
    }
    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }
    loadSample('hundred');
  </script>
</body>
</html>
"""
