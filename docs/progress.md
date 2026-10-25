# OfferPilot 实施进度

2026-10-23。已完整读取工程总提示词与业务 v2。初始目录只有四份方案，未发现适用 AGENTS.md；单一实现流程，无并行 Agent、无公网发布、无真实投递。

**离线验证完成；核心Provider与合成业务的Live冒烟已通过，统一招聘卡片已增加并实测，国内真实JD/面经正文完整验收仍待完成。** offline_verified 表示此处列出的合成/故障/数据库/浏览器证据通过，不等于真实 Provider、来源授权或模型质量验收通过。live_verified仅指对应已执行的真实调用范围，不代表所有招聘来源或真实个人事实质量。最新找岗优化见 [discovery-update.md](discovery-update.md)。

## 阶段

| 阶段 | 实现与离线状态 | 阶段验证证据 | 剩余 |
| --- | --- | --- | --- |
| S0 | offline_verified | 实际 Web→API→PG17、真实迁移、锁文件、Provider 契约、镜像构建 | 真实API已测；目标来源存在不可读/目录页 |
| S1 | offline_verified | 身份隔离、简历/事实不可变版本、手工 JD、字段校对、确定性规则 | 真实模型合成抽取通过；真实用户资料未使用 |
| S2 | offline_verified | 搜索确认、候选、去重/撤销、SSE 补发、取消/预算、租约/旧写入保护 | 真实搜索通过；国内相关JD正文完整链路仍待完成 |
| S3 | offline_verified | 投递快照、查询无变化、轮次改期、材料批准/基准、任务；E1/E2 | 真实用户外部提交由本人完成 |
| S4 | offline_verified | 来源降级、题单采用、回答/反馈、复习、复盘；E3 | 真实题单/反馈与合成事实抽查通过；面经正文引用待完成 |
| S5 | offline_verified | Offer、统计、运营、导出、删除竞态、回执、响应式；E3 | 第三方保留/来源依据由部署者核对 |
| S6 | offline_verified | make bootstrap / verify、空库与逐阶段升级、Docker/Caddy、21张截图、交接文档 | 核心Live通过；国内JD/面经正文样本受限 |

每阶段均先完成可运行后端/前端纵向链路与测试，再扩展下一阶段。最终检查汇总及修复见 test-report.md。

## 功能矩阵

| 功能 | 实现与离线状态 | 界面与证据 | Live |
| --- | --- | --- | --- |
| F01 账号与偏好 | offline_verified | /login /profile；test_s1、test_event_boundaries、E1 | 不依赖云端 |
| F02 简历事实 | offline_verified | /profile；解析/仅存文本、逐条确认/计划/撤回、新版本；test_s1/test_facts | live_verified：真实模型+已知合成输入，非准确率评测 |
| F03 联网找岗 | offline_verified | /discover；自然语言、统一卡片/原文依据/预测难度、筛选、旧结果重整、保存意向、取消/恢复；test_opportunities/test_opportunity_rules、E1/E4 | 真实Search与卡片整理 live_verified；国内完整JD正文待完成 |
| F04 岗位库 | offline_verified | /jobs /jobs/:id；字段证据、版本、筛选、意向、比较、重复撤销；test_matrix | 已测来源受限，覆盖不作保证 |
| F05 条件匹配 | offline_verified | 岗位详情；pass/fail/unknown、理由与引用；test_rules/test_s1 | 规则不依赖模型，真实输入待抽查 |
| F06 申请档案 | offline_verified | /applications /applications/:id；快照/链接/事件/考核；test_s3、E1/E2 | 不代替实际外部操作 |
| F07 材料准备 | offline_verified | 申请详情；生成/编辑/人工降级/审核；test_s3/test_security_recovery | live_verified：合成事实的真实材料生成 |
| F08 面试准备 | offline_verified | /study /study/:id；来源类别、能力图、练习/反馈/复习；test_s4、E3 | 真实题单/反馈 live_verified；真实面经正文引用待完成 |
| F09 任务与日程 | offline_verified | /today；任务/逾期/未来7天、考核/回复期限/复习；test_s3/test_event_boundaries | 站内提醒，不接邮箱 |
| F10 复盘与 Offer | offline_verified | /reviews；实际反馈/推测、统计、口头/书面、比较/决定；test_s5、E2/E3 | 不推断录用结果 |
| F11 基础运营 | offline_verified | /operations；管理员来源/报告处理/汇总，用户可举报；test_security_recovery | blocked_external：真实来源使用依据 |
| F12 数据控制 | offline_verified | /profile；导出/删除预览/进度/回执/撤销授权；test_s5、E3 | 第三方系统删除不作保证 |

## 验收矩阵

下表是离线场景映射；test_*.py 位于 apps/server/tests 的相应 unit/integration/contract 目录。浏览器位于 tests/e2e/flows.spec.ts。没有把代码存在本身计作真实联网证据。

