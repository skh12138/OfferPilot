> 最新找岗改造：统一招聘卡片、独立公开信息授权、预测难度、旧结果重整与保存意向；完整make verify为106项后端、4项前端、5条浏览器流程，构建/迁移/契约通过。真实公开招聘搜索与卡片已执行，详见discovery-update.md、verification-discovery.json/log及discovery-live-evidence.json。以下为首次离线交付与先前Live修复的历史记录，“当时缺凭据”不表示当前状态。

> 先前Live修复：多行JD段落映射问题已修复；当次回归94项后端、3项前端、4条浏览器流程，真实搜索、简历/JD解析、5道题、反馈、材料生成通过。见live-test-report.md及verification-live-fix.log。

# 实际测试报告

日期：2026-10-23（Asia/Shanghai）。结论：**实现与离线验证完成，真实验收待完成。** 本报告中的通过均有实际命令结果；未提供外部密钥，没有真实模型质量、招聘站覆盖率或真实用户效果声明。

## 环境与结果

本机 macOS/arm64，Python3.12.14、Node24.19.0、pnpm11.25.0、uv0.13.5；真实 PostgreSQL17.6 Docker 数据库。浏览器为本机 Chrome（Playwright channel=chrome）；CI 配置安装 Chromium，但未在远程仓库运行 CI。

| 命令 / 验证 | 实际结果 |
| --- | --- |
| make bootstrap | 退出0；uv --frozen 检查75个包，pnpm --frozen-lockfile无漂移，运行时检查通过 |
| make verify | 退出0；check、test、e2e、build、contract-check 全部执行 |
| Ruff lint / format | 98个应用 Python 文件通过 |
| mypy strict | 98个源文件通过，无全局忽略 |
| vue-tsc / ESLint / Prettier | 通过 |
| pytest unit/integration/contract | **93 passed**，13.44秒；无 Live 混入，无关键 skip |
| Vitest | **3 passed / 2 files**；登录失败、只读草稿隔离、文本转义 |
| Playwright | **4 passed**，35.7秒；三个主流程与恢复/退出/响应式 |
| 前端生产构建 | Vite 成功，1726模块；Element Plus 分块约917kB，存在大分块提示，非构建失败 |
| Python 包 | offerpilot-0.1.0-py3-none-any.whl 实际构建成功 |
| 契约漂移 | 重新导出 OpenAPI、生成并格式化 TS，按字节比对通过；111个实际操作 |
| 迁移 | 真实空库0001→0009；逐阶段升级后保留基础元数据和用户哨兵；最终 alembic check 无漂移 |
| Docker Compose 构建 | Python/Web 镜像实际构建成功，锁定镜像digest；五服务实际启动 |
| Compose/Caddy 冒烟 | migrate Exited(0)、db healthy、api/worker/web运行；8081的ready=ready，capabilities=demo |
| scripts/live.py | **退出1，未执行真实验收**；明确缺 DEEPSEEK_API_KEY 与 TAVILY_API_KEY，无 fixtures 回退 |

最终 make verify 的原始控制台输出保存在 `docs/verification.log`（仅构建与合成测试结果，路径归一化）；补充结构化状态见 `docs/verification.json`。bootstrap、Compose 诊断保留在本地忽略日志中。测试数据和开发/Compose数据独立，不通过清空真实库获得绿灯。

## 场景与证据

- `tests/integration/test_s1.py`：登录/CSRF、跨用户资料、解析未确认事实、不可变版本、手工 JD/校对/匹配、无需授权仅存文本、降低事实状态时旧版本也撤回、人工补充字段与模型输出区别。
- `test_s2.py` / `test_matrix.py`：搜索确认、报告、零/部分/全失败、SSE序号/补发、租约换领/旧写拒绝、同URL新版本、疑似重复合并/撤销、空外部ID不误并、同ID URL别名、幂等异payload409、取消、live缺密钥不降级。
- `test_s3.py` / `test_event_boundaries.py`：真实提交确认与材料快照、查询不变、直接技术面、轮次改期提醒不重复、并发旧revision412、更正/重开、keep/cancel/detach任务选择、批准/基准与重复副作用、错误密码/Origin/15分钟限流。
- `test_s4.py`：无面经正文的明确降级、题型/理由/来源、采用一次、看答案不改掌握、回答先保存、反馈失败保留、本人纠正评价。
- `test_s5.py`：口头Offer/期限不过度推断、接受不关闭其他申请、暂停生成时删除、旧执行者不能发布、导出不含删掉事实、账户删除立即登出/私有数据清理、有限删除回执。
- `test_security_recovery.py`：完成步骤崩溃后仅一次外部调用、语义只修一次且人工入口可用、预算耗尽保留已得结果、metadata_only禁止Extract、SSE/下载/统计隔离、管理员无私人简历入口。
- 单元测试：三态/约束强度、词边界、闰年日历月、否定风险、私网URL及DNS、薪资精度、CSV公式、角色/数字/错误声明引用、显式复习时钟、模型不能自我确认或伪装本人补充。
- Provider契约使用 respx 固定HTTP响应：空choices/null/refusal/截断/非法JSON、部分Extract失败、429/5xx/4xx重试分类、usage缺失、外部指令只作数据且无tools。

