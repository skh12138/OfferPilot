# OfferPilot UI 改造验收

日期：2026-10-24。依据用户附件（与根目录06提示词一致），实现B暖白墨绿配色与宋体主标题、A扁平列表/细分隔/列表加预览。U0–U5已完成，最终检查及发布记录见文末。此文记录真实执行范围，不将隔离demo结果作为联网招聘效果证明。

## 交付范围

全部既有路由保留：找岗位、岗位库/详情、今日、申请列表/详情、面试准备/逐题练习、资料、复盘/Offer、登录、来源运营。具体原字段、权限、入口和新位置见[inventory.md](inventory.md)。

- **全局**：统一侧栏、顶部栏、小屏导航、图标、焦点与状态；Element Plus表单、选择器、日期、标签、弹窗、抽屉统一。真实/live与隔离demo标志仍来自原capabilities接口。
- **找岗/岗位**：紧凑输入、IME组合保护、筛选/排序query、来源状态和预测的平面行式列表；桌面双栏、小屏预览抽屉；默认阅读、显式校对；意向、导入CSV/文本、去重、比较、来源/证据与历史原能力保留。预览复用已获取的DTO。
- **申请/今日**：真实七阶段分组看板，明确“已加载”局部计数；无拖拽推进。外链、无变化核对、阶段记录、实际投递分别保留。补录、任务创建、轮次与投递表单进入命名抽屉；今日/逾期/未来组按ID去重，日期用Asia/Shanghai。
- **训练**：一次挂载当前题，目录显示真实回答加载状态；按题/题单版本/用户隔离内存草稿。原采用确认、版本/hash/基准边界、来源、指导、历史、反馈和举报保留。反馈重试复用已保存回答。
- **资料/复盘/运营**：资料分为偏好、简历事实、版本、授权数据控制；默认阅读，编辑保留四种事实状态与全部隐藏事实。Offer/复盘分开，实际反馈与个人推测分开；比较不换算薪资、不排名。管理员接口仅在管理员权限下启用。

主题入口：[tokens.scss](../../apps/web/src/styles/tokens.scss)、[element-theme.scss](../../apps/web/src/styles/element-theme.scss)、[main.scss](../../apps/web/src/styles/main.scss)、[discovery.scss](../../apps/web/src/styles/discovery.scss)。共享实现：[App.vue](../../apps/web/src/app/App.vue)、[ui.ts](../../apps/web/src/app/ui.ts)、[navigation.ts](../../apps/web/src/app/navigation.ts)、[PageHeader.vue](../../apps/web/src/components/PageHeader.vue)、[AsyncState.vue](../../apps/web/src/components/AsyncState.vue)、[SplitPreview.vue](../../apps/web/src/components/SplitPreview.vue)、[DraftDrawer.vue](../../apps/web/src/components/DraftDrawer.vue)、[RunStatus.vue](../../apps/web/src/components/RunStatus.vue)、[JobReading.vue](../../apps/web/src/features/jobs/JobReading.vue)。

## 业务与数据边界

改造前保存179个源码/契约/构建配置校验值及前端归档，见[baseline](baseline/)。保护范围核对见[boundary-check.json](boundary-check.json)：后端源码、迁移、提示词、OpenAPI、生成类型、依赖与锁文件保持基线。没有新增后端接口或业务状态。

原CSRF、权限、幂等头、expected_revision、payload_hash、basis_revision继续使用。打开原站不记录投递；确认实际投递仍保存实际使用的旧资料/材料版本；生成与采用题单分别确认；公开搜索授权与简历/回答模型处理授权独立；删除影响预览、最终确认和清理回执保留。

Pinia仅保存本次会话的可编辑草稿、列表位置等UI状态，服务端数据继续交给Vue Query。退出/账号切换/会话失效清理；未提交草稿不写localStorage，刷新会丢失并已在界面提示。后台refetch与revision冲突不覆盖脏输入。

## 执行环境和基线

沿用本地Node24、pnpm11.25、Python3.12与现有锁文件。原`make verify`基线通过：106个后端测试、4个前端测试、5个E2E，以及构建/契约检查。

