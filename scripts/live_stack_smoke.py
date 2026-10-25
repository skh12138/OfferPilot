"""Real HTTP/API/Worker smoke against the isolated Compose acceptance stack."""
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


async def main():
    access=json.loads(Path('.local/live-access.json').read_text())
    if access['origin'] != 'http://localhost:8082':
        raise SystemExit('Only the isolated 8082 acceptance stack may be tested')
    report={'time':datetime.now(UTC).isoformat(),'mode':'live','input_kind':'explicitly synthetic resume/JD/answer','origin':access['origin'],'username':access['username'],'checks':{},'runs':[],'limitations':[]}
    async with httpx.AsyncClient(base_url=access['origin'],timeout=20) as client:
        async def request(method,path,body=None):
            csrf=(await client.get('/api/v1/auth/csrf')).json()['csrf_token']
            response=await client.request(method,'/api/v1'+path,json=body,headers={'Origin':access['origin'],'X-CSRF-Token':csrf,'Idempotency-Key':str(uuid4())})
            if not response.is_success:
                error=response.json().get('error',{})
                raise RuntimeError(f'{method} {path}: HTTP{response.status_code} {error.get("code")}')
            return response.json()
        async def run(record):
            for _ in range(240):
                current=(await client.get('/api/v1/runs/'+record['id'])).json()
                if current['status'] in {'succeeded','partial','failed','cancelled'}:
                    report['runs'].append({k:current.get(k) for k in ['id','kind','status','error_code','model','prompt_version','result']})
                    print('run',current['kind'],current['status'],current.get('error_code'),flush=True)
                    return current
                await asyncio.sleep(1)
            raise RuntimeError('Bounded acceptance wait expired')
        try:
            await request('POST','/auth/login',{'username':access['username'],'password':access['password']})
            cap=(await client.get('/api/v1/capabilities')).json()
            assert cap['mode']=='live' and cap['model_available'] and cap['search_available']
            report['checks']['login_and_live_capabilities']='passed'
            await request('POST','/me/model-consent',{'granted':True})
            spec=await request('POST','/search-specs',{'keywords':'Python 应用开发实习','cities':['杭州'],'confirmed':True,'max_queries':1,'max_results':3,'max_extracts':1})
            searched=await run(await request('POST','/search-runs',{'spec_id':spec['id']}))
            report['checks']['real_search_queue']='passed' if searched['status']=='succeeded' else 'failed'
            report['limitations'].append('Unknown recruitment domains remain metadata_only; search summaries are not complete JDs.')
            text='使用 Python 完成合成 API 原型。'
            parsed=await run(await request('POST','/resume-versions',{'title':'真实模型验收专用合成简历','text':text}))
            assert parsed['status']=='succeeded','Resume parsing failed'
            profile=(await client.get('/api/v1/profiles/current')).json()['current']
            assert profile['facts'],'Model returned no facts for the supplied synthetic sentence'
            assert all(f['text']==text and f['evidence']['quote']==text for f in profile['facts']),'Model fact differs from the known synthetic sentence'
            for fact in profile['facts']:fact['status']='user_confirmed'
            profile=await request('POST','/profile-versions',{k:profile[k] for k in ['resume_version_id','preferences','facts']}|{'reason':'验收脚本核对已知合成句子；不代替真实用户确认'})
            report['checks']['real_resume_parse_and_known_fact_confirmation']='passed'
            imported=await run(await request('POST','/job-imports',{'text':'合成验收岗位：Python API 开发实习生\n公司：合成验收公司\n地点：杭州\n职责：参与 Python API 开发、异常处理和接口测试。\n要求：了解 Python、SQL 和 HTTP；本科在读；每周至少3天，至少持续3个月。\n这是合成技术验收JD，不是真实招聘机会。'}))
            assert imported['status']=='succeeded' and imported['result']['job_ids'],'Job extraction failed'
            job=(await client.get('/api/v1/jobs/'+imported['result']['job_ids'][0])).json()
            report['checks']['real_model_synthetic_jd_parse']='passed'
            application=await request('POST','/applications',{'title':job['current']['data']['title'],'company':'合成验收公司','job_version_id':job['current_version_id'],'profile_version_id':profile['id']})
            study=await run(await request('POST','/study-package-runs',{'application_id':application['id'],'count':5,'include_interview_search':True}))
            assert study['status']=='succeeded','Study generation failed'
            package=(await client.get('/api/v1/study-packages/'+study['result']['study_package_id'])).json()
            version=package['current']
            assert len(version['questions'])==5 and all(q['source_kind']!='experience_reported' for q in version['questions'])
            await request('POST','/study-packages/'+package['id']+'/adopt',{'expected_revision':package['revision'],'version_id':version['id'],'payload_hash':version['payload_hash'],'basis_revision':version['basis_revision']})
            report['checks']['real_study_and_honest_no_source_fallback']='passed'
            attempt=await request('POST','/questions/'+version['questions'][0]['id']+'/attempts',{'answer':'合成回答：先说明HTTP请求的输入输出；异常区分业务错误和系统错误，使用事务和幂等键避免重复写入；编写正常、错误和超时场景测试。'})
            assert attempt['feedback_run_id'],'Feedback not queued'
            evaluated=await run({'id':attempt['feedback_run_id']})
            feedback=(await client.get('/api/v1/attempts/'+attempt['id']+'/feedback')).json()['items']
            assert evaluated['status']=='succeeded' and feedback,'Real feedback failed'
            report['checks']['real_answer_persisted_and_feedback']='passed'
            material=await run(await request('POST','/applications/'+application['id']+'/preparation-runs',{'expected_revision':application['revision']}))
            report['checks']['real_preparation']='passed' if material['status']=='succeeded' else 'failed'
            report['study_package_id']=package['id']
        except Exception as exc:
            report['failure']={'type':type(exc).__name__,'message':str(exc)}
            print('Acceptance failure:',type(exc).__name__,str(exc),flush=True)
    report['completed_at']=datetime.now(UTC).isoformat()
    Path('docs/live-stack-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Real stack evidence saved without credentials',flush=True)
    if report.get('failure') or 'failed' in report['checks'].values():
        raise SystemExit(1)


if __name__=='__main__':
    asyncio.run(main())
