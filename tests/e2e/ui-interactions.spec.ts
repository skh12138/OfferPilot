import {test,expect,type Page} from '@playwright/test';
import fs from 'node:fs/promises';
import {getUiFixture} from './ui-fixture';
import {api,login,importJob,waitRun} from './helpers';
import type {components} from '../../apps/web/src/api/schema';
test.beforeEach(()=>{expect(process.env.APP_MODE).toBe('demo');});
const fixtureLogin=getUiFixture;
async function screenshot(page:Page,name:string){for(const width of [1440,390]){await page.setViewportSize({width,height:900});await page.screenshot({path:`docs/ui-redesign/screenshots/after/${name}-${width}.png`,fullPage:true,animations:'disabled'});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}}

test('UX01/03 筛选、游标、选中、比较与返回滚动；预览没有业务写入',async({page})=>{
 const f=await fixtureLogin(page);await page.setViewportSize({width:1440,height:600});
 const first=await(await page.request.get('/api/v1/jobs?q=合成&limit=1')).json() as components['schemas']['Page_JobDTO_'];
 await page.goto('/jobs?q=合成&run='+f.run+(first.next_cursor?'&cursor='+encodeURIComponent(first.next_cursor):''));
 const rows=page.getByRole('article',{name:/岗位：/});await expect(rows.first()).toBeVisible();
 const writes:string[]=[];page.on('request',r=>{if(r.method()!=='GET'&&r.url().includes('/api/v1/'))writes.push(r.url());});
 await rows.last().getByRole('button',{name:/预览/}).click();const selected=new URL(page.url()).searchParams.get('selected');
 await rows.first().getByRole('checkbox',{name:/比较/}).press('Space');await expect(page.getByLabel('岗位比较选择')).toContainText('已选 1');
 expect(new URL(page.url()).searchParams.get('selected')).toBe(selected);expect(writes).toHaveLength(0);
 await rows.last().getByRole('link').first().scrollIntoViewIfNeeded();const top=await page.evaluate(()=>scrollY);const listUrl=page.url();
 await rows.last().getByRole('link').first().click();await expect(page.getByRole('button',{name:'校对字段',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'← 岗位库',exact:true}).click();await expect(page).toHaveURL(listUrl);await expect(rows.first()).toBeVisible();
 await expect.poll(async()=>Math.abs((await page.evaluate(()=>scrollY))-top)).toBeLessThan(100);
 expect(new URL(page.url()).searchParams.get('run')).toBe(f.run);expect(new URL(page.url()).searchParams.get('q')).toBe('合成');
});

test('UX02 中文组合输入、防抖与较早响应不覆盖较新结果',async({page})=>{
 await fixtureLogin(page);const base=await(await page.request.get('/api/v1/jobs')).json() as components['schemas']['Page_JobDTO_'];const calls:string[]=[];
 await page.route(/\/api\/v1\/jobs(\?|$)/,async route=>{const q=new URL(route.request().url()).searchParams.get('q')??'';if(!['旧','新'].includes(q)){await route.continue();return;}calls.push(q);await new Promise(r=>setTimeout(r,q==='旧'?800:20));const data=structuredClone(base);const item=data.items[0];if(item?.current)item.current.data.title='合成'+q+'响应';data.items=data.items.slice(0,1);try{await route.fulfill({json:data});}catch{/* Superseded requests may be cancelled. */}});
 await page.goto('/jobs');await expect(page.getByRole('article',{name:/岗位：/}).first()).toBeVisible();const input=page.getByRole('textbox',{name:'筛选岗位',exact:true});
 await input.evaluate(el=>el.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true})));await input.fill('旧');await page.waitForTimeout(400);expect(calls).toHaveLength(0);
 await input.evaluate(el=>el.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true})));await expect.poll(()=>calls.includes('旧')).toBe(true);
 await input.fill('新');await expect.poll(()=>calls.includes('新')).toBe(true);await expect(page.getByRole('article',{name:'岗位：合成新响应'})).toBeVisible();await page.waitForTimeout(900);
 await expect(page.getByRole('article',{name:'岗位：合成新响应'})).toBeVisible();await expect(page.getByRole('article',{name:'岗位：合成旧响应'})).toHaveCount(0);
});

