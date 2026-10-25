import {expect,type Page} from '@playwright/test';
import fs from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {api,waitRun} from './helpers';
import type {components} from '../../apps/web/src/api/schema';
export type Fixture={username:string;password:string;run:string;jobs:string[];application:string;study:string};
export async function getUiFixture(page:Page):Promise<Fixture>{expect(process.env.APP_MODE).toBe('demo');
 let fixture:Fixture|undefined;
 try{fixture=JSON.parse(await fs.readFile('.local/ui-fixture.json','utf8')) as Fixture;}catch{ /* First isolated capture. */ }
 if(fixture){
  const csrf=(await(await page.request.get('/api/v1/auth/csrf')).json()).csrf_token;
  const authenticated=await page.request.post('/api/v1/auth/login',{data:{username:fixture.username,password:fixture.password},headers:{Origin:'http://localhost:5179','X-CSRF-Token':csrf}});
  if(authenticated.ok())return fixture;
  if(authenticated.status()!==401)throw new Error('Synthetic UI login unavailable: '+authenticated.status());
  fixture=undefined;
 }
 if(!fixture){
  const credentials={username:'ui_'+crypto.randomUUID().slice(0,8),password:'synthetic-ui-password-2026'};
  await api(page.request,'/auth/register',credentials);
  const owner=await api<components['schemas']['UserDTO']>(page.request,'/auth/login',credentials);
  await api(page.request,'/me/model-consent',{granted:true});
  const resume=await api<components['schemas']['RunDTO']>(page.request,'/resume-versions',{title:'合成UI验收简历',text:'使用 Python 完成合成接口与测试。'});await waitRun(page,resume.id);
  const profile=(await (await page.request.get('/api/v1/profiles/current')).json() as components['schemas']['CurrentDTO']).current;
  if(!profile)throw new Error('Synthetic profile missing');
  await api(page.request,'/profile-versions',{resume_version_id:profile.resume_version_id,preferences:{cities:['杭州'],days_per_week:3},facts:profile.facts.map(f=>({...f,status:'user_confirmed'})),reason:'本人核对已知合成句子'});
  const jobs:components['schemas']['JobDTO'][]=[];
  for(const title of ['Python 应用开发实习','前端开发实习','后端开发实习','开发测试实习']){
   const r=await api<components['schemas']['RunDTO']>(page.request,'/job-imports',{text:`合成 ${title}\n城市：杭州\n每周至少3天，持续3个月，本科及以上\n职责：参与接口开发与测试\n要求：Python API 异常处理`,url:`https://synthetic.example/ui/${jobs.length}`});
   const result=await waitRun(page,r.id);const id=(result.result.job_ids as string[])[0];if(!id)throw new Error('Job missing');
   jobs.push(await(await page.request.get('/api/v1/jobs/'+id)).json() as components['schemas']['JobDTO']);
  }
  const first=jobs[0];if(!first)throw new Error('No fixture job');
  const applications:components['schemas']['ApplicationDTO'][]=[];
  for(const company of ['合成云杉智能','合成栖光科技','合成北岸科技','合成原野科技','合成青禾数据','合成远山软件','合成拾光科技']){
   applications.push(await api(page.request,'/applications',{title:'应用开发实习生',company,job_version_id:applications.length===0?first.current_version_id:null,progress_url:'https://synthetic.example/progress',job_url:`https://synthetic.example/job/${applications.length}`,navigation_hint:'合成验收入口'}));
  }
  const app=applications[0];if(!app)throw new Error('App missing');
  for(const i of [1,2,3,4,5,6]){
   const a=applications[i];if(!a)continue;
   if(i===1)await api(page.request,`/applications/${a.id}/events`,{expected_revision:a.revision,event_type:'advance',to_stage:'preparing',reason:'本人准备合成材料',source:'本人记录',happened_at:new Date().toISOString(),task_action:'keep'});
   if(i===2)await api(page.request,`/applications/${a.id}/submissions`,{expected_revision:a.revision,actual_submission_confirmed:true,submitted_at:new Date().toISOString(),channel:'合成历史记录',missing_materials:true});
   if(i===3)await api(page.request,`/applications/${a.id}/rounds`,{name:'合成技术一面',type:'technical',status:'scheduled',planned_at:new Date(Date.now()+86400000).toISOString(),reminders_enabled:true});
   if(i===4||i===5){const o=await api<components['schemas']['OfferDTO']>(page.request,'/offers',{application_id:a.id,type:'oral',notification_confirmed:true,source:'本人记录的合成电话通知',salary_raw:'200–300元/天',salary_unit:'day'});if(i===5)await api(page.request,`/offers/${o.id}/events`,{expected_revision:o.revision,decision:'accepted',reason:'本人接受合成通知',user_confirmed:true});}
   if(i===6)await api(page.request,`/applications/${a.id}/events`,{expected_revision:a.revision,event_type:'advance',to_stage:'closed',reason:'本人结束合成申请',close_reason:'本人结束合成申请',source:'本人记录',happened_at:new Date().toISOString(),task_action:'keep'});
  }
  await api(page.request,'/tasks',{title:'整理接口项目与测试案例',kind:'other',deliverable:'一份合成项目说明',acceptance:'正常/失败路径均可解释'});
  await api(page.request,'/interview-reviews',{application_id:app.id,questions_asked:'如何处理接口重试？',explicit_feedback:'请补充幂等与失败恢复的例子',user_inference:'个人认为表达可更清晰',next_steps:'练习说明一次完整失败路径'});
  const searched=await api<components['schemas']['RunDTO']>(page.request,'/search-runs/natural',{text:'杭州开发实习，每周3天',max_queries:1,public_info_ai_consent:true});await waitRun(page,searched.id);
  const packRun=await api<components['schemas']['RunDTO']>(page.request,'/study-package-runs',{job_version_id:first.current_version_id,count:5,include_interview_search:true});const pack=await waitRun(page,packRun.id);
  const study=String(pack.result.study_package_id);
  // Only the dedicated E2E database is seeded; all added records are explicitly synthetic.
  execFileSync('.venv/bin/python',['-c',`
import os,sys,json,uuid,psycopg
from psycopg.types.json import Jsonb
url=os.environ['DATABASE_URL'].replace('postgresql+psycopg','postgresql')
assert url.rsplit('/',1)[-1].startswith('offerpilot_test')
owner,run=sys.argv[1:]
with psycopg.connect(url) as db:
 db.execute('UPDATE users SET is_admin=true WHERE id=%s',(owner,))
 for n,(company,title,level) in enumerate([('合成云杉智能','AI应用开发实习生','medium'),('合成栖光科技','前端开发实习生','easy'),('合成北岸科技','Python后端实习生','medium'),('合成青禾数据','数据开发实习生','hard'),('合成远山软件','软件测试实习生','easy')]):
  cid=str(uuid.uuid4());summary=f'{company}招聘{title}，杭州，本科及以上；每周至少3天；要求Python与接口测试。'
  db.execute('INSERT INTO search_candidates (id,owner_id,created_at,run_id,url,title,summary,query,query_kind,status) VALUES(%s,%s,now(),%s,%s,%s,%s,%s,%s,%s)',(cid,owner,run,f'https://synthetic.example/ui-candidate/{n}',title,summary,'杭州开发实习','user_confirmed','metadata_only'))
  opportunity={'title':title,'company':company,'cities':['杭州'],'salary':None,'education':'本科及以上','attendance':'每周至少3天','requirements':['Python与接口测试'],'responsibilities':[],'relevance':'high','relevance_reason':'合成验收：地点与开发方向一致','difficulty':{'level':level,'reason':'合成预测：依据有限，仅作一般准备参考','preparation':['准备接口开发案例','复习异常与测试边界']}}
  data={'kind':'position','opportunities':[opportunity],'note':'显式合成UI验收记录','basis':'search_excerpt','prompt_version':'synthetic-ui'}
  db.execute('INSERT INTO search_candidate_analyses(id,owner_id,created_at,candidate_id,analysis_run_id,data) VALUES(%s,%s,now(),%s,%s,%s)',(str(uuid.uuid4()),owner,cid,run,Jsonb(data)))
`,owner.id,searched.id],{env:process.env});
  fixture={...credentials,run:searched.id,jobs:jobs.map(j=>j.id),application:app.id,study};
  await fs.mkdir('.local',{recursive:true});await fs.writeFile('.local/ui-fixture.json',JSON.stringify(fixture),{mode:0o600});
 }

return fixture;
}
