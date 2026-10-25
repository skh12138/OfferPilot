import { test,expect } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';
import {capture} from './ui-capture';
import { api,login,waitRun,importJob } from './helpers';

test('E1 搜索、校对、申请、实际投递、旧材料保留',async({page})=>{
 await login(page);
 await page.getByRole('button',{name:'导入简历',exact:true}).click();
 await page.getByRole('textbox',{name:'简历文本',exact:true}).fill('使用 Vue3 完成合成任务列表。');
 await page.getByRole('button',{name:'解析并保存新简历'}).click();
 await page.getByRole('button',{name:'编辑资料与事实',exact:true}).click();
 await expect(page.getByLabel('事实正文').first()).toHaveValue('使用 Vue3 完成合成任务列表。');
 await page.getByRole('combobox',{name:'事实状态',exact:true}).press('ArrowDown');await page.getByRole('option',{name:'本人确认做过'}).click();await page.getByRole('button',{name:'保存新的资料版本'}).click();
 await expect.poll(async()=>{const v=await (await page.request.get('/api/v1/profiles/current')).json() as components['schemas']['CurrentDTO'];return v.current?.facts[0]?.status;}).toBe('user_confirmed');
 const p=await (await page.request.get('/api/v1/profiles/current')).json() as components['schemas']['CurrentDTO'];
 await page.goto('/discover');await page.getByLabel('自然语言条件').fill('杭州 Python 应用开发实习');await page.getByRole('button',{name:'AI 找岗位',exact:true}).click();
 await expect(page.getByRole('link',{name:'查看岗位与证据 →'}).first()).toBeVisible();
 await page.reload();await expect(page.getByRole('link',{name:'查看岗位与证据 →'}).first()).toBeVisible();
 await page.getByRole('link',{name:'查看岗位与证据 →'}).first().click();
 await page.getByRole('button',{name:'校对字段',exact:true}).click();await page.getByRole('button',{name:'校对并保存新岗位版本'}).click();await page.getByRole('button',{name:'加入申请档案'}).click();await expect(page).toHaveURL(/\/applications\//);
 await page.getByRole('button',{name:'记录实际投递',exact:true}).click();
 await page.getByText('实际使用的资料版本',{exact:true}).locator('..').getByRole('combobox').press('ArrowDown');await page.getByRole('option').filter({hasText:'人工确认与修改'}).first().click();
 await page.getByRole('checkbox',{name:'我确认已在外部真实提交',exact:true}).press('Space');await capture(page,'submission-confirmation');await page.getByRole('button',{name:'保存投递快照'}).click();
 await expect(page.locator('main').getByText('已投递',{exact:true})).toBeVisible();
 const appId=page.url().split('/applications/')[1]?.split('?')[0];
 await api(page.request,'/profile-versions',{preferences:{days_per_week:5},reason:'合成新版，不替换历史'});
 const submissions=await (await page.request.get('/api/v1/applications/'+appId+'/submissions')).json() as components['schemas']['Page_SubmissionDTO_'];
 expect(submissions.items[0]?.profile_version_id).toBe(p.current?.id);
});

test('E4 自然语言招聘卡片、独立公开信息授权、难度筛选、刷新与保存意向',async({page})=>{
 await login(page);
 await api(page.request,'/me/model-consent',{granted:false});
 await page.goto('/discover');
 await page.getByLabel('自然语言条件').fill('帮我找找杭州开发相关实习');
 await page.getByRole('button',{name:'AI 找岗位',exact:true}).click();
 const card=page.getByRole('article',{name:/招聘机会：/}).first();
 await expect(card).toBeVisible();
 await card.getByRole('button',{name:/预览/}).click();
 const detail=page.locator('.opportunity-card:visible');
 await expect(detail.getByText('AI 预测难度',{exact:true})).toBeVisible();
 await expect(detail.getByRole('heading',{name:'岗位要求',exact:true})).toBeVisible();
 await expect(detail.getByRole('link',{name:/原始来源/})).toHaveAttribute('href',/synthetic/);
 expect((await (await page.request.get('/api/v1/me/model-consent')).json()).granted).toBe(false);
 await page.getByRole('combobox',{name:'预测难度筛选'}).press('ArrowDown');await page.getByRole('option',{name:'偏难',exact:true}).click();
 await expect(page.getByText('当前筛选下没有匹配机会',{exact:true})).toBeVisible();
 // New UI keeps the selected difficulty through refresh.
 await page.reload();await expect(page.getByText('当前筛选下没有匹配机会',{exact:true})).toBeVisible();await page.getByRole('button',{name:'清空筛选',exact:true}).click();await expect(card).toBeVisible();
 for(const width of [390,768,1440]){await page.setViewportSize({width,height:1000});await page.screenshot({path:`docs/screenshots/${width}-discovery-cards.png`,fullPage:true,animations:'disabled'});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();}
 await page.getByRole('button',{name:'重新整理结果',exact:true}).click();
 await expect(page.getByRole('button',{name:'重新整理结果',exact:true})).toBeVisible();
 await detail.getByRole('button',{name:'保存申请意向',exact:true}).click();
 await page.getByRole('button',{name:'保存意向档案',exact:true}).click();
 await expect(page).toHaveURL(/\/applications\//);
 const app=await (await page.request.get('/api/v1/applications/'+page.url().split('/applications/')[1]?.split('?')[0])).json();
 expect(app.stage).toBe('interested');expect(app.job_url).toContain('synthetic');
});

test('E2 外链不推进、无变化查询、直接技术面、改期、待办与复盘',async({page})=>{
 await login(page);
 const app=await api<components['schemas']['ApplicationDTO']>(page.request,'/applications',{title:'合成已有面试',company:'合成E2',progress_url:'https://example.com/careers'});
 await page.goto('/applications/'+app.id);const before=await (await page.request.get('/api/v1/applications/'+app.id)).json() as components['schemas']['ApplicationDTO'];
 const popupPromise=page.waitForEvent('popup');await page.getByRole('link',{name:'打开进度页面 ↗'}).click();const popup=await popupPromise;await popup.close();
 const after=await (await page.request.get('/api/v1/applications/'+app.id)).json() as components['schemas']['ApplicationDTO'];expect(after.stage).toBe(before.stage);expect(after.last_checked_at).toBeNull();
 await page.getByLabel('官网状态').fill('收到面试通知，原系统暂未变化');await page.getByRole('button',{name:'确认已查看，阶段不变'}).click();
 await page.getByRole('button',{name:'新增考核轮次'}).click();await page.getByLabel('轮次名称').fill('技术一面');await page.getByRole('checkbox',{name:'为这轮考核建立站内待办',exact:true}).press('Space');await capture(page,'round-edit');await page.getByRole('button',{name:'保存考核',exact:true}).click();
 await page.getByRole('tab',{name:'考核安排'}).click();await expect(page.getByRole('heading',{name:'1 · 技术一面'})).toBeVisible();await page.getByRole('button',{name:'改期 / 记录结果'}).click();await page.getByRole('button',{name:'保存考核',exact:true}).click();
 await page.goto('/today');await expect(page.getByRole('heading',{name:'技术一面',exact:true})).toBeVisible();
 const rounds=await (await page.request.get('/api/v1/applications/'+app.id+'/rounds')).json() as components['schemas']['Page_RoundDTO_'];const rnd=rounds.items[0];if(!rnd)throw new Error('round missing');
 await api(page.request,'/rounds/'+rnd.id,{name:rnd.name,type:rnd.type,status:'completed_waiting_result',expected_revision:rnd.revision,reason:'本人参加，结果待定'},'PATCH');
 await api(page.request,'/interview-reviews',{application_id:app.id,round_id:rnd.id,questions_asked:'实际问到异常处理',explicit_feedback:'请补充测试边界',user_inference:'个人感觉表达偏慢',next_steps:'再练一次异常恢复'});
 await page.goto('/reviews');await expect(page.getByText('请补充测试边界',{exact:true})).toBeVisible();await expect(page.getByText('个人感觉表达偏慢',{exact:true})).toBeVisible();
});

test('E3 训练、来源、采用、作答反馈、复习、Offer 与资料删除',async({page})=>{
 await login(page);
 const resume=await api<components['schemas']['RunDTO']>(page.request,'/resume-versions',{title:'E3合成简历',text:'使用 Python 完成合成 API 原型。'});await waitRun(page,resume.id);
 const profile=await (await page.request.get('/api/v1/profiles/current')).json() as components['schemas']['CurrentDTO'];const p=profile.current;if(!p)throw new Error('profile missing');
 const confirmed=await api<components['schemas']['ProfileDTO']>(page.request,'/profile-versions',{resume_version_id:p.resume_version_id,preferences:p.preferences,facts:p.facts.map(f=>({...f,status:'user_confirmed'})),reason:'确认合成事实'});
 const job=await importJob(page);const app=await api<components['schemas']['ApplicationDTO']>(page.request,'/applications',{title:job.current?.data.title,company:'合成E3',job_version_id:job.current_version_id,profile_version_id:confirmed.id});
 await page.goto('/study');await page.getByRole('button',{name:'创建短题单',exact:true}).click();await page.getByRole('combobox',{name:'训练目标岗位'}).press('ArrowDown');await page.getByRole('option').filter({hasText:'合成 Python 应用开发实习'}).first().click();await page.getByRole('button',{name:'生成训练包',exact:true}).click();
 await expect(page.getByRole('link',{name:'打开训练包 →'})).toBeVisible();await page.getByRole('link',{name:'打开训练包 →'}).click();
 await expect(page.getByText('基于目标岗位生成',{exact:true}).first()).toBeVisible();await page.getByRole('button',{name:'采用题单并建立复习任务'}).click();await expect(page.getByRole('button',{name:'题单已采用'})).toBeDisabled();
 await page.getByLabel('我的回答',{exact:true}).first().fill('先说明系统边界，再用幂等键、事务和查询验证失败恢复。');await page.getByRole('button',{name:'保存回答并请求反馈'}).first().click();await expect(page.getByText('可改进：请补充失败路径和验证依据').first()).toBeVisible();await capture(page,'practice-feedback');
 await page.goto('/study');await page.getByRole('button',{name:'需复习',exact:true}).first().click();await expect(page.getByText('本人：需复习',{exact:false}).first()).toBeVisible();
 await api(page.request,'/offers',{application_id:app.id,type:'oral',notification_confirmed:true,source:'合成电话通知',salary_raw:'200元/天',salary_unit:'day'});
 await page.goto('/reviews');await page.getByRole('tab',{name:'Offer 记录与比较'}).click();await expect(page.getByText('口头意向',{exact:false}).first()).toBeVisible();await page.getByRole('checkbox',{name:'加入比较',exact:true}).press('Space');await page.getByRole('button',{name:'比较 1 / 4'}).click();await expect(page.getByRole('heading',{name:'并排比较，不做薪资口径换算'})).toBeVisible();await expect(page.locator('.comparison-table').getByText('未提供',{exact:true})).toHaveCount(3);await capture(page,'offer-comparison');
 const packages=await (await page.request.get('/api/v1/study-packages')).json() as components['schemas']['Page_StudyDTO_'];const questionId=packages.items[0]?.current?.questions[0]?.id;
 await page.goto('/profile');await page.getByRole('tab',{name:'授权与数据控制'}).click();await page.getByRole('button',{name:'查看影响并删除这份简历'}).first().click();await capture(page,'delete-preview');await page.getByRole('button',{name:'确认删除并清理衍生内容'}).click();await expect(page.getByText('清理状态：succeeded',{exact:false})).toBeVisible();
 expect((await page.request.get('/api/v1/questions/'+questionId)).status()).toBe(404);
});

test('刷新恢复、退出缓存与 390/768/1440 页面截图',async({page})=>{
 await login(page);await importJob(page);
 for(const width of [390,768,1440]){await page.setViewportSize({width,height:1000});for(const path of ['/today','/discover','/jobs','/applications','/study','/profile','/reviews']){await page.goto(path);await expect(page.locator('h1')).toBeVisible();await page.screenshot({path:`docs/screenshots/${width}-${path.slice(1)}.png`,fullPage:true,animations:"disabled"});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();}}
 await page.setViewportSize({width:390,height:1000});await page.getByRole('button',{name:'退出登录'}).click();await expect(page).toHaveURL('/login');expect(await page.evaluate(()=>localStorage.length)).toBe(0);await page.goto('/profile');await expect(page).toHaveURL('/login');
});
