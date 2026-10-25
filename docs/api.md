# 实际 API

契约源：`contracts/openapi.json`，当前 API 0.1.0。前端唯一请求客户端由 openapi-fetch + 生成类型支撑。开发查看 `/docs`；部署 Caddy 只公开 `/api/*`，完整 JSON 在交付目录中。

## 通用约定

- Cookie opaque session，HttpOnly/SameSite=Lax，生产 Secure；7 天绝对有效期。先 GET `/api/v1/auth/csrf` 获取 csrf_token，再用相同浏览器 Cookie、精确 `Origin` 和 `X-CSRF-Token` 调用所有写接口，包括登录/注册。
- 成功返回 DTO 本身。输入默认拒绝未知字段。金额 JSON 是 Decimal 字符串；时间点要求含时区，存 UTC；日期单独为 YYYY-MM-DD。UUID 由服务端/合成事实 UUID4 创建，不接受 owner_id。
- 错误统一 `{"error":{"code":"...","message":"...","details":[]},"request_id":"UUID"}`，响应有 X-Request-ID。401 未登录，403 CSRF/Origin/非管理员，404 本人不可读对象，409 业务/幂等/批准冲突，412 revision 过期，422 输入/引用不合法，429 登录限制，503 缺 Provider/迁移。错误不回显正文或密码。
- 分页资源返回 `{items, next_cursor, has_more}`。jobs/applications/tasks 支持 cursor、limit(1–100，默认20)；其他小型历史列表有显式100条上限，无后续 cursor 时 has_more=false。岗位分页按当时本人确定性排名，筛选变化重置 cursor。
- 可变资源用 body.expected_revision，服务端加锁后对比，冲突 412，客户端重新读取再修改。部分 GET 返回 ETag 表达当前 revision，写协议使用 body；不假称所有接口支持 If-Match。
- 需要幂等的长任务、提交、审批、采用、导出、删除及批处理写入必须携带 `Idempotency-Key`。作用域 owner+operation+key，比较 payload_hash。同键同 payload 返回同一结果，同键异 payload 409；普通编辑用 revision 防止覆盖。不能无限缓存用户授权。
- POST resume-versions `parse=true` 返回 RunDTO(202)，`parse=false` 返回已存 ResumeDTO(202)，不请求模型；该联合响应在 OpenAPI 中明确。长操作202代表持久入队，后续读取 run；不是完成提示。

## 运行协议

`GET /runs/{id}` 返回 queued/running/succeeded/partial/failed/cancelled、结果引用、错误和预算。`POST /cancel` 停止后续步骤，已知结果保留；`POST /retry` 只允许终止/失败/部分完成，创建新 run，retry_of 可追踪原运行。

`GET /runs/{id}/events` 返回 text/event-stream，格式 `id: seq` / `event: type` / `data: JSON`。断线携 Last-Event-ID（或 after>=0）补发更大序号；每15秒心跳，每次交付重新检查 owner 和有效会话，终态发送后关闭。客户端按序号去重，可轮询状态兜底。

## 高风险业务写入

实际投递需要 actual_submission_confirmed，未知历史材料必须 missing_materials。外链访问没有写接口副作用。特殊阶段由实际提交/考核/Offer/接受决定驱动，普通事件不能伪造。更正/重开追加历史，不覆盖已有提交快照。

材料 approve / 题单 adopt 校验 expected_revision、version_id、payload_hash、basis_revision、资料可用与事实撤回，再原子写审批与唯一任务；旧内容不能继续使用旧授权。查看答案 guidance 不写掌握，answer attempt 先保存再排反馈，失败保留原文。掌握/复习由本人显式更正。

来源管理 `/admin/*` 明确要求管理员。报告只共享用户勾选授权的 excerpt。删除回执 X-Deletion-Receipt 仅授权删除状态查询与该请求重试，不能访问业务数据。导出 download 必须本人有效会话且未过期。

## 接口清单

以下从已生成 OpenAPI 机械提取；具体字段、枚举、必填和响应 Schema 以 JSON 为准。

