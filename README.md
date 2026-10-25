# OfferPilot

从岗位查找到上岸全流程

私有求职工作台：找岗、证据校对、资格匹配、申请与投递快照、材料审核、面试训练、复盘、Offer、任务及数据控制。实现范围以 `04_OfferPilot_工程Agent开发总提示词.md` 和业务 v2 为准。

**当前状态：离线验证完成，真实 Provider 与合成资料业务流程的 Live 冒烟已通过；国内真实 JD 和面经正文完整验收仍待完成。** 本机已配置私有凭据，密钥不进入报告；来源实测存在不可读、目录页和非目标结果，不声称全网覆盖。详情见 [测试报告](docs/test-report.md)、[功能与验收矩阵](docs/progress.md)、[来源可行性](docs/source-feasibility.md)。

## 最快启动：Docker Compose

需要 Docker Engine / Docker Desktop 与支持 `!override` 的 Compose 2.24.4+。首次构建需要下载固定镜像及锁定依赖；仓库路径支持中文和空格。

```sh

# 仅首次新环境：已有 .env 时不要覆盖（其中可能保存密钥）。
cp .env.example .env
# Docker 同源入口必须使用 8080；本地 Vite 开发才使用 5173。
# 将 .env 的 PUBLIC_ORIGIN 改为 http://localhost:8080。
make up
# 仅 APP_MODE=demo 的新环境执行；本机当前 live 环境跳过。
docker compose exec api python -m offerpilot.cli seed-demo
```

打开 <http://localhost:8080>。显式 demo 账号为 `demo`、`demo_other`，密码均为 `offerpilot-demo-2026`；前者可管理来源策略。不自动创建生产账号。`make down` 停止服务，保留数据库卷。

正常账号（交互输入至少 10 字符密码）：

```sh
docker compose exec api python -m offerpilot.cli create-user --username myname
# 如需要管理员，在命令末尾加 --admin。
```

Compose 包含 db、一次性 migrate、api、worker、web。只有 Web 的本机 8080 端口暴露。API/Worker 等待迁移成功，数据库卷持久保存；无自动清空、自动投递或自动联系外部公司的行为。

## 模式与配置

| 配置 | 含义 |
| --- | --- |
| APP_MODE=demo | 明示使用合成 Provider，全部页面显示演示标识；可完整运行流程，不调用云端 |
| APP_MODE=live | 真实适配器；缺凭据时返回能力不可用/503，绝不回退合成结果 |
| APP_MODE=test | 仅隔离自动测试使用 |
| ENVIRONMENT=production | 强制 live 与 HTTPS PUBLIC_ORIGIN、安全 Cookie；需自行配置 HTTPS 网关 |
| COMPOSE_PROJECT_NAME / WEB_PORT | Compose 项目名与本机端口；本机已设 offerpilot-acceptance / 8081 |
| PUBLIC_ORIGIN | 浏览器实际同源地址，CSRF 严格匹配，包括端口 |
| DATABASE_URL | 本地 Python 进程使用的 PostgreSQL17 URL；Compose 内使用 db 服务名 |
| DB_PASSWORD | Compose 数据库密码；修改后不会自动修改已有数据库用户密码 |
| ALLOW_REGISTRATION | 默认 false；常规账号通过 CLI 建立 |
| DEEPSEEK_API_KEY / TAVILY_API_KEY | 仅服务端环境变量，不进入前端或导出 |
| LLM_MODEL | 默认 deepseek-flash，每次调用保存实际请求与响应模型；别名不代表完全可复现 |
| RUN_MAX_CALLS / RUN_INPUT_TOKENS / RUN_OUTPUT_TOKENS | 每次运行的调用/输入估算/输出预算，默认 50 / 80000 / 24000 |
| RUN_TIMEOUT_SECONDS | 默认运行总时限 600 秒；单次网络超时 60 秒 |
| GLOBAL_RUN_CONCURRENCY / USER_RUN_CONCURRENCY | 数据库执行租约并发上限，默认 2 / 1 |
| EXPORT_RETENTION_HOURS | 导出保留窗口，默认 24 小时 |

表中配置已在 Compose 的共享 environment 中显式传入。生产部署应更换 DB_PASSWORD、关闭注册、使用 HTTPS，并核对来源使用依据。仓库默认 Caddy 配置只用于本机 HTTP，没有部署公网证书或备份。

