import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_message import ChatMessage
from app.schemas.demand_radar import DemandMessage
from app.services.demand_radar import DemandRadar
from app.services.llm_client import LLMConfigurationError, LLMRequestError
from app.services.llm_demand_radar import LLMDemandRadar
from app.services.message_store import MessageStore
from app.services.wechat_directory import MAX_MESSAGE_PAGE_LIMIT, WeChatDirectoryService


router = APIRouter(tags=["review-workbench"])
DEFAULT_DECRYPTED_WECHAT_DIR = Path(__file__).resolve().parents[4] / "external_tools" / "decrypted_wechat"
REVIEW_WORKBENCH_MESSAGE_LIMIT = 50


@router.get("/review-workbench/recent-50-stream")
def stream_recent_50_messages(room_id: str | None = None, extractor: str = "llm", db: Session = Depends(get_db)):
    return StreamingResponse(
        _recent_message_events(db=db, room_id=room_id, limit=REVIEW_WORKBENCH_MESSAGE_LIMIT, extractor=extractor),
        media_type="application/x-ndjson; charset=utf-8",
    )


@router.get("/review-workbench/recent-500-stream")
def stream_recent_500_messages(room_id: str | None = None, extractor: str = "llm", db: Session = Depends(get_db)):
    safe_limit = min(500, MAX_MESSAGE_PAGE_LIMIT)
    return StreamingResponse(
        _recent_message_events(db=db, room_id=room_id, limit=safe_limit, extractor=extractor),
        media_type="application/x-ndjson; charset=utf-8",
    )


def _recent_message_events(db: Session, room_id: str | None, limit: int, extractor: str = "llm") -> Iterable[str]:
    if not room_id:
        yield _event(
            "warning",
            message="没有消息：请先在左侧选择一个群聊或联系人，再获取最近消息。",
            limit=limit,
        )
        yield _event("done", message="未选择会话，已停止读取，避免全库大查询。")
        return

    yield _event("start", message=f"开始获取最近 {limit} 条消息", limit=limit, roomId=room_id)
    chat_messages = MessageStore(db).list_messages(room_id=room_id, limit=limit, order="desc")
    yield _event("fetched", message=f"已从业务库获取 {len(chat_messages)} 条消息", count=len(chat_messages), source="app_database")
    if not chat_messages:
        yield _event("warning", message="业务库里没有该会话消息，开始检查本机已解密微信库。")
        import_result = _import_latest_from_decrypted_wechat(db=db, room_id=room_id, limit=limit)
        for progress_event in import_result["events"]:
            yield progress_event
        resolved_room_id = import_result.get("room_id") or room_id
        if import_result.get("imported_count", 0) > 0 or resolved_room_id != room_id:
            chat_messages = MessageStore(db).list_messages(room_id=resolved_room_id, limit=limit, order="desc")
            yield _event(
                "fetched",
                message=f"已从业务库重新获取 {len(chat_messages)} 条消息",
                count=len(chat_messages),
                source="app_database_after_wechat_import",
            )
        if not chat_messages:
            yield _event("warning", message="仍然没有可提取消息。请确认已选择正确会话，或先运行解密/导入脚本。")

    demand_messages: list[DemandMessage] = []
    for index, message in enumerate(chat_messages, start=1):
        demand_message = _chat_message_to_demand_message(message)
        demand_messages.append(DemandMessage(**demand_message))
        yield _event(
            "message",
            message=f"转换第 {index}/{len(chat_messages)} 条消息",
            index=index,
            total=len(chat_messages),
            demandMessage=demand_message,
        )

    extractor_name = "llm" if extractor == "llm" else "local"
    yield _event("extracting", message=f"开始提取候选需求（{extractor_name}）", count=len(demand_messages), extractor=extractor_name)
    try:
        candidates = LLMDemandRadar().extract(demand_messages) if extractor_name == "llm" else DemandRadar().extract(demand_messages)
    except (LLMConfigurationError, LLMRequestError, ValueError) as exc:
        yield _event("error", message=f"LLM 提取失败：{exc}", extractor=extractor_name)
        yield _event("candidates", message="提取失败，得到 0 个候选需求", count=0, candidates=[])
        yield _event("done", message=f"最近 {limit} 条消息获取完成，但 LLM 提取失败")
        return
    yield _event(
        "candidates",
        message=f"提取完成，得到 {len(candidates)} 个候选需求",
        count=len(candidates),
        candidates=[candidate.model_dump(mode="json", by_alias=True) for candidate in candidates],
    )
    yield _event("done", message=f"最近 {limit} 条消息获取与提取完成")