| 方法 | 路径 | 操作 | 成功响应 |
| --- | --- | --- | --- |
| GET | `/api/v1/health/live` | Live | 200 |
| GET | `/api/v1/health/ready` | Ready | 200 |
| GET | `/api/v1/capabilities` | Capabilities | 200 |
| GET | `/api/v1/auth/csrf` | Csrf Token | 200 |
| POST | `/api/v1/auth/register` | Register | 201 |
| POST | `/api/v1/auth/login` | Login | 200 |
| GET | `/api/v1/auth/me` | Me | 200 |
| POST | `/api/v1/auth/logout` | Logout | 200 |
| GET | `/api/v1/me/model-consent` | Consent | 200 |
| POST | `/api/v1/me/model-consent` | Change Consent | 200 |
| GET | `/api/v1/profiles/current` | Current | 200 |
| POST | `/api/v1/profile-versions` | Create Version | 201 |
| POST | `/api/v1/profiles/current-selection` | Select Version | 200 |
| GET | `/api/v1/resume-versions` | Resumes | 200 |
| POST | `/api/v1/resume-versions` | Import Resume | 202 |
| GET | `/api/v1/resume-versions/{resume_id}` | Resume | 200 |
| DELETE | `/api/v1/resume-versions/{resume_id}` | Delete Resume | 202 |
| POST | `/api/v1/profile-versions/{profile_id}/revocations` | Revoke | 200 |
| POST | `/api/v1/job-imports` | Import Job | 202 |
| GET | `/api/v1/job-imports/{run_id}` | Import Status | 200 |
| GET | `/api/v1/jobs` | Jobs | 200 |
| GET | `/api/v1/jobs/{job_id}` | Job | 200 |
| POST | `/api/v1/jobs/compare` | Compare | 200 |
| POST | `/api/v1/jobs/{job_id}/versions` | Revise | 201 |
| PUT | `/api/v1/jobs/{job_id}/preference` | Preference | 200 |
| POST | `/api/v1/matches` | Match | 201 |
| GET | `/api/v1/matches/{report_id}` | Report | 200 |
| POST | `/api/v1/jobs/{job_id}/refresh` | Refresh | 202 |
| GET | `/api/v1/runs/{run_id}` | Read Run | 200 |
| POST | `/api/v1/runs/{run_id}/cancel` | Cancel | 200 |
| POST | `/api/v1/runs/{run_id}/retry` | Retry | 202 |
| GET | `/api/v1/runs/{run_id}/events` | Events | 200 |
| GET | `/api/v1/runs` | Runs | 200 |
| POST | `/api/v1/search-specs/parse` | Parse | 202 |
| GET | `/api/v1/search-specs` | Specs | 200 |
| POST | `/api/v1/search-specs` | Create | 201 |
| GET | `/api/v1/search-specs/{spec_id}` | Spec | 200 |
| POST | `/api/v1/search-runs` | Search | 202 |
| POST | `/api/v1/search-runs/natural` | Natural Search | 202 |
| POST | `/api/v1/search-runs/{run_id}/organize` | Organize Existing | 202 |
| GET | `/api/v1/search-runs/{run_id}` | Result | 200 |
| GET | `/api/v1/search-runs/{run_id}/candidates` | Candidates | 200 |
| GET | `/api/v1/duplicate-reviews` | Duplicates | 200 |
| POST | `/api/v1/duplicate-reviews/{review_id}/decision` | Decide | 200 |
| GET | `/api/v1/job-merges` | Merges | 200 |
| POST | `/api/v1/job-merges/{merge_id}/undo` | Undo | 200 |
| POST | `/api/v1/applications` | Create | 201 |
| GET | `/api/v1/applications` | Applications | 200 |
| GET | `/api/v1/applications/{app_id}` | Application | 200 |
| PATCH | `/api/v1/applications/{app_id}` | Patch | 200 |
| GET | `/api/v1/applications/{app_id}/events` | Events | 200 |
| POST | `/api/v1/applications/{app_id}/events` | Event | 200 |
| GET | `/api/v1/applications/{app_id}/submissions` | Submissions | 200 |
| POST | `/api/v1/applications/{app_id}/submissions` | Submit | 201 |
| POST | `/api/v1/applications/{app_id}/progress-checks` | Progress | 200 |
| POST | `/api/v1/applications/{app_id}/preparation-basis` | Basis | 200 |
| GET | `/api/v1/applications/{app_id}/rounds` | Rounds | 200 |
| POST | `/api/v1/applications/{app_id}/rounds` | Add Round | 201 |
| PATCH | `/api/v1/rounds/{round_id}` | Update Round | 200 |
| GET | `/api/v1/tasks` | Tasks | 200 |
| POST | `/api/v1/tasks` | Create | 201 |
| PATCH | `/api/v1/tasks/{task_id}` | Update | 200 |
| GET | `/api/v1/dashboard/today` | Today | 200 |
| POST | `/api/v1/tasks/batch` | Batch | 200 |
| POST | `/api/v1/applications/{app_id}/preparation-runs` | Generate | 202 |
| GET | `/api/v1/applications/{app_id}/preparation-bundles` | Bundles | 200 |
| POST | `/api/v1/applications/{app_id}/preparation-bundles` | Manual Bundle | 201 |
| GET | `/api/v1/preparation-bundles/{bundle_id}` | Bundle | 200 |
| POST | `/api/v1/preparation-bundles/{bundle_id}/versions` | Edit | 201 |
| POST | `/api/v1/preparation-bundles/{bundle_id}/approve` | Approve | 200 |
| POST | `/api/v1/study-package-runs` | Prepare | 202 |
| GET | `/api/v1/study-packages` | Packages | 200 |
| GET | `/api/v1/study-packages/{package_id}` | Package | 200 |
| POST | `/api/v1/study-packages/{package_id}/versions` | Edit | 201 |
| POST | `/api/v1/study-packages/{package_id}/adopt` | Adopt | 200 |
| GET | `/api/v1/questions/{question_id}` | Question | 200 |
| GET | `/api/v1/questions/{question_id}/guidance` | Guidance | 200 |
| POST | `/api/v1/interview-source-runs` | Source Search | 202 |
| GET | `/api/v1/interview-sources` | Sources | 200 |
| POST | `/api/v1/interview-sources` | Manual Source | 201 |
| POST | `/api/v1/questions/{question_id}/attempts` | Answer | 201 |
| GET | `/api/v1/questions/{question_id}/attempts` | Attempts | 200 |
| GET | `/api/v1/attempts/{attempt_id}` | Attempt | 200 |
| GET | `/api/v1/attempts/{attempt_id}/feedback` | Feedback | 200 |
| POST | `/api/v1/attempts/{attempt_id}/feedback-retry` | Retry | 202 |
| GET | `/api/v1/review-items` | Reviews | 200 |
| PATCH | `/api/v1/review-items/{item_id}` | Update | 200 |
| GET | `/api/v1/interview-reviews` | Reviews | 200 |
| POST | `/api/v1/interview-reviews` | Create | 201 |
| GET | `/api/v1/interview-reviews/{review_id}` | Review | 200 |
| PATCH | `/api/v1/interview-reviews/{review_id}` | Update | 200 |
| GET | `/api/v1/offers` | Offers | 200 |
| POST | `/api/v1/offers` | Create | 201 |
| GET | `/api/v1/offers/{offer_id}` | Offer | 200 |
| POST | `/api/v1/offers/{offer_id}/events` | Event | 200 |
| GET | `/api/v1/offers/{offer_id}/events` | Events | 200 |
| POST | `/api/v1/offers/compare` | Compare | 200 |
| POST | `/api/v1/feedback-reports` | Report | 201 |
| GET | `/api/v1/feedback-reports/mine` | Mine | 200 |
| GET | `/api/v1/admin/source-policies` | Policies | 200 |
| POST | `/api/v1/admin/source-policies` | Create Policy | 201 |
| PATCH | `/api/v1/admin/source-policies/{policy_id}` | Update Policy | 200 |
| GET | `/api/v1/admin/feedback-reports` | Reports | 200 |
| POST | `/api/v1/admin/feedback-reports/{report_id}/resolution` | Resolve | 200 |
| GET | `/api/v1/admin/overview` | Operations | 200 |
| GET | `/api/v1/reports/overview` | Overview | 200 |
| GET | `/api/v1/resume-versions/{resume_id}/deletion-preview` | Preview | 200 |
| DELETE | `/api/v1/me` | Delete Account | 202 |
| GET | `/api/v1/deletion-requests/{deletion_id}` | Deletion | 200 |
| POST | `/api/v1/me/exports` | Create Export | 202 |
| GET | `/api/v1/me/exports/{export_id}` | Export Status | 200 |
| GET | `/api/v1/me/exports/{export_id}/download` | Download | 200 |
| POST | `/api/v1/deletion-requests/{deletion_id}/retry` | Retry Deletion | 202 |

共 113 个实际操作；没有占位成功接口。

自然语言找岗：`POST /search-runs/natural` 接受 text、max_queries(默认3，最多6)、max_results(最多8)、max_extracts、public_info_ai_consent，202 返回持久运行。搜索候选的 intelligence 为最新统一卡片：opportunities、basis(job_text/search_excerpt)、prompt_version；difficulty 是明确的模型预测。`POST /search-runs/{id}/organize` 只接受已终止的本人 search，返回新的 search_organize 运行，不重新检索。三个公开搜索入口的 public_info_ai_consent 只覆盖公开条件和公开资料，不授予个人简历模型处理权限。