F01–F12、A01–A36的逐项映射在 progress.md。离线契约与合成注入测试不证明真实模型始终服从；事实与权限仍由服务端规则控制，真实质量必须人工抽查。

## 三条 E2E 与响应式

E1：浏览器登录、简历解析/确认、保存搜索条件/搜索、刷新恢复、岗位校对、加入申请、本人确认实际投递，创建新资料后旧 submission 仍绑定旧资料。重复合并与撤销的数据库断言在 test_matrix 中补足。

E2：浏览器打开外部进度链接前后状态与查询时间不变；本人记录查询无变化；直接增加技术面、改期、今日待办；记录完成待结果、实际反馈与个人推测分别展示。下一轮准备通过同一轮次/基准 API 支持，未对真实公司操作。

E3：训练生成、来源类别、采用、逐题作答与反馈、薄弱点/复习、口头Offer/比较、删除简历并确认题目404。模型/搜索均为明确 demo Provider，Web/API/PG/Worker未mock。

额外浏览器流程在390/768/1440px访问今日、找岗、岗位库、申请、练习、资料、复盘共21张全页截图，并断言无页面水平溢出。390px下实际退出清空缓存、localStorage为空、访问私密路由转登录。截图在 `docs/screenshots/`，关闭截图动画避免标签入场过程影响可读性；人工抽查移动岗位页与桌面今日页。另有最终 Compose 浏览器完整冒烟截图 compose-smoke.png 与 compose-evidence.json：实际经 Caddy 登录、无模型保存简历、授权后入队，由独立 Worker 持久化岗位。截图使用合成随机账户，没有真实个人资料。

## 已修复问题

| 发现 | 修复与复核 |
| --- | --- |
| 无外部ID的同来源URL被误当同岗 | 非空ID且有证据才参与身份匹配，URL独立比较；新增三城市隔离与别名测试 |
| 动态ORM注册被lint删除造成迁移遗漏 | 显式静态模型导出；空库逐阶段升级并检查领域表及schema漂移 |
| SSE/后台租约与删除竞态 | 新fencing token、提交前资料/授权/基准复查；暂停生成→删除→释放响应仍不能发布 |
| 人工字段修改被模型边界规则误拒绝 | 独立user_review校验，修改来源记user_asserted；保留conflict/missing，新增回归 |
| 事实降低状态后旧版本仍可用 | 全局FactRevocation，旧版本confirmed_facts也剔除；新增回归 |
| Browser与JSDOM客户端初始化失败/Mock fetch不可替换 | 基于window.origin统一客户端，动态fetch边界；实际登录失败组件与E2E通过 |
| 只读Query快照与重复点击竞态 | 显式clone表单、动作互斥与错误提示；校对完成后才能加入申请 |
| pnpm11构建许可/镜像依赖层失败 | allowBuilds替代被忽略配置；冻结安装/构建缓存分层，实际镜像构建成功 |
| 移动端退出入口被布局隐藏 | 在移动header补齐退出入口，并在390px实际退出验证；截图关闭动画 |
| 最后新增表单字段的TS默认值与Python变量类型冲突 | 按生成契约补齐字段、独立变量名；最终完整make verify重跑通过 |

## 未执行与局限

1. 真实国内关键词搜索、相关JD正文、第二来源可用性、真实面经/无面经实测、真实题单与反馈、UI人工来源/事实抽查，均 **blocked_external**。没有生成伪造的 live-evidence.json。
2. 合成样本28条JD与3份简历按模板分组；FixtureProvider有意覆盖边界，不是实际LLM准确率评测。无第三方网络请求进入离线测试。
3. 没有执行真实投递、发送邮件、招聘网站登录、购买服务或公网部署。外链E2E仅打开example.com并关闭，没有任何投递动作。
4. 迁移升级哨兵验证基础/身份数据保留和最终领域schema；不等于大规模生产备份恢复演练。备份未配置。
5. UI主要页面已检查，Element Plus分块较大；个人规模的岗位排名在服务端内存完成。跨年真实转载与来源覆盖仍需真实样本，不能把合成验证泛化。

下一步按 source-feasibility.md 配置隔离验收库与密钥、核对来源策略，再显式运行 make test-live，保留实际usage/run/model/来源时间与人工审查结果。