def _event(event_type: str, **payload: Any) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


def _chat_message_to_demand_message(message: ChatMessage) -> dict[str, Any]:
    raw = message.raw_json or {}
    chat_name = raw.get("room_display_name") or raw.get("display_name") or message.room_id
    sender = raw.get("sender_display_name") or message.sender_display_name or message.sender_hash or None
    return {
        "id": f"chat-{message.id}",
        "chatId": message.room_id,
        "chatName": chat_name,
        "sender": sender,
        "timestamp": message.timestamp.isoformat(),
        "text": message.text,
        "msgType": _normalize_message_type(message.message_type),
        "source": message.platform or "stored-chat",
        "raw": {
            "id": message.id,
            "platform": message.platform,
            "room_id": message.room_id,
            "room_display_name": chat_name,
            "sender_hash": message.sender_hash,
            "sender_display_name": sender,
            "sender_wxid": raw.get("sender_wxid"),
            "message_type": message.message_type,
        },
    }


def _normalize_message_type(message_type: str | None) -> str:
    value = (message_type or "text").lower()
    return value if value in {"text", "image", "file", "link", "system", "unknown"} else "text"


def _import_latest_from_decrypted_wechat(db: Session, room_id: str, limit: int) -> dict[str, Any]:
    service = WeChatDirectoryService(DEFAULT_DECRYPTED_WECHAT_DIR)
    events: list[str] = []
    if not DEFAULT_DECRYPTED_WECHAT_DIR.exists():
        events.append(_event("warning", message=f"未找到已解密微信库：{DEFAULT_DECRYPTED_WECHAT_DIR}"))
        return {"room_id": None, "imported_count": 0, "events": events}

    candidates = service.list_conversations(kind="all", query=room_id, limit=20)
    exact = [candidate for candidate in candidates if candidate.id == room_id]
    if exact:
        candidates = exact
    if not candidates:
        events.append(_event("warning", message="没有找到匹配的微信群聊或联系人。", query=room_id))
        return {"room_id": None, "imported_count": 0, "events": events}
    if len(candidates) > 1:
        events.append(
            _event(
                "warning",
                message="会话筛选匹配到多个结果，请先从会话选择器中点选一个精确 ID。",
                candidates=[candidate.model_dump(mode="json", by_alias=True) for candidate in candidates[:20]],
            )
        )
        return {"room_id": None, "imported_count": 0, "events": events}

    candidate = candidates[0]
    events.append(_event("wechat_room_resolved", message=f"已匹配会话：{candidate.display_name}", roomId=candidate.id, displayName=candidate.display_name))
    rows = service.latest_rows(candidate.id, limit=limit)
    events.append(_event("wechat_db_read", message=f"已从已解密微信库读取 {len(rows)} 条消息", count=len(rows), roomId=candidate.id))
    if not rows:
        return {"room_id": candidate.id, "imported_count": 0, "events": events}

    chat_creates = [service.row_to_chat_message(row) for row in reversed(rows)]
    import_result = MessageStore(db).import_messages_with_result(chat_creates)
    imported_count = import_result.inserted_count
    events.append(_event("wechat_db_imported", message=f"已导入 {imported_count} 条新消息", count=imported_count))
    return {"room_id": candidate.id, "imported_count": imported_count, "events": events}


