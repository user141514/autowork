# Agent Workflow

群聊驱动的自主开发工作流系统。

当前实现阶段：Phase 1 项目骨架。

## 目录

- `backend/`: FastAPI 后端
- `docs/`: 架构与范围文档

## 当前可运行内容

```bash
cd agent-workflow/backend
python -m pip install -e ".[dev]"
python -m pytest
uvicorn app.main:app --reload
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

