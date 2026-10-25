import { expect,type Page,type APIRequestContext } from '@playwright/test';
import type { components } from '../../apps/web/src/api/schema';
export async function api<T>(request:APIRequestContext,path:string,body?:unknown,method='POST'):Promise<T>{
 const c=await request.get('/api/v1/auth/csrf');const csrf=await c.json() as components['schemas']['CSRF'];
 const response=await request.fetch('/api/v1'+path,{method,data:body,headers:{Origin:'http://localhost:5179','X-CSRF-Token':csrf.csrf_token,'Idempotency-Key':crypto.randomUUID()}});
 expect(response.ok(),await response.text()).toBeTruthy();return response.json() as Promise<T>;
}
export async function login(page:Page){
 const name='e2e_'+crypto.randomUUID().replaceAll('-','').slice(0,16);
 await api(page.request,'/auth/register',{username:name,password:'synthetic-password-123'});
 await page.goto('/login');await page.getByLabel('用户名',{exact:true}).fill(name);await page.getByLabel('密码',{exact:true}).fill('synthetic-password-123');await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page).toHaveURL('/jobs');
 await page.goto('/profile');await page.getByRole('tab',{name:'授权与数据控制'}).click();await page.getByRole('button',{name:'同意必要的外部模型处理'}).click();await page.getByRole('tab',{name:'简历与事实'}).click();
 return name;
}
export async function waitRun(page:Page,id:string){
 await expect.poll(async()=>{const r=await page.request.get('/api/v1/runs/'+id);const run=await r.json() as components['schemas']['RunDTO'];if(['failed','partial','cancelled'].includes(run.status))throw new Error(JSON.stringify(run));return run.status;},{timeout:25000}).toBe('succeeded');
 return await (await page.request.get('/api/v1/runs/'+id)).json() as components['schemas']['RunDTO'];
}
export async function importJob(page:Page){
 const run=await api<components['schemas']['RunDTO']>(page.request,'/job-imports',{text:'合成 Python 应用开发实习\n城市：杭州\n每周至少3天，持续3个月\n要求：Python API 异常处理'});
 const done=await waitRun(page,run.id);const ids=done.result.job_ids as string[];
 return await (await page.request.get('/api/v1/jobs/'+ids[0])).json() as components['schemas']['JobDTO'];
}
