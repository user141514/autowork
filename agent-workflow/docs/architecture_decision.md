# Architecture Decision

## ADR-001: WorkDoc 是核心契约

决定：

系统不允许 Agent 直接读取群聊并修改代码。聊天消息必须先沉淀为 WorkDoc，经过校验和审批后才能进入 AgentRunner。

原因：

- 群聊内容噪声高，不适合作为直接执行输入。
- WorkDoc 可以作为可审核、可复现、可追踪的任务契约。
- 后续 Agent、聊天平台、Git 平台都可替换，但 WorkDoc 契约保持稳定。

## ADR-002: 第一版使用 FastAPI + SQLite

决定：

MVP 后端使用 FastAPI，数据库使用 SQLite。

原因：

- 启动成本低。
- 适合本地工作流和 mock demo。
- 后续可以迁移到 PostgreSQL，但不影响领域模型和服务边界。

## ADR-003: 危险操作默认 dry-run

决定：

所有危险操作默认 dry-run，包括 push、PR、敏感文件修改和真实外部 Agent 调用。

原因：

- MVP 阶段优先验证流程闭环。
- 防止系统在未充分验证前对真实仓库或远程平台产生不可控影响。

## ADR-004: Phase 1 只实现项目骨架

决定：

Phase 1 只实现可运行骨架、配置、日志、数据库初始化和健康检查。消息导入、WorkDoc、AgentRunner、GitPublisher 后续分阶段实现。

原因：

- 每一步都保持可运行。
- 避免一次性写完整 MVP 导致边界混乱。
- 让服务边界先稳定下来。