浏览器测试由原`scripts/e2e.py`启动独立demo API(8011)/Worker/Vite(5179)，数据库`offerpilot_test_e2e`，PG端口55432。脚本校验测试库名；截图fixture另校验APP_MODE=demo和测试库前缀。合成记录包含四个导入岗位、七阶段申请、任务、五题训练包、复盘及六条招聘机会。账号通过测试API创建；附加候选和管理员权限只写测试库。`.local/ui-fixture.json`为0600，不属于交付数据/截图内容。

同一个fixture用于before/after的13个路由视图×390/768/1440，改造前39张。其他业务用例使用独立合成用户。运营汇总属于整个测试库，随重复回归增长，不能将前后总量变化理解为产品统计变化。

## 功能回归映射

| 需求 | 实际检查 |
|---|---|
| UX01 筛选/返回 | q、游标、选中、比较、run query与返回滚动断言；原E4改为刷新保留难度的明确新预期 |
| UX02 IME/防抖/乱序 | 组合期间0次查询，结束后防抖；800ms旧响应与20ms新响应不覆盖新结果 |
| UX03 行内操作 | 比较与预览独立，预览不写业务；原站外链行为见E2 |
| UX04 运行恢复 | running/partial为隔离拦截响应；刷新仍显示已有结果，0次自动POST搜索，失败原因/重试可见 |
| UX05 refetch/冲突 | 隔离412冲突后保留输入，读取最新不覆盖；放弃需明确确认 |
| UX06 草稿/失败 | 隔离503保存失败输入保留；Esc继续编辑/保留关闭、重新打开及焦点恢复 |
| UX07 切题/反馈 | A/B草稿独立；初始仅当前题1次回答历史GET；撤销授权使反馈未完成，再授权只重试同一条回答 |
| UX08 进度边界 | 原E2：外链不改stage/last_checked_at，无变化查询与考核/改期、任务、复盘实测 |
| UX09 业务确认 | 原E1/E3/E4保留真实投递勾选、旧版本快照、采用、授权、Offer、删除清理断言 |
| UX10 看板 | 七阶段各列与API同一批数据逐项比数量，局部计数、刷新视图、无拖拽/无业务写入 |
| UX11 用户隔离 | 退出清缓存/草稿，新账号不见旧输入，localStorage为空；普通用户0次admin请求 |
| UX12 键盘/焦点 | Space勾选、Enter打开、Esc脏表单保护、抽屉/导航关闭后的触发器焦点 |
| UX13 异常 | 加载、真实无筛选结果、网络503及恢复、运行partial、无权限；模拟态文件明确命名 |
| UX14 响应式 | 全主路由390/768/1440无页面横向溢出，重点浮层桌面/手机截图，CSS200%布局 |

第一轮发现并修复：新建草稿返回原始对象导致输入回弹、宽度变化时Drawer误清选中、重复Esc确认、首屏第三条机会超出900px。定点复验通过后重新执行整套回归。没有删除原有业务断言。

## 视觉与请求检查

已实际打开A/B参考图及生成截图检查，非仅保存文件。列表平面行、来源/待核实文字、宋体主标题、表单正文无衬线、暖白浮层和焦点贯穿主路由。截图目录：[before](screenshots/before/) / [after](screenshots/after/)。全部截图为合成数据。

[visual-checks.json](visual-checks.json)记录Chrome CDP实际使用Songti SC（本机系统字体、非自定义字体）；14组文字/背景及控件对比度断言均达相应4.5:1/3:1。1440×900前三条短机会完整出现。CSS zoom=2布局无页面溢出。动画遵循prefers-reduced-motion；测试截图禁用动画。

筛选使用280ms防抖，旧query结果不会覆盖新条件；预览复用列表DTO。当前题初次回答历史请求断言为1，其他题未访问时如实显示“回答状态未加载”，提示按需读取，题单编辑指导分批最多3并发。页面RunStatus采用Vue Query同key查询、2秒轮询、终态停止；发现候选2.5秒仅运行中刷新，全局近期事项5秒刷新，不再同一页面既建SSE又无限轮询。Offer局部操作仅使相关数据过期。

## 已知限制

