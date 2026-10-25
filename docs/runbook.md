> 2026-10-23 本机更新：私有.env已配置真实Provider、项目offerpilot-acceptance、8081。当前用make up / make down即可管理原卷；infra/acceptance.compose.yaml固定demo，请勿用于当前真实模式重启。真实调用证据见live-test-report.md。

# 运行与恢复手册

## 启停与迁移

按 README 创建 .env，Compose PUBLIC_ORIGIN 使用实际浏览器地址（默认 http://localhost:8080）。运行 `make up`；`docker compose ps -a` 确认 migrate Exited(0)、其余服务运行。`curl --fail http://localhost:8080/api/v1/health/ready` 与 `/api/v1/capabilities` 检查数据库/schema/模式。`make down` 不删卷。

升级前在自己的受控环境备份；本项目目前没有自动备份。保留原卷，`docker compose build` 后执行 `docker compose run --rm migrate`，成功后 `docker compose up -d api worker web`。迁移失败先停业务写入并修复原因，不使用 create_all 绕过。`docker compose logs --tail=100 migrate` 查看诊断。不可在真实库运行测试，不能用 down -v 排障。

开发 `make dev` / `make migrate` 使用 DATABASE_URL；Compose 内固定数据库地址 db。本地 55432 的开发库与 Compose 的私有卷是两套数据。测试要求库名 offerpilot_test*，新库升级测试仅清理自己创建的随机库。

## 账号与常见连接问题

`docker compose exec api python -m offerpilot.cli create-user --username <name>` 交互输入密码，管理员加 --admin。demo seed 必须显式 APP_MODE=demo 且非 production；不会覆盖已存在账号密码或重新授权。

403 Origin/CSRF：核对 PUBLIC_ORIGIN 与浏览器 scheme/host/port；localhost 与 127.0.0.1 不是相同 Origin。重新载入获取 CSRF。登录连续失败触发 15 分钟窗口限制，不应修改表绕过正常保护。401：重新登录；7 天绝对有效期，退出/删账号立即失效。

production 强制 HTTPS/live；默认 Caddy 只监听容器 HTTP80，用于本机。公网使用者需自行提供 TLS 入口、精确 PUBLIC_ORIGIN 与安全网络配置，项目未发布公网。

## Worker 与 Provider 故障

`docker compose logs --tail=100 worker` 仅看运行 ID、步骤与错误类型；不得把私有正文、Cookie、密钥粘贴到公开 issue。`docker compose restart worker` 后队列仍在 PG；崩溃任务在租约过期后重领，已完成步骤复用。旧租约回写会拒绝。正常 cancel/retry 从界面或 API 操作；重试产生新 run 并保留 retry_of，不直接改数据库终态。删除清理使用删除请求专用重试按钮。

增加 Worker 实例前核对全局/每用户并发上限。DB 是唯一队列；无 Redis/Celery 需要额外恢复。单次调用可能已被外部计费而本地未收到响应，这类 usage 记录未知。不要把重试后结果等同于远端 exactly once。

缺 key：capabilities 明示不可用，live 返回 503；补充服务端环境变量并重新创建 api/worker。不切换 demo 冒充恢复。429/超时/5xx 受有限重试和预算约束；partial 保留已成功候选，用户可检查报告后重试。schema/语义错误修正一次仍失败时显示失败，材料保留手工编辑路径，回答已经保存可重新请求反馈。

页面不可读：检查来源策略、URL 与 Tavily 返回。metadata_only 不执行 Extract；已有公开摘要可整理为标注“详情待核实”的招聘卡片，无法确定的字段留空，无具体职位的目录折叠为线索；不依据无法访问判定关闭/诈骗。不允许将搜索摘要复制为完整 JD。正式来源需核对用途/使用依据；政策收紧触发正文和引用衍生清理，不应手工强制补回。

旧搜索只有链接：打开该次找岗结果，点击“AI 整理已有链接”。已有卡片可“重新整理结果”；两者只读取已保存的公开依据，不重新搜索。新搜索直接输入自然语言并点“AI 找岗位”，每次默认最多3组查询。难度筛选基于模型粗略估计；缺失薪资、学历或要求需到来源确认。只做公开找岗时勾选本页独立授权即可，不必授权处理个人简历。

SSE：Caddy `flush_interval -1`；代理不能缓存 /api。断线客户端按 seq 补发并轮询 run 状态。刷新时运行 ID 在 URL 或“进行中的运行”中恢复，不重复自动创建 run。

## 导出、删除、保留

资料页先看删除预览；请求后立即不可用于新生成、审批与导出。Worker 清理成功才显示 succeeded。删除失败应重试同一删除请求；不可用状态仍保持。相关混合生成版本整体清除，历史申请只保留材料已删除墓碑。

账户删除需密码及确认，立即撤销登录；保存一次性返回的 receipt，用 X-Deletion-Receipt 查询/重试该删除，不能读取任何业务数据。Worker 清理后 owner 内容和私有运行记录删除，受限删除回执不保存可还原正文。

导出只允许本人，默认 JSON，CSV 是摘要。数据库保存导出 payload，默认 24 小时后下载返回 410；Worker 轻量维护循环清理到期内容。没有本地导出目录或对象存储。登录失败记录维护清理超过一天数据。租约恢复/保留清理不执行搜索订阅。

**备份实际状态：未配置。** Compose 卷不是独立备份，没有承诺备份清除窗口。未来如配置 pg_dump/卷快照，部署者必须制定加密、访问、恢复与删除窗口，并在恢复后重放删除墓碑/来源限制，验证不会恢复已删内容。外部 Provider 接收的数据受其设置与政策影响，本应用不保证即时远端删除；未启用外部正文 Trace。

## 真实验收

先按 source-feasibility.md 建立独立验收库与两来源策略。配置 live 与两个有效 key，再执行 `make test-live`；缺配置非零退出，不能计为通过。查看 docs/live-evidence.json 的实际 run/model/usage/候选/时间，再在 UI 人工核对真实 JD、第二来源、面经与事实引用。没有可读面经样本必须保留未验收项。不要用真实求职者简历，不对真实公司投递或发消息。
