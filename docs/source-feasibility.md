# 来源可行性与真实验证

2026-10-23（Asia/Shanghai）。密钥已在本机私有.env配置，真实API调用已执行；不再是缺凭据状态。API连通与特定招聘页面可读性分开记录。

| 来源/样本 | 实际结果 | 结论 |
| --- | --- | --- |
| Tavily官方文档 https://docs.tavily.com/ | Extract返回4599字符正文 | Search/Extract鉴权与正文接口正常，不能替代招聘JD验收 |
| jobs.bytedance.com 实习职位 | 搜索返回实际职位链接，抽样移动职位页Extract无正文；桌面定向检索补测仍无可读正文 | 搜索线索可用，相关正文未通过；不造JD、不判断关闭 |
| career.huawei.com/cn/department-list | Extract返回8380字符 | 这是部门/招聘资讯目录，不是单一职位JD，不能将目录规范化为完整岗位 |
| www.nowcoder.com/discuss 定向检索 | 返回结果未命中目标域名 | 无可读相关面经样本；不能声称历史真题引用通过 |
| jobs.smartrecruiters.com/BoschGroup/744000095392835-software-development-intern | 返回1282字符Software Development Intern片段 | 有职位片段，但要求区块不完整、国内相关性未确认；不计国内目标JD完整样本通过 |
| jobs.smartrecruiters.com/VialtoPartners/743999912805409-intern-trainee-shanghai-china- | 高级限定域搜索返回上海实习链接，Extract无正文 | 有线索但正文未通过 |

完整查询、候选URL、返回usage和提取长度见 live-source-probe.json。探针只做有限公开页面技术可读性检查，未自动批准这些站点的长期全文保存；原文不进入公开交付报告。robots.txt使用浏览工具访问未成功，不能把工具不可达当作允许或禁止的证据。

## 当前应用行为

未知来源维持metadata_only，只保存搜索线索。摘要不包装成正文，不会因为能搜索到链接就创建完整JD。管理员可在“来源与运营”按域名/用途核对usage_basis、正文/片段保留策略和官方关联依据；并非填了Key就能读取所有网站。

真实题单与反馈的本次业务验证采用明确标记的合成JD/简历和真实DeepSeek请求。真实面经搜索无可读支持时，5道题均标generated_for_target，并显示“未找到可读且相关的面经正文”；不是企业历史真题。

## 仍待完成

国内相关真实单一JD的正文→模型规范化→UI核对→定制题单完整链路，以及真实面经正文引用样本，尚未完成。后续应选择可读且有使用/保存依据的具体来源，不无限重试受限站点，不绕过登录或验证码，不泛化全网覆盖。第二目标来源的可用性已经实际检查，上表如实保留成功/受限及目录结果。

真实API与合成业务流程证据见 live-test-report.md、provider-live-health.json、live-stack-evidence.json、live-usage.json。模型请求/响应为deepseek-flash，Prompt版本2026-10-23.3；模型别名不代表完全可复现。

官方接口：[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、[Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract)、[DeepSeek JSON](https://api-docs.deepseek.com/guides/json_mode/)、[Chat](https://api-docs.deepseek.com/api/create-chat-completion/)。
