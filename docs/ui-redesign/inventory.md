# 功能保留与新位置盘点

以实际源码为准；字段与确认约束继续使用现有DTO、API client及action。以下入口均已保留并落到表内位置，未以主题调整替代功能。

| 页面 | 原有动作/字段/状态 | 改造位置与回归 |
|---|---|---|
| 全局 | 7个用户导航、管理员运营、账户/退出、live/demo、近期运行；CSRF与会话 | 固定侧栏/小屏导航抽屉、56px顶部栏、处理事项；UX04/11/12 |
| /discover | 自然语言、公开授权默认true；示例填入、高级关键词/城市/天数/查询上限/确认；保存/再次搜索；取消/重试；推荐/全部、难度、排序；来源/摘要/正文、AI预测/建议；重整、保存意向、历史 | 紧凑搜索、扁平行、共享速览/小屏Drawer，query保留run/organize；UX01–04/09/14 |
| /jobs | q/意向/资格/风险；文本/CSV/URL导入；最多4项比较；游标；去重决定/理由、保留不同、合并/撤销 | 工具栏、列表与共享岗位阅读预览、导入抽屉、已选操作条、去重展开；UX01–03/05/06 |
| /jobs/:id | 申请、条件匹配、个人意向4状态及理由；标题/公司及6类条件的值/强度/不限/核验；保存新版本、历史、所有来源/别名、段落证据、举报 | 默认阅读，校对明确入口，来源/历史/意向分区；保存保留原revision与草稿；UX05/06/09 |
| /applications | 阶段筛选、列表/board、补录title/company/3URL/navigation_hint、重复约束 | 列表、按既有7阶段真实分组看板、局部已加载计数/游标、补录抽屉；UX01/10 |
| /applications/:id | 6分区；3URL与说明编辑；本人核对无变化；投递时间/实际资料版本/材料缺失/本人确认；阶段advance/correction/reopen/note、理由/结束任务keep/cancel/detach；轮次类型/时间/状态/提醒；准备/手动材料/审核/基准切换；历史 | 顶部操作、紧凑入口与编辑、原6标签(query)、考核行、原确认表单；UX05/06/08/09 |
| /today | 真实4摘要、任务title/due_date/deliverable/acceptance创建；完成/等待/取消；轮次/Offer期限/复习；今日/逾期/未来7天 | 创建抽屉、轻摘要、互斥分组任务行、上海时区日期；UX06/08/14 |
| /study | 岗位/申请/轮次/日期/5–15题生成；训练包草稿/采用；复习topic/mastery/AI建议/next_date与本人3状态 | 已有训练包优先，创建抽屉、复习行；UX09/14 |
| /study/:id | 能力地图、限制、StudyEditor/新版本、采用(version/hash/basis)；每题来源/难度/推荐/举报、按需guidance；回答、历史、反馈、失败重试 | 当前题目+目录，按需挂载，内存答案以user/package/version/question隔离，原采用边界；UX05–07/09/11 |
| /profile | 全部偏好、简历标题/正文/解析与仅存；事实正文/四状态/新fact_id/证据/撤回/补充；新资料版本、历史；个人模型授权/撤销 | 清楚分区、默认阅读/显式编辑，导入与事实校对保留，脏表单不被refetch覆盖；UX05/06/09/11 |
| 数据控制 | JSON/CSV导出/有效期；简历删除影响预览/最终确认/清理状态；账户密码/确认/回执 | 明确数据控制区，原删除回执与异步状态保留；UX09/11 |
| /reviews | 实际问题/回答摘要/明确反馈/个人推测/下一步与申请关联；通知oral/written/本人确认、薪资raw/unit/currency、城市/期限；沟通/接受/拒绝/失效；最多4比较；真实统计 | 复盘/Offer两视图、原表单、局部比较滚动，未知不换算；UX09/14 |
| /operations | 管理员鉴权、真实概览、来源domain/purpose/mode/store_text/store_excerpt/依据/revision、举报处理原因 | 同主题表格和分区；普通用户无管理员入口与数据；UX11/13 |
| /login | username/password/autocomplete、失败、busy、CSRF、返回 | 紧凑同主题；不新增未实现入口；UX11–14 |
| 共享材料/举报 | Bundle草稿/批准与版本基准，ManualMaterial，SubmissionSnapshot；举报kind/id/message/shared_excerpt授权 | 保留已有组件、主题统一、脏关闭与动作错误可见；UX05/06/09 |

不新增通知/收藏/全局搜索、后台筛选、成功率、自动投递或假统计。截图和演示仅为同一隔离合成账号。


验收闭环（2026-10-24）：上述路径均已完成；5个原浏览器流程保留，9个UX用例覆盖UX01–14，另2个视觉用例覆盖主路由三档与重点状态。前端新增5条草稿/日期单元测试，合计9条。异常重试入口覆盖岗位/申请列表与详情、今日、训练、资料、复盘及运营；不会把失败显示为成功。详情见[acceptance.md](acceptance.md)。

回归源码：[原业务流程](../../tests/e2e/flows.spec.ts)、[UX交互](../../tests/e2e/ui-interactions.spec.ts)、[视觉与状态](../../tests/e2e/ui-visual.spec.ts)、[草稿单元测试](../../apps/web/tests/ui-state.test.ts)。