| 验收 | 状态 | 证据与断言 |
| --- | --- | --- |
| A01 | offline_verified | test_identity_versions_isolation、test_cross_owner_run_sse_download_stats_and_links：详情/引用/SSE/导出404，统计隔离 |
| A02 | offline_verified | test_csrf_logout_and_unknown_fields、test_login_origin_wrong_password_and_rate_limit：401/403/429，退出失效 |
| A03 | offline_verified | test_search_confirmation_and_sse、test_queries_do_not_expand_hard_scope：未确认不执行，硬条件保留 |
| A04 | offline_verified | test_search_failures_and_zero 参数化 partial/failed/zero，零结果 succeeded |
| A05 | offline_verified | test_metadata_only_never_extracts、Provider 部分 Extract 失败：只有线索，不造 JD |
| A06 | offline_verified | test_synthetic_samples 28条、test_days_missing_unrestricted_and_negotiable；人工冲突不被批量确认覆盖 |
| A07 | offline_verified | test_job_versions_same_url_and_duplicates_undo：同 URL 新版本且旧版本保留 |
| A08 | offline_verified | 同上合并/撤销；same_board_without_external_id、supported_source_id_keeps_url_aliases：不因空外部 ID 误合并 |
| A09 | offline_verified | test_negation_unknown_company_and_availability、synthetic fixtures：网络未知/明确关闭/截止分离 |
| A10 | offline_verified | 同上：“不收培训费”、未知公司不自动高风险；需付费表达仅提示复核 |
| A11 | offline_verified | test_job_parse_confirm_and_match、test_days_missing_unrestricted_and_negotiable：fail/unknown/pass |
| A12 | offline_verified | test_skill_and_calendar_boundaries、test_csv_formula_and_salary_precision：词边界、闰年、Decimal原单位 |
| A13 | offline_verified | E2：打开外链前后 stage/last_checked_at 不变 |
| A14 | offline_verified | test_submission_snapshot_and_progress_rounds、E1：新资料不覆盖已投材料，未知材料显式标记 |
| A15 | offline_verified | 同上及E2：无变化查询保留阶段，直接技术面与多轮可记录 |
| A16 | offline_verified | test_close_reopen_and_stale_application_events、轮次旧 revision：412，更正/重开追加历史 |
| A17 | offline_verified | test_s3 改期只有一个任务；test_event_boundaries 的 keep/cancel/detach 三种结束选择 |
| A18 | offline_verified | test_prepare_approval_basis_and_idempotency、raw_resume_without_consent_and_revocation_across_versions：计划项剔除，全局撤回旧引用 |
| A19 | offline_verified | test_valid_id_does_not_authorize_wrong_claim 参数化角色/数字/错误经历：有真ID也拒绝错误声明 |
| A20 | offline_verified | test_semantic_repair_only_once_and_manual_path：只两次生成，终止失败，人工入口可保存 |
| A21 | offline_verified | test_prepare_approval_basis_and_idempotency：旧基准批准409；版本/hash/revision在服务原子核验 |
| A22 | offline_verified | test_s3 重复批准/提交、test_s4重复采用、test_idempotency_payload_conflict_and_cancel：副作用唯一，异payload409 |
| A23 | offline_verified | test_lease_fencing_and_capacity、test_completed_step_reused_after_crash：换租约、旧写拒绝、完成步骤仅一次调用 |
| A24 | offline_verified | test_search_confirmation_and_sse 的 seq 补发无重复；E1刷新恢复；组件按seq处理 |
| A25 | offline_verified | test_idempotency_payload_conflict_and_cancel、test_budget_exhaustion_retains_known_results：取消/预算停止且已得结果保留 |
| A26 | offline_verified | test_missing_usage_is_unknown_and_injection_stays_data：恶意文本仍在数据消息，无tools；权限独立由owner约束；不代表真实模型抗注入质量已测 |
| A27 | offline_verified | test_unsafe_urls、test_dns_private_resolution_rejected、metadata_only_never_extracts：私网/scheme/凭据/DNS拒绝 |
| A28 | offline_verified | test_study_source_adoption_answer_feedback_review：无可读面经诚实降级；来源去重/跨年适用性代码与合成元数据，真实样本待测 |
| A29 | offline_verified | test_s4 与 E3：版本、requirement/fact/source 引用及推荐理由；计划事实不得引用 |
| A30 | offline_verified | test_answer_survives_feedback_consent_failure：原文先保存，反馈失败不丢失；真实服务重试待测 |
| A31 | offline_verified | test_study_source_adoption_answer_feedback_review：看答案不改掌握，本人可改评价；E3复习 |
| A32 | offline_verified | E2：明确反馈与个人推测分别展示，未自动推断录用 |
| A33 | offline_verified | test_offer_no_implicit_expiry_or_close、E3：口头标明，期限不硬判，接受不关闭其他申请 |
| A34 | offline_verified | test_delete_race_blocks_old_worker_and_exports、账户回执与E3：暂停生成时删除，不能回写，导出无正文，题目404 |
| A35 | offline_verified | plain-text组件测试、CSV防公式、E2E退出路由与localStorage检查；不解析模型HTML |
| A36 | offline_verified | test_live_never_uses_fixtures、capabilities、make test-live缺凭据非零；demo有明确标识 |

## 关键取舍、限制与续作

- 固定图领域节点内部用持久步骤细分；DB 为恢复来源，无 LangGraph checkpointer。见 decisions/0001-execution.md。
- 自述保守原文引用，关键词覆盖用于解释，不宣称模型理解或能力评分准确率。
- 28条合成 JD、3份简历按模板分组区分开发/评估，两个以上随机隔离账号；fixtures 无真实个人资料，样本不代表真实分布。
- 有限列表/个人规模排名、无公网HTTPS/备份；Element Plus 生产分块较大，见测试报告。删除第三方副本不在本应用保证范围。
- 真实凭据阻碍已解除，.env为0600且排除版本管理。Docker/PG17/浏览器、真实DeepSeek/Tavily及独立Worker流程已验证。剩余为国内目标JD与面经正文的可读样本、来源使用依据核对和真实资料人工审查。
- 最新证据：docs/live-test-report.md、provider-live-health.json、live-stack-evidence.json、live-usage.json、live-source-probe.json。首次真实多行JD失败已保存在live-first-failure.json；修复后94项后端、3项前端、4条E2E与真实核心流程通过。下一步选择可读且允许保存的国内JD/面经样本完成来源验收，不以当前成功调用泛化为全网可用。