test('UX04/13 运行恢复不自动重新搜索，部分完成保留结果且有恢复入口',async({page})=>{
 const f=await fixtureLogin(page);const record=await(await page.request.get('/api/v1/runs/'+f.run)).json() as components['schemas']['RunDTO'];let status='running';let posts=0;
 page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/search-runs'))posts++;});
 await page.route('**/api/v1/runs/'+f.run,route=>route.fulfill({json:{...record,status,error_code:status==='partial'?'content_unavailable':null}}));
 await page.goto('/discover?run='+f.run);await expect(page.getByText('正在处理，已保存的结果会陆续出现。')).toBeVisible();await page.reload();await expect(page.getByRole('article',{name:/招聘机会：/}).first()).toBeVisible();expect(posts).toBe(0);
 await screenshot(page,'discover-running-simulated');status='partial';await expect(page.getByText('部分完成，可用结果已保留；部分来源或步骤未完成，可查看原因后重试。')).toBeVisible();
 await expect(page.getByRole('button',{name:'重试',exact:true})).toBeVisible();await expect(page.getByRole('article',{name:/招聘机会：/}).first()).toBeVisible();expect(posts).toBe(0);await screenshot(page,'discover-partial-simulated');
});

test('UX05 版本冲突和重新读取保留脏字段，放弃需本人决定',async({page})=>{
 await login(page);const job=await importJob(page);await page.goto('/jobs/'+job.id);await page.getByRole('button',{name:'校对字段',exact:true}).click();
 const title=page.getByRole('textbox',{name:'标题',exact:true});await title.fill('合成未保存修改');
 await page.route('**/api/v1/jobs/'+job.id+'/versions',route=>route.fulfill({status:412,json:{error:{code:'revision_conflict',message:'数据已更新，请重新读取并保留草稿后决定'}}}));
 await page.getByRole('button',{name:'校对并保存新岗位版本'}).click();await expect(page.getByText('数据已更新，请重新读取并保留草稿后决定')).toBeVisible();
 await page.getByRole('button',{name:'查看最新岗位版本'}).click();await expect(title).toHaveValue('合成未保存修改');
 await page.getByRole('button',{name:'放弃草稿，载入最新字段'}).click();await page.getByRole('button',{name:'继续编辑',exact:true}).click();await expect(title).toHaveValue('合成未保存修改');
 await page.getByRole('button',{name:'放弃草稿，载入最新字段'}).click();await page.getByRole('button',{name:'放弃草稿并载入',exact:true}).click();await expect(title).toHaveValue(job.current?.data.title??'');
});

test('UX06/12 表单失败不丢草稿，Esc保留/继续编辑与焦点回归',async({page})=>{
 await login(page);await page.setViewportSize({width:390,height:900});await page.goto('/today');const trigger=page.getByRole('button',{name:'新建待办',exact:true});await trigger.click();
 const title=page.getByRole('textbox',{name:'待办标题',exact:true});await title.fill('合成待办草稿');
 await page.route('**/api/v1/tasks',route=>route.request().method()==='POST'?route.fulfill({status:503,json:{error:{message:'合成测试：暂时无法保存，请稍后重试'}}}):route.continue());
 await page.getByRole('button',{name:'保存待办',exact:true}).click();await expect(page.getByText('合成测试：暂时无法保存，请稍后重试')).toBeVisible();await expect(title).toHaveValue('合成待办草稿');await screenshot(page,'today-draft-error-open');
 await page.keyboard.press('Escape');await page.getByRole('button',{name:'继续编辑',exact:true}).click();await expect(page.getByRole('dialog',{name:'保留草稿并关闭？'})).toBeHidden();await expect(title).toBeVisible();
 await page.keyboard.press('Escape');await page.getByRole('button',{name:'保留草稿并关闭',exact:true}).click();await expect(title).not.toBeVisible();await expect(trigger).toBeFocused();
 await trigger.press('Enter');await expect(title).toHaveValue('合成待办草稿');await page.keyboard.press('Escape');await page.getByRole('button',{name:'保留草稿并关闭',exact:true}).click();
 await page.getByRole('button',{name:'打开导航',exact:true}).click();await expect(page.getByRole('navigation',{name:'移动导航'})).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('button',{name:'打开导航',exact:true})).toBeFocused();
 await screenshot(page,'today-draft-error');
});

