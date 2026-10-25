import {test,expect} from '@playwright/test';
import {capture} from './ui-capture';
import {api} from './helpers';
import {getUiFixture} from './ui-fixture';
test.use({reducedMotion:'reduce'});
test('UI 同一合成数据的全页面与三档截图',async({page})=>{test.setTimeout(240000);const fixture=await getUiFixture(page);
 const phase=process.env.UI_CAPTURE==='before'?'before':'after';
 const routes=[['discover',`/discover?run=${fixture.run}`],['jobs','/jobs'],['job-detail',`/jobs/${fixture.jobs[0]}`],['today','/today'],['applications','/applications'],['board','/applications?view=board'],['application-detail',`/applications/${fixture.application}`],['study','/study'],['practice',`/study/${fixture.study}`],['profile','/profile'],['reviews','/reviews'],['operations','/operations']];
 for(const width of [390,768,1440]){
  await page.setViewportSize({width,height:900});
  for(const [name,path] of (process.env.UI_SAMPLE?routes.filter(r=>r[0]==='discover'):routes)){
   await page.goto(path!);await expect(page.locator('h1')).toBeVisible();await expect(page.locator('.el-skeleton')).toHaveCount(0);
   await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:`docs/ui-redesign/screenshots/${phase}/${name}-${width}.png`,fullPage:true,animations:'disabled'});
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),`${name} ${width} overflow`).toBeTruthy();
   if(phase==='after'&&name==='discover'){await page.getByRole('article',{name:/招聘机会：/}).first().getByRole('button',{name:/预览/}).click();await capture(page,'discover-preview',[width]);if(width<1280)await page.keyboard.press('Escape');}
   if(phase==='after'&&name==='jobs'){await page.getByRole('button',{name:'导入文本 / CSV'}).click();await capture(page,'job-import',[width]);await page.keyboard.press('Escape');}
   if(phase==='after'&&name==='profile'){await page.getByRole('button',{name:'编辑资料与事实',exact:true}).click();await capture(page,'profile-editor',[width]);}
  }
 }
 await api(page.request,'/auth/logout');await page.goto('/login');
 for(const width of [390,768,1440]){await page.setViewportSize({width,height:900});await page.screenshot({path:`docs/ui-redesign/screenshots/${phase}/login-${width}.png`,fullPage:true,animations:'disabled'});}
});


test('UI 补充空态、加载、比较、证据、编辑与长内容',async({page})=>{
 test.setTimeout(180000);const f=await getUiFixture(page);
 let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve;});
 const jobList=/\/api\/v1\/jobs(\?|$)/;
 await page.route(jobList,async route=>{await gate;await route.continue();});
 await page.goto('/jobs?q=合成加载态');await expect(page.locator('.loading-state')).toBeVisible();
 await capture(page,'jobs-loading-simulated');release();await page.unrouteAll({behavior:'wait'});
 await expect(page.locator('.el-skeleton')).toHaveCount(0);
 await page.goto('/jobs?q=合成不存在的岗位');await expect(page.getByRole('article',{name:/岗位：/})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'没有匹配筛选的岗位',exact:true})).toBeVisible();await capture(page,'jobs-no-filter-results');
 await page.goto('/discover?run='+f.run+'&difficulty=unknown');await expect(page.getByText('当前筛选下没有匹配机会',{exact:true})).toBeVisible();await capture(page,'discover-no-filter-results');
 await page.goto('/jobs');const rows=page.getByRole('article',{name:/岗位：/});await expect(rows.first()).toBeVisible();
 await rows.nth(0).getByRole('checkbox',{name:/比较/}).press('Space');await rows.nth(1).getByRole('checkbox',{name:/比较/}).press('Space');
 await page.getByRole('button',{name:'比较 2 / 4',exact:true}).click();await expect(page.getByRole('heading',{name:'岗位比较',exact:true})).toBeVisible();await capture(page,'jobs-comparison');
 await page.goto('/jobs/'+f.jobs[0]);await page.getByRole('button',{name:'校对字段',exact:true}).click();await expect(page.getByRole('textbox',{name:'标题',exact:true})).toBeVisible();await capture(page,'job-edit');
 await page.locator('.preview-content').getByText('用户提供文本',{exact:true}).first().click();await expect(page.locator('.preview-content .evidence').first()).toBeVisible();await capture(page,'job-evidence');
 await page.goto('/today');const taskTags=page.locator('.task-row .el-tag');await expect(taskTags.first()).toContainText('待办');await expect(taskTags.first()).toHaveCSS('visibility','visible');
 await page.setViewportSize({width:390,height:900});await page.getByRole('button',{name:'打开导航',exact:true}).click();await expect(page.getByRole('navigation',{name:'移动导航'})).toBeVisible();await capture(page,'mobile-navigation',[390,768]);await page.keyboard.press('Escape');
 await page.goto('/profile?tab=privacy');await expect(page.getByRole('button',{name:'查看影响并删除这份简历'}).first()).toBeVisible();await capture(page,'profile-privacy');
 const original=await(await page.request.get('/api/v1/jobs/'+f.jobs[0])).json();
 await page.route('**/api/v1/jobs/'+f.jobs[0],route=>route.fulfill({json:{...original,current:{...original.current,data:{...original.current.data,title:'合成长岗位名称：企业级分布式系统开发与接口可靠性测试实习生（跨团队协作与技术文档方向）',company:'合成长公司名称：杭州云杉智能技术与开发研究中心有限公司'}}}}));
 await page.goto('/jobs/'+f.jobs[0]);await expect(page.getByRole('heading',{name:/合成长岗位名称/}).first()).toBeVisible();await capture(page,'job-long-content-simulated');
});