## 本地开发与验证

运行时：Python 3.12.14、Node 24.19.0、uv 0.13.5、pnpm 11.25.0、PostgreSQL 17.6。版本文件和锁文件已经保留在交付目录中。确保这些工具在 PATH 中，不能用系统 Python3.8 / Node23 替代。

独立开发数据库（不要对已有容器重复创建）：

```sh
docker run -d --name offerpilot-dev-pg17 \
  -e POSTGRES_USER=offerpilot -e POSTGRES_PASSWORD=offerpilot \
  -e POSTGRES_DB=offerpilot -p 127.0.0.1:55432:5432 \
  -v offerpilot-development-db:/var/lib/postgresql/data \
  postgres:17.6-bookworm@sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3
docker exec offerpilot-dev-pg17 createdb -U offerpilot offerpilot_test
cp .env.example .env
# 本地开发保留 PUBLIC_ORIGIN=http://localhost:5173。
make bootstrap
make migrate
make seed-demo
make dev
```

开发地址 <http://localhost:5173>，API 文档 <http://localhost:8000/docs>。Vite 通过代理请求 API，API 与独立 Worker 同包不同进程。停止 `make dev` 会关闭它启动的子进程。

首次浏览器测试运行 `pnpm exec playwright install chromium`。本机已有 Chrome 时可用 `PLAYWRIGHT_CHANNEL=chrome make verify`。测试不使用开发库：后端默认 `offerpilot_test`，浏览器默认 `offerpilot_test_e2e`；迁移升级测试新建随机命名的 `offerpilot_test_upgrade_*` 空库并仅删除该临时库。测试用户是随机合成账号，不清空其他数据。

| 入口 | 等价命令 / 实际动作 |
| --- | --- |
| make bootstrap | uv sync --frozen；pnpm install --frozen-lockfile；python scripts/runtime_check.py |
| make dev | .venv/bin/python scripts/dev.py（先迁移再启动 API/Worker/Vite） |
| make up / down | docker compose up --build -d / docker compose down |
| make migrate | .venv/bin/alembic -c apps/server/alembic.ini upgrade head |
| make seed-demo | .venv/bin/python -m offerpilot.cli seed-demo |
| make create-user USERNAME=myname | 同包 CLI create-user，交互输入密码；ADMIN=1 添加管理员 |
| make check | Ruff lint/format；mypy strict；vue-tsc；ESLint；Prettier |
| make test | pytest unit/integration/contract；pnpm --dir apps/web test（Vitest） |
| make e2e | .venv/bin/python scripts/e2e.py（真实 PG/API/Worker/浏览器，显式 demo Provider） |
| make test-live | .venv/bin/python scripts/live.py（真实收费 API，必须显式配置） |
| make build | pnpm build；uv build --wheel；scripts/validate_deployment.py；容器构建由 make up 和 CI 单独执行 |
| make contract | 导出 contracts/openapi.json，openapi-typescript 生成前端类型，Prettier 格式化 |
| make contract-check | 重新生成并按字节检测契约漂移 |
| make verify | check → test → e2e → build → contract-check |

`UV`、`PNPM` 可通过 make 参数指定可执行文件；脚本不依赖开发者的绝对路径。CI 的离线任务执行 make verify，容器任务执行 docker compose build；尚未在远程 GitHub 仓库实际运行 CI。

## 合成演示流程

1. 登录 demo；在“我的资料”粘贴 `fixtures/synthetic/resumes.json` 中一份合成文本。可仅保存文本；解析需要在界面明确授权。逐条确认事实或标为计划中，保存新版本。
2. “找岗位”直接输入“帮我找找杭州开发相关实习”，点击“AI 找岗位”。公开搜索信息单独授权，不读取简历；结果统一展示公司、岗位、要求、来源和 AI 预测难度。缺失字段留空，摘要结果标注待核实；可筛选、保存申请意向、取消、刷新恢复或重新整理旧链接。手动城市/天数等条件在高级设置中。演示模式候选全部标明合成。
3. “岗位库”查看正文/段落证据、字段校对、缺失与核验，设置意向、比较、处理重复，加入申请。也可导入 `text,url` 两列 CSV，最多 500 行/5MB。
4. 申请详情保存三个独立链接；打开链接不改变状态。只有本人确认“实际投递”才锁定材料。可手工补录未知材料的历史投递、直接新增技术面、改期、记录无变化查询和复盘。
5. 生成材料后人工审核，批准才建立任务；生成训练包，核对来源类别后采用、作答、查看反馈、调整掌握与复习时间。没有真实面经时标记为定制生成。
6. “复盘与 Offer”记录口头/书面 Offer、比较和决定；“今日待办”查看任务、轮次、复习及回复期限。资料页支持导出、删除预览、删除进度和撤销授权。