test('UX07 逐题草稿、回答归属与反馈重试只保留一条回答',async({page})=>{
 await login(page);const job=await importJob(page);const queued=await api<components['schemas']['RunDTO']>(page.request,'/study-package-runs',{job_version_id:job.current_version_id,count:5,include_interview_search:true});const done=await waitRun(page,queued.id);
 let attemptQueries=0;page.on('request',r=>{if(r.method()==='GET'&&/\/questions\/[^/]+\/attempts/.test(r.url()))attemptQueries++;});
 await page.goto('/study/'+String(done.result.study_package_id));const input=page.getByRole('textbox',{name:'我的回答',exact:true});await input.fill('合成回答 A：使用幂等键记录失败重试');expect(attemptQueries).toBe(1);
 await page.getByRole('button',{name:'下一题',exact:true}).click();await input.fill('合成回答 B：说明事务边界');await page.getByRole('button',{name:'上一题',exact:true}).click();await expect(input).toHaveValue('合成回答 A：使用幂等键记录失败重试');
 await api(page.request,'/me/model-consent',{granted:false});await page.getByRole('button',{name:'保存回答并请求反馈'}).click();await expect(page.getByText('回答已保存，反馈未完成，可重试反馈。')).toBeVisible();
 const question=new URL(page.url()).searchParams.get('question');const first=await(await page.request.get('/api/v1/questions/'+question+'/attempts')).json() as components['schemas']['Page_AttemptDTO_'];expect(first.items).toHaveLength(1);
 await api(page.request,'/me/model-consent',{granted:true});await page.getByRole('button',{name:'重试反馈（回答已保存）'}).click();await expect(page.getByText('可改进：请补充失败路径和验证依据')).toBeVisible();
 const after=await(await page.request.get('/api/v1/questions/'+question+'/attempts')).json() as components['schemas']['Page_AttemptDTO_'];expect(after.items).toHaveLength(1);expect(after.items[0]?.id).toBe(first.items[0]?.id);
 await page.getByRole('button',{name:'下一题',exact:true}).click();await expect(input).toHaveValue('合成回答 B：说明事务边界');await expect(page.getByText('可改进：请补充失败路径和验证依据')).toHaveCount(0);await screenshot(page,'practice-current');
});

test('UX10 真实阶段分组、局部计数、视图刷新与无拖拽写入',async({page})=>{
 await fixtureLogin(page);const items=(await(await page.request.get('/api/v1/applications?limit=100')).json() as components['schemas']['Page_ApplicationDTO_']).items;
 let writes=0;page.on('request',r=>{if(r.method()!=='GET'&&r.url().includes('/api/v1/applications'))writes++;});
 await page.goto('/applications?view=board');const labels={interested:'意向',preparing:'准备投递',submitted:'已投递',assessment:'考核中',offer:'Offer 沟通',onboarding:'已接受 / 入职',closed:'已结束'};
 for(const [stage,label] of Object.entries(labels)){const column=page.getByRole('region',{name:label,exact:true});await expect(column).toContainText(`${items.filter(a=>a.stage===stage).length} 条已加载`);expect(await column.locator('[draggable="true"]').count()).toBe(0);}
 await page.reload();await expect(page.getByLabel('申请阶段看板')).toBeVisible();expect(writes).toBe(0);await screenshot(page,'applications-board');
});