1. UI改造未运行`make test-live`，未重新验证真实Tavily/DeepSeek招聘效果、来源可读性和计费服务，界面测试不代表真实联网验收。主服务仍使用原live后端配置。
2. 390/768为Chrome桌面窗口模拟，IME为composition事件回归；真实手机软键盘、安全区、其他操作系统字体和浏览器原生200%缩放仍需设备验收。已测CSS200%与键盘焦点，不将其写作所有物理设备通过。
3. 继续使用系统宋体回退栈；Windows/Linux的实际字体外观取决于安装字体。本次没有下载或引入字体文件/新依赖。
4. 现有接口未提供全库阶段统计/列表下一轮安排等数据；只显示已加载计数，详情继续访问真实考核和任务，不伪造全库统计或下一步。
5. 招聘候选尚无个人意向字段时，仍保留已有“保存申请意向”动作和岗位详情入口，不能凭客户端推断已收藏/已申请。
6. Element Plus既有大chunk仍超过500kB，属于构建警告；记录体积变化，未声称页面实测加速。
7. 内存草稿只保证同次登录和页面切换，整页刷新不能恢复；这与隐私要求一致，界面有说明。

## 最终检查与发布

全部必要命令实际执行：

| 命令 | 结果 | 证据 |
|---|---|---|
| `pnpm --dir apps/web check` | 通过，exit 0，vue-tsc/ESLint/Prettier | [check.log](evidence/check.log) |
| `pnpm --dir apps/web test` | 通过，4个文件/9项，exit 0 | [test.log](evidence/test.log) |
| `pnpm --dir apps/web build` | 通过，exit 0，存在既有Element大chunk警告 | [build.log](evidence/build.log) |
| `PLAYWRIGHT_CHANNEL=chrome make e2e` | 通过，16项，exit 0；5个原流程+9个UX用例+2个视觉用例 | [e2e.log](evidence/e2e.log) |
| `make contract-check` | 通过，exit 0，OpenAPI/生成类型同步且字节未变 | [contract-check.log](evidence/contract-check.log) |
| 最后Offer空值文案后单独复验E3 | 通过，1项，exit 0，含训练/采用/反馈/复习/Offer/删除与缺失值断言 | [e3-final.log](evidence/e3-final.log) |
| `docker compose build web` / `up -d --no-deps web` | 通过，exit 0，仅替换web | [构建](evidence/docker-web-build.log) / [发布](evidence/docker-web-deploy.log) |

初次补拍用例的请求拦截释放时序和重复证据标题定位失败均已修复，并在完整16项检查中通过。截图等待字体/两帧布局稳定、调整视口时清除输入焦点自动滚动，避免截图拼接伪影；浮层按实际视口拍摄。

构建体积（所有产物之和，非首屏下载）：JS 1208.80→1260.29 kB，gzip合计406.83→426.49 kB；CSS 368.60→383.66 kB，gzip 50.07→53.30 kB。路由懒加载继续保留，新增共享分块后JS块19→24；无新字体或依赖。Element chunk仍为917.21 kB / gzip295.77 kB。详[bundle-sizes.json](bundle-sizes.json)，不据此声称实际加载更快。

共132张截图：39张before，93张after，见[清单](screenshots/manifest.json)。实际打开核对了所有主页面的代表性桌面/手机图，以及预览、资料编辑/授权、投递、轮次、反馈、比较、删除、加载、无结果、移动导航和长内容。自动覆盖13个路由视图的390/768/1440无横向溢出。看板和Offer比较仅自身容器可横向滚动。

代表图：[找岗桌面](screenshots/after/discover-1440.png)、[手机速览](screenshots/after/discover-preview-390.png)、[阶段看板](screenshots/after/board-1440.png)、[逐题反馈](screenshots/after/practice-feedback-390.png)、[Offer比较](screenshots/after/offer-comparison-1440.png)、[资料与授权](screenshots/after/profile-privacy-390.png)。

已发布至 **http://localhost:8081**，刷新原浏览器即可。发布仅替换web；API、Worker、DB的容器ID不变，原`offerpilot-acceptance_database`卷身份不变。发布后`/api/v1/health/ready`返回ready，capabilities仍为live；模型/搜索可用标志为配置检查，未进行真实Provider调用。新的入口JS/CSS与本地最终构建逐字节一致，暖白墨绿token已从8081实际返回。详[deployment.json](deployment.json)。

本次无剩余代码阻塞。真实设备、跨系统字体、真实联网效果和既有包体警告的影响已列在上节，未将未执行项标为通过。
