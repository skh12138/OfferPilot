# 固定图与数据库执行协议

采用已确定的 Vue/FastAPI/PostgreSQL17/LangGraph。S0 空库迁移先建立部署元数据，后续迁移按阶段增加领域。队列恢复依赖 SQL 步骤与租约，不启用 LangGraph checkpointer。

当前开发主机附带 Python3.12.14、Node24.19.0 可用于构建；系统默认版本不适用。所有脚本从 PATH 查找版本并报错，不写机器绝对路径。

实现使用固定 LangGraph 入口校验节点和按任务种类绑定的领域执行节点；领域节点内部的搜索、提取、归一、生成等子步骤使用持久 step_key，避免把私有正文放入图状态。没有 checkpointer/interrupt，也没有自由工具循环。恢复与租约保证来自 PostgreSQL 协议。

材料自述采用保守原文片段引用：暂不接受模型自由改写后直接作为本人已完成经历。自由文本是提纲/联系草稿，个人经历必须通过 claims 引用；仍须本人审核。这样会拒绝部分合理改写，记录为首版能力限制。

依赖实际兼容验证选择 pnpm11.25.0。其构建许可配置使用 allowBuilds；旧 onlyBuiltDependencies 在该版本被忽略，已按官方说明修复。Prettier 负责格式，ESLint/Vue essential 与 TypeScript strict 负责代码检查，避免格式规则冲突。Docker安装层分离并使用 uv/pnpm 缓存，源代码变更不重装全部第三方依赖。
