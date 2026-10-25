# 真实服务验证报告

当前找岗逻辑已升级到统一招聘卡片与粗略预测难度，Prompt2026-10-23.6、迁移0010；最新真实搜索/整理和完整回归见 [discovery-update.md](discovery-update.md)。下文保留较早的Prompt.3业务验收记录，各次范围分别核对。

2026-10-23，用户明确授权配置凭据并执行真实服务验证。本报告不含密钥、Cookie或真实求职者资料。

## 配置与运行

密钥写入项目根.env，权限0600，.gitignore和Docker构建上下文排除该文件。当前APP_MODE=live、模型deepseek-flash、Prompt2026-10-23.3。正常入口仍为http://localhost:8081，原数据库与账户保留；.env设置COMPOSE_PROJECT_NAME=offerpilot-acceptance、WEB_PORT=8081，因此make up/down现在直接管理原项目。

API、Worker加载服务端环境变量，浏览器不接收密钥。原合成记录保留，不会因模式切换被当成真实机会。用户的真实资料处理授权仍须本人在界面确认。

## 实际结果

| 验证 | 结果 |
| --- | --- |
| 8081 API readiness / capabilities | ready，live，model_available/search_available均true |
| DeepSeek真实JSON API | passed；请求与响应model均deepseek-flash；实际usage可查 |
| Tavily真实Search | passed；返回候选与usage，未用FixtureProvider |
| Tavily真实Extract | passed；官方文档4599字符；招聘页面限制另列 |
| 独立API/PG/Worker的真实搜索队列 | succeeded；3条线索，不伪造正文 |
| 合成简历经真实模型抽取 | succeeded；逐字段核对已知原句后以验收账号显式确认 |
| 合成多行JD经真实模型抽取 | succeeded；段落证据由后端验证，不跳过校验 |
| 真实模型生成5道题并采用 | succeeded；全部generated_for_target，无面经正文时明确降级 |
| 保存合成回答、真实模型反馈 | succeeded；回答和反馈持久化 |
| 真实模型材料准备 | succeeded；claims受已确认事实与原文约束 |
| 浏览器打开真实模式与实际题单 | passed；5题可读、来源标识与限制可见 |
| 修复后完整make verify | 退出0；后端94、前端3、浏览器4；构建/契约检查通过 |

上述成功的最终隔离业务流程共7条Provider调用：5次LLM，返回input_tokens=11861、output_tokens=5799；2次Tavily搜索返回credits合计2.0。这不包含连接探针、来源可读性探针和首次失败排查；不是费用承诺。完整实际记录见live-usage.json。

运行ID：

- search: 69a85582-75c0-4441-bada-28047f59face，succeeded，Prompt 2026-10-23.3
- resume_parse: a0b473b1-e6b9-46a3-9f67-1f424df29864，succeeded，Prompt 2026-10-23.3
- job_import: 374eb542-d021-4146-aded-941ee033b5a9，succeeded，Prompt 2026-10-23.3
- study: 1d4b7a70-aaa2-4cfe-8d6c-e22191f2238e，succeeded，Prompt 2026-10-23.3
- feedback: c908187b-3d73-4853-ac59-9855fb5dc740，succeeded，Prompt 2026-10-23.3
- material_prepare: a8900d29-2f76-46de-95e3-e27fc0d6934c，succeeded，Prompt 2026-10-23.3

## 发现与修复

首次真实多行JD抽取时，模型把不同段落的引文都标p1，后端拒绝并以model_semantic_invalid终止；原始失败状态保存在live-first-failure.json，没有改成成功。

修复为：输入显式传入与后端相同的pN→原文映射；按任务补充学历、日历月、UUID、来源和事实引用规则；一次语义修正传有限字段路径/错误码。映射及系统规则计入步骤哈希/预算，Prompt升级到2026-10-23.3。新增Provider契约回归验证段落映射。没有关闭或放宽证据校验。

修复后重新构建同一API/Worker镜像，完整离线回归及上述真实流程全部重新执行通过。不是只重放旧产物。

## 隔离与局限

业务测试使用独立Compose项目offerpilot-live-validation、8082和独立PG卷；不把测试账号/简历/题单写入用户8081数据库。合成验收账号凭据只在.local/live-access.json(0600)，不写公开报告。完成后关闭该临时栈并保留其卷供复查，用户8081继续运行。

核心服务正常不等于所有招聘站正文正常。字节样本无正文、华为目录不算JD、牛客检索未得到相关面经；详见source-feasibility.md。国内真实相关完整JD及真实面经引用验收仍未完成，不能宣称完整P0真实验收通过。

截图：screenshots/live-mode.png、screenshots/live-study.png。原始成功证据：provider-live-health.json、live-stack-evidence.json、live-usage.json；离线回归：verification-live-fix.log/json。仅使用已知合成个人输入，没有真实投递、发邮件或外部联系。