test('UX11 用户切换清理草稿与缓存，普通用户不能读取运营数据',async({page})=>{
 await login(page);await page.getByRole('button',{name:'编辑资料与事实',exact:true}).click();await page.getByRole('button',{name:'补充事实',exact:true}).click();await page.getByRole('textbox',{name:'事实正文',exact:true}).fill('合成仅属于旧用户的私密草稿');
 await page.getByRole('button',{name:'退出登录',exact:true}).first().click();await page.getByRole('button',{name:'放弃草稿并退出',exact:true}).click();await expect(page).toHaveURL('/login');
 await login(page);await expect(page.getByText('合成仅属于旧用户的私密草稿')).toHaveCount(0);expect(await page.evaluate(()=>localStorage.length)).toBe(0);
 let adminCalls=0;page.on('request',r=>{if(r.url().includes('/api/v1/admin/'))adminCalls++;});await page.goto('/operations');await expect(page.getByText('此页面仅供管理员使用，你没有来源运营权限。')).toBeVisible();expect(adminCalls).toBe(0);await screenshot(page,'operations-no-permission');
});

test('UX13/14 加载失败恢复、实际主题对比度与200%布局',async({page})=>{
 const f=await fixtureLogin(page);await page.setViewportSize({width:1440,height:900});let broken=true;
 await page.route(/\/api\/v1\/jobs(\?|$)/,route=>broken?route.fulfill({status:503,json:{error:{message:'合成离线状态'}}}):route.continue());
 await page.goto('/jobs');await expect(page.getByRole('heading',{name:'暂时无法加载'})).toBeVisible();await screenshot(page,'jobs-network-error');broken=false;await page.getByRole('button',{name:'重新加载',exact:true}).click();await expect(page.getByRole('article',{name:/岗位：/}).first()).toBeVisible();
 await page.setViewportSize({width:1440,height:900});await page.goto('/discover?run='+f.run);await expect(page.locator('.opportunity-row').nth(2)).toBeVisible();const third=await page.locator('.opportunity-row').nth(2).boundingBox();expect(third&&third.y+third.height).toBeLessThanOrEqual(900);
 const theme=await page.evaluate(()=>{const s=getComputedStyle(document.documentElement);const value=(k:string)=>s.getPropertyValue(k).trim();function lum(hex:string){const c=hex.replace('#','').match(/../g)!.map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4));return c[0]!*.2126+c[1]!*.7152+c[2]!*.0722;}const pairs=[['--op-text-primary','--op-bg-canvas',4.5],['--op-text-secondary','--op-bg-canvas',4.5],['--op-text-secondary','--op-bg-selected',4.5],['--op-text-secondary','--op-bg-sidebar',4.5],['--op-text-secondary','--op-bg-hover',4.5],['--op-text-primary','--op-bg-surface',4.5],['--op-text-placeholder','--op-bg-surface',4.5],['--op-text-on-accent','--op-accent',4.5],['--op-warning-text','--op-warning-bg',4.5],['--op-danger-text','--op-danger-bg',4.5],['--op-info-text','--op-info-bg',4.5],['--op-success-text','--op-success-bg',4.5],['--op-border-control','--op-bg-surface',3],['--op-focus-ring','--op-bg-canvas',3]] as const;return {primary:value('--el-color-primary'),pairs:pairs.map(([fg,bg,min])=>{const a=lum(value(fg)),b=lum(value(bg));return {fg,bg,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),min};})};});
 expect(theme.primary).toBe('#243d35');for(const p of theme.pairs)expect(p.ratio,`${p.fg} on ${p.bg}`).toBeGreaterThanOrEqual(p.min);
 const cdp=await page.context().newCDPSession(page);await cdp.send('DOM.enable');await cdp.send('CSS.enable');const cdpDocument=await cdp.send('DOM.getDocument');const node=await cdp.send('DOM.querySelector',{nodeId:cdpDocument.root.nodeId,selector:'h1'});const fonts=await cdp.send('CSS.getPlatformFontsForNode',{nodeId:node.nodeId});
 await page.evaluate(()=>{document.documentElement.style.zoom='2';});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await expect(page.getByRole('button',{name:'高级条件',exact:true})).toBeVisible();await page.screenshot({path:'docs/ui-redesign/screenshots/after/discover-1440-zoom200.png',fullPage:true,animations:'disabled'});
 await fs.writeFile('docs/ui-redesign/visual-checks.json',JSON.stringify({theme,fonts:fonts.fonts,zoom:'CSS zoom=2 at 1440x900; no horizontal overflow',three_short_rows_visible:true},null,2)+'\n');
});