## 真实接入续作

设置 live、有效密钥及来源策略；未知来源默认只保存线索。来源需在“运营维护”登记域名、用途、extract/store 策略与使用依据。不能仅为测试通过就允许全文镜像。

准备独立 `offerpilot_live_acceptance*` 数据库并迁移，在该库建立管理员及至少两条已核对的来源策略。设置 `LIVE_DATABASE_URL`（同 DATABASE_URL 的格式），执行 `make test-live`。该命令会实际产生 API 费用并记录合成测试账号与调用证据，不会真实投递。缺配置返回非零。成功调用后还必须按 [来源可行性](docs/source-feasibility.md) 在 UI 人工抽查；探针成功本身不等于完整真实验收。

## 已知边界

- 真实搜索、DeepSeek JSON、简历/JD解析、5道题、采用/回答反馈和材料生成已实测通过（个人输入为合成）。招聘正文抽取存在站点限制，尚未完成国内真实相关JD→题单的完整样本验收、真实面经引用及真实个人资料审核。离线与Live合成样本不代表模型准确率或网站覆盖率。
- 自述 claims 保守要求引用已确认事实的原文片段，可能拒绝合理改写；仍需人工审核。关键词规则不代表完整语义理解。
- 未知/受限来源不会构造完整 JD；不登录招聘网站、不绕过验证码、不自动发送或投递。
- P0 列表适用于个人规模；岗位排序先读取本人候选后计算确定性排名，无大规模检索基础设施。
- 备份、第三方数据保留/删除和公网部署未配置。用户授权撤销能停止本应用后续调用，无法保证已发给第三方的数据即时删除。

更多操作见 [运行手册](docs/runbook.md)，进程与数据约束见 [实际架构](docs/architecture.md)，接口见 [API](docs/api.md)。

## 本机当前启动与关闭

本机私有 .env 已配置 live、COMPOSE_PROJECT_NAME=offerpilot-acceptance、WEB_PORT=8081、PUBLIC_ORIGIN=http://localhost:8081。仍访问 <http://localhost:8081>，既有账户及数据库保留。已有 .env 不要重新复制覆盖。

```sh
make up       # 构建、迁移、启动当前8081真实模式
make down     # 关闭当前项目，保留数据库卷
```

也可显式执行：

```sh
docker compose -p offerpilot-acceptance -f compose.yaml -f infra/local.compose.yaml up -d
```

infra/acceptance.compose.yaml 刻意固定 demo，当前真实模式不要再使用该覆盖文件。密钥为服务端环境变量，不需填到网页；资料页的外部模型授权仍需本人确认。旧合成记录不会因模式切换变成真实招聘信息。

本次真实流程在独立项目 offerpilot-live-validation、8082和独立数据库卷执行，合成管理员凭据只保存在 .local/live-access.json(0600)。验证后该临时栈关闭并保留卷。重现需先以 infra/live-validation.compose.yaml 启动该项目，再运行 scripts/live_stack_smoke.py；这将真实消耗Provider额度。报告见 docs/live-test-report.md。

## UI 改造（2026-10-24）

暖白墨绿主题、扁平列表/响应式预览、申请阶段看板、逐题练习和会话内草稿已完成。功能保留与验证见 [UI 验收报告](docs/ui-redesign/acceptance.md)、[逐页盘点](docs/ui-redesign/inventory.md)、[进度](docs/ui-redesign/progress.md)，合成数据前后截图位于 `docs/ui-redesign/screenshots/`。本次只更新前端，不修改原 API、迁移、业务规则或主数据库；真实联网验收范围仍以上述原测试报告为准。