@router.get("/review-workbench", response_class=HTMLResponse)
def review_workbench() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>需求审查工作台</title>
  <style>
    :root { --bg:#f5f7fb; --panel:#fff; --line:#d8e0ea; --text:#17202c; --muted:#667085; --accent:#0f766e; --soft:#e7f5f2; --code:#eef2f6; --warn:#a15c07; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { height:58px; padding:0 22px; display:flex; justify-content:space-between; align-items:center; background:#fff; border-bottom:1px solid var(--line); }
    h1 { margin:0; font-size:18px; } h2 { margin:0 0 10px; font-size:15px; } h3 { margin:14px 0 8px; font-size:13px; color:var(--muted); }
    main { display:grid; grid-template-columns:minmax(360px,430px) minmax(420px,1fr) minmax(380px,520px); gap:1px; min-height:calc(100vh - 58px); background:var(--line); }
    section { min-width:0; padding:16px; background:var(--panel); overflow:auto; }
    label { display:block; margin:8px 0 4px; font-size:12px; color:var(--muted); }
    textarea,input,select { width:100%; border:1px solid #aab6c4; border-radius:7px; padding:9px; color:var(--text); background:#fff; font:inherit; font-size:13px; }
    textarea { min-height:120px; resize:vertical; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; line-height:1.45; }
    button { min-height:34px; border:1px solid #1f2937; border-radius:7px; background:#1f2937; color:#fff; padding:8px 11px; font:inherit; font-size:13px; cursor:pointer; }
    button.secondary { background:#fff; color:#1f2937; } button.accent { border-color:var(--accent); background:var(--accent); }
    .toolbar { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 12px; } .row { display:grid; grid-template-columns:1fr 1fr; gap:9px; }
    .hint { color:var(--muted); font-size:12px; line-height:1.55; margin:0 0 10px; } .badge { display:inline-flex; align-items:center; min-height:24px; padding:2px 8px; border-radius:999px; background:var(--soft); color:var(--accent); font-weight:700; font-size:12px; }
    .loading { display:none; align-items:center; gap:7px; min-height:24px; color:var(--muted); font-size:12px; }
    .loading.active { display:inline-flex; }
    .spinner { width:14px; height:14px; border:2px solid #cbd5e1; border-top-color:var(--accent); border-radius:50%; animation:spin .75s linear infinite; }
    button:disabled { opacity:.58; cursor:not-allowed; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .cards { display:grid; gap:9px; } .card { border:1px solid var(--line); border-left:5px solid var(--accent); border-radius:8px; padding:11px; background:#fff; cursor:pointer; } .card.suspect { border-left-color:var(--warn); }
    .conversation { border-left-color:#64748b; }
    .card-title { font-weight:700; font-size:14px; margin-bottom:5px; } .meta { color:var(--muted); font-size:12px; }
    pre { margin:0; border:1px solid var(--line); border-radius:8px; background:var(--code); padding:11px; white-space:pre-wrap; overflow:auto; max-height:430px; font-size:12px; line-height:1.45; }
    .divider { height:1px; background:var(--line); margin:14px 0; }
    @media (max-width:1160px) { main { grid-template-columns:360px 1fr; } section.audit { grid-column:1 / -1; } }
    @media (max-width:780px) { main { grid-template-columns:1fr; } header { height:auto; padding:12px; align-items:flex-start; flex-direction:column; } .row { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header><h1>需求审查工作台</h1><div><span id="status" class="badge">空闲</span> <span id="loadingIndicator" class="loading"><span class="spinner"></span><span id="loadingText">运行中</span></span> <span class="meta">需求雷达 → 人工审查 → WorkDoc 草稿 → Agent 输入包</span></div></header>
  <main>
    <section>
      <h2>1. 群聊消息批次</h2>
      <p class="hint">先选择群聊或联系人，再获取最近 50 条消息。这里不做全库大查询，不直接触发 Agent。</p>
      <div class="row">
        <div><label>会话类型</label><select id="conversationKind"><option value="chatroom">群聊</option><option value="contact">联系人</option><option value="filehelper">文件传输助手</option><option value="all">全部类型</option></select></div>
        <div><label>群聊筛选 / 联系人筛选</label><input id="conversationQuery" placeholder="按群名称或联系人名称搜索；精确 raw id 也可选"></div>
      </div>
      <div class="row">
        <div><label>需求提取方式</label><select id="extractorMode"><option value="llm">LLM 提取（推荐）</option><option value="local">本地规则提取</option></select></div>
        <div><label>速度提示</label><input value="LLM 会截断长消息并限制候选数" readonly></div>
      </div>
      <div class="toolbar"><button class="secondary" onclick="loadConversations()">搜索会话</button><button class="secondary" onclick="loadLatest50AndExtract()">获取并提取最近 50 条消息</button><button class="secondary" onclick="loadMessagePage()">加载更早 50 条</button><button class="secondary" onclick="resetSample()">重置样例</button></div>
      <label>已选会话 ID</label><input id="latestRoomId" placeholder="必须先选择一个会话，避免全库扫描">
      <h3>会话选择</h3><p class="hint">普通搜索只匹配群名称/联系人名称，并按最新消息时间倒序排列；raw id 仅用于精确定位已选会话。</p><div id="conversationCards" class="cards"></div>
      <h3>最近 50 条获取摘要</h3><p class="hint">旧接口参考：/messages?limit=50&order=desc；流式接口：/review-workbench/recent-50-stream；正式读取必须带 room_id。</p><pre id="latestFetchSummary">尚未获取最近消息。</pre>
      <textarea id="messages"></textarea>
      <div class="toolbar"><button class="accent" onclick="extractCandidates()">提取候选需求</button></div>
      <h3>提取结果原文</h3><pre id="extractOutput">尚未提取。</pre>
    </section>
    <section>
      <h2>2. 候选需求审查</h2>
      <p class="hint">选择候选需求，补齐仓库、范围、验收标准，再提升为 WorkDoc 草案和 Agent 输入包。</p>
      <div id="candidateCards" class="cards"></div><div class="divider"></div>
      <div class="row"><div><label>审查人</label><input id="reviewer" value="human-reviewer"></div><div><label>审查决定</label><select id="decision"><option value="confirm">确认</option><option value="reject">忽略</option><option value="merge">合并</option><option value="expire">过期</option></select></div></div>
      <label>项目或仓库</label><input id="projectOrRepo" value="agent-workflow">
      <label>工作目录</label><input id="workingDir" value="F:\\autowork\\agent-workflow\\backend">
      <label>范围</label><input id="scope" value="只实现审查确认过的后端行为；执行仍然必须经过 WorkDoc 审批。">
      <label>约束，每行一条</label><textarea id="constraints">不要绕过 WorkDoc 审批。
不要读取无关群聊。
原始群聊消息只能作为证据。</textarea>
      <label>验收标准，每行一条</label><textarea id="criteria">候选需求可以转换成 WorkDoc 草稿。
Agent 输入包包含证据和执行策略。
原始群聊消息不会直接创建 AgentRun。</textarea>
      <label>人工备注</label><textarea id="humanNotes">在需求审查工作台中人工确认。</textarea>
      <div class="toolbar"><button class="secondary" onclick="buildReviewDocument(false)">生成审查文档</button><button class="secondary" onclick="buildReviewDocument(true)">生成审查文档并写文件</button></div>
      <div class="toolbar"><button class="accent" onclick="promoteCandidate(false)">提升为草稿</button><button onclick="promoteCandidate(true)">提升为草稿并写入 inbox</button></div>
    </section>
    <section class="audit">
      <h2>3. 结果预览</h2><p class="hint">结果包含 WorkDoc 草案、Agent 输入包和 Agent brief markdown；它仍然只是审查产物，不会自动执行代码。</p>
      <h3>当前选中的候选需求</h3><pre id="selectedOutput">尚未选择候选需求。</pre>
      <h3>审查文档</h3><pre id="reviewDocumentOutput">尚未生成审查文档。</pre>
      <h3>提升结果</h3><pre id="promotionOutput">尚未提升。</pre>
    </section>
  </main>
  <script>
    let candidates = []; let selectedCandidate = null; let nextCursor = null; let activeRequests = 0;
    function sampleMessages(){return JSON.stringify({messages:[{id:'m-1',chatId:'dev-room',chatName:'项目开发群',sender:'PM',timestamp:'2026-06-19T10:00:00+08:00',text:'看板页需要加一个按负责人筛选，验收是选人后列表只显示对应任务',msgType:'text',source:'manual'},{id:'m-2',chatId:'dev-room',chatName:'项目开发群',sender:'Dev',timestamp:'2026-06-19T10:02:00+08:00',text:'先别重构，只改筛选组件和相关接口参数',msgType:'text',source:'manual'},{id:'m-3',chatId:'dev-room',chatName:'项目开发群',sender:'QA',timestamp:'2026-06-19T10:04:00+08:00',text:'今天发版前要修，注意不要影响原来的状态筛选',msgType:'text',source:'manual'}]},null,2)}
    function setStatus(text){document.getElementById('status').textContent=text} function show(id,value){document.getElementById(id).textContent=typeof value==='string'?value:JSON.stringify(value,null,2)} function lines(id){return document.getElementById(id).value.split('\\n').map(x=>x.trim()).filter(Boolean)}
    function setLoading(active,text){const node=document.getElementById('loadingIndicator'); const label=document.getElementById('loadingText'); if(text){label.textContent=text} activeRequests=Math.max(0,activeRequests+(active?1:-1)); node.classList.toggle('active',activeRequests>0); document.querySelectorAll('button').forEach(button=>button.disabled=activeRequests>0)}
    async function withLoading(text,work){setLoading(true,text); try{return await work()} finally{setLoading(false)}}
    async function request(url,options){const res=await fetch(url,options); const text=await res.text(); let data; try{data=JSON.parse(text)}catch{data=text} return {ok:res.ok,status:res.status,data}}
    async function post(url,body){return request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
    function resetSample(){document.getElementById('messages').value=sampleMessages(); setStatus('样例已载入')}
    function renderConversations(items){const root=document.getElementById('conversationCards'); root.innerHTML=''; if(!items.length){root.innerHTML='<p class="hint">没有匹配会话。</p>'; return} items.forEach(item=>{const node=document.createElement('div'); node.className='card conversation'; node.innerHTML=`<div class="card-title">${escapeHtml(item.displayName)}</div><div class="meta">${escapeHtml(item.kind)} · ${escapeHtml(item.id)} · ${escapeHtml(item.messageCount)} 条 · ${escapeHtml(item.latestTime||'无时间')}</div><div class="meta">${escapeHtml(item.lastPreview||'')}</div>`; node.onclick=()=>{document.getElementById('latestRoomId').value=item.id; document.getElementById('conversationQuery').value=item.displayName; setStatus(`已选择 ${item.displayName}`)}; root.appendChild(node)})}
    async function loadConversations(){return withLoading('正在搜索会话...',async()=>{const params=new URLSearchParams({kind:document.getElementById('conversationKind').value,limit:'100'}); const q=document.getElementById('conversationQuery').value.trim(); if(q){params.set('query',q)} const result=await request(`/wechat-directory/conversations?${params.toString()}`); renderConversations(result.ok?(result.data.conversations||[]):[]); show('latestFetchSummary',result.data); setStatus(result.ok?`${result.data.count} 个会话`:`会话读取失败 ${result.status}`)})}
    function chatMessageToDemandMessage(message){const raw=message.raw_json||{}; return {id:`chat-${message.id}`,chatId:message.room_id,chatName:raw.room_display_name||raw.display_name||message.room_id,sender:raw.sender_display_name||message.sender_display_name||message.sender_hash||null,timestamp:message.timestamp,text:message.text,msgType:normalizeMessageType(message.message_type),source:message.platform||'stored-chat',raw:message}}
    function pageItemToDemandMessage(item){return {id:`wechat-${item.conversationId}-${item.createTime}-${item.localId||''}`,chatId:item.conversationId,chatName:item.conversationDisplayName,sender:item.senderDisplayName,timestamp:item.timestamp,text:item.text,msgType:normalizeMessageType(item.messageType),source:'wechat-directory-page',raw:item}}
    function normalizeMessageType(type){const value=String(type||'text').toLowerCase(); return ['text','image','file','link','system','unknown'].includes(value)?value:'text'}
    function renderCandidates(){const root=document.getElementById('candidateCards'); root.innerHTML=''; if(!candidates.length){root.innerHTML='<p class="hint">还没有候选需求。</p>'; return} candidates.forEach((candidate,index)=>{const node=document.createElement('div'); node.className=`card ${escapeHtml(candidate.status)}`; node.innerHTML=`<div class="card-title">${escapeHtml(candidate.title)}</div><div class="meta">${escapeHtml(candidate.id)} · ${escapeHtml(candidate.requirementType)} · ${escapeHtml(candidate.status)} · ${escapeHtml(candidate.confidence)} ${escapeHtml(candidate.confidenceScore)}</div><div class="meta">缺失字段：${escapeHtml((candidate.missingFields||[]).join('，')||'无')}</div>`; node.onclick=()=>selectCandidate(index); root.appendChild(node)})}
    function selectCandidate(index){selectedCandidate=candidates[index]; show('selectedOutput',selectedCandidate); setStatus(`已选择 ${selectedCandidate.id}`)}
    async function extractCandidates(){let payload; try{payload=JSON.parse(document.getElementById('messages').value)}catch(error){show('extractOutput',`JSON 格式错误：${error}`); setStatus('JSON 格式错误'); return} return withLoading(`正在用 ${extractorMode()==='llm'?'LLM':'本地规则'} 提取候选需求...`,async()=>{const result=await post(demandRadarEndpoint(),payload); show('extractOutput',result.data); candidates=result.ok?(result.data.candidates||[]):[]; selectedCandidate=candidates[0]||null; renderCandidates(); if(selectedCandidate) show('selectedOutput',selectedCandidate); setStatus(result.ok?`${candidates.length} 个候选需求`:`错误 ${result.status}`)})}
    function extractorMode(){return document.getElementById('extractorMode').value}
    function demandRadarEndpoint(){return extractorMode()==='llm'?'/demand-radar/extract-llm':'/demand-radar/extract'}
    function latest50StreamUrl(){const room=document.getElementById('latestRoomId').value.trim(); if(!room){return null} const params=new URLSearchParams({room_id:room,extractor:extractorMode()}); return `/review-workbench/recent-50-stream?${params.toString()}`}
    function appendProgress(event){const current=document.getElementById('latestFetchSummary').textContent; const line=`[${new Date().toLocaleTimeString()}] ${event.message||event.type}`; document.getElementById('latestFetchSummary').textContent=(current&&current!=='尚未获取最近消息。'?current+'\\n':'')+line; document.getElementById('latestFetchSummary').scrollTop=document.getElementById('latestFetchSummary').scrollHeight}
    async function loadLatest50AndExtract(){const url=latest50StreamUrl(); if(!url){show('latestFetchSummary','请先搜索并选择一个群聊或联系人。'); setStatus('未选择会话'); return} return withLoading('正在获取并提取最近 50 条...',async()=>{setStatus('正在流式获取最近 50 条消息'); document.getElementById('latestFetchSummary').textContent=''; show('extractOutput','等待流式结果...'); candidates=[]; selectedCandidate=null; nextCursor=null; renderCandidates(); const response=await fetch(url); if(!response.ok||!response.body){const text=await response.text(); show('latestFetchSummary',`流式请求失败 ${response.status}: ${text}`); setStatus(`读取失败 ${response.status}`); return} const reader=response.body.getReader(); const decoder=new TextDecoder('utf-8'); let buffer=''; let demandMessages=[]; while(true){const chunk=await reader.read(); if(chunk.done) break; buffer+=decoder.decode(chunk.value,{stream:true}); const parts=buffer.split('\\n'); buffer=parts.pop()||''; for(const line of parts){if(!line.trim()) continue; const event=JSON.parse(line); appendProgress(event); if(event.type==='message'){demandMessages.push(event.demandMessage); if(demandMessages.length<=50){document.getElementById('messages').value=JSON.stringify({messages:demandMessages},null,2)}} if(event.type==='candidates'){candidates=event.candidates||[]; show('extractOutput',event); renderCandidates(); selectedCandidate=candidates[0]||null; if(selectedCandidate) show('selectedOutput',selectedCandidate); setStatus(`${candidates.length} 个候选需求`)}}} if(buffer.trim()){appendProgress(JSON.parse(buffer))} if(!candidates.length){show('extractOutput',{candidates:[]})}})}
    async function loadMessagePage(){const room=document.getElementById('latestRoomId').value.trim(); if(!room){show('latestFetchSummary','请先选择会话。'); return} return withLoading('正在加载更早消息...',async()=>{const params=new URLSearchParams({conversation_id:room,limit:'50'}); if(nextCursor&&nextCursor.beforeTs){params.set('before_ts',nextCursor.beforeTs); if(nextCursor.beforeLocalId){params.set('before_local_id',nextCursor.beforeLocalId)}} const result=await request(`/wechat-directory/messages?${params.toString()}`); show('latestFetchSummary',result.data); if(result.ok){nextCursor=result.data.nextCursor; const demandMessages=(result.data.items||[]).map(pageItemToDemandMessage); document.getElementById('messages').value=JSON.stringify({messages:demandMessages},null,2); setStatus(`分页载入 ${demandMessages.length} 条`)}})}
    async function buildReviewDocument(writeDocument){let payload; try{payload=JSON.parse(document.getElementById('messages').value)}catch(error){show('reviewDocumentOutput',`JSON 格式错误：${error}`); setStatus('JSON 格式错误'); return} if(!Array.isArray(payload.messages)){show('reviewDocumentOutput','messages 必须是数组，不能自动当作空数组处理。'); setStatus('messages 字段错误'); return} return withLoading(writeDocument?'正在生成并写入审查文档...':'正在生成审查文档...',async()=>{const body={messages:payload.messages,writeDocument:writeDocument,title:`${document.getElementById('conversationQuery').value||'群聊'} 需求审查文档`}; const endpoint=candidates.length?'/message-documents/from-candidates':'/message-documents/from-demand-messages'; if(candidates.length){body.candidates=candidates}else{body.extractor=extractorMode()} const result=await post(endpoint,body); if(result.ok){show('reviewDocumentOutput',result.data.markdown)}else{show('reviewDocumentOutput',result.data)} setStatus(result.ok?`审查文档已生成：${result.data.reviewDocumentId}`:`文档生成失败 ${result.status}`)})}
    async function promoteCandidate(writeInbox){if(!selectedCandidate){setStatus('请先选择候选需求'); return} return withLoading('正在提升为草稿...',async()=>{const payload={candidate:selectedCandidate,decision:{candidateId:selectedCandidate.id,decision:document.getElementById('decision').value,reviewer:document.getElementById('reviewer').value,reviewedAt:new Date().toISOString(),reason:'工作台人工审查',humanFields:{projectOrRepo:document.getElementById('projectOrRepo').value,workingDir:document.getElementById('workingDir').value,branch:'main',targetObject:selectedCandidate.title,actualBehavior:selectedCandidate.hypothesis,expectedBehavior:lines('criteria')[0]||selectedCandidate.hypothesis,desiredBehavior:selectedCandidate.hypothesis,scope:document.getElementById('scope').value,constraints:lines('constraints'),acceptanceCriteria:lines('criteria'),outOfScope:['原始群聊消息不能直接触发 AgentRun'],humanNotes:document.getElementById('humanNotes').value,allowAgent:true}},writeInbox:writeInbox}; const result=await post('/requirement-promotion/promote',payload); show('promotionOutput',result.data); setStatus(result.ok?'已提升':`错误 ${result.status}`)})}
    function escapeHtml(value){return String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;")}
    resetSample(); renderCandidates();
  </script>
</body>
</html>
"""
