import asyncio
import json
import secrets
from datetime import UTC,datetime
from pathlib import Path
from uuid import UUID,uuid4
from sqlalchemy import select
from offerpilot.infrastructure.db import Session
from offerpilot.modules.identity.models import ModelConsent
from offerpilot.modules.identity.schemas import Credentials
from offerpilot.modules.identity.service import register
from offerpilot.modules.discovery.models import SourcePolicy
from offerpilot.modules.runs.models import AgentRun,ProviderCall
from offerpilot.modules.runs.service import enqueue
from offerpilot.modules.jobs.models import JobVersion
from offerpilot.modules.interview.models import StudyPackageVersion,Question,AnswerAttempt
from offerpilot.worker.main import once


async def run(owner,kind,inputs,profile=None):
    async with Session() as db:
        record=await enqueue(db,owner,kind,inputs,str(uuid4()),profile_id=profile)
        run_id=record.id
    for _ in range(100):
        await once('explicit-live-acceptance')
        async with Session() as db:
            row=await db.get(AgentRun,run_id)
            if row.status in {'succeeded','failed','partial','cancelled'}:return row
    raise RuntimeError('Acceptance worker did not finish')


async def main():
    report={'mode':'live','synthetic_personal_data':True,'time':datetime.now(UTC).isoformat(),'runs':[],'limitations':[]}
    async with Session() as db:
        policies=list(await db.scalars(select(SourcePolicy).where(SourcePolicy.purpose=='jobs')))
        if len(policies)<2:raise SystemExit('至少配置两个国内目标来源策略（含访问/保存依据）；未知来源不会自动提取。')
        login=Credentials(username='live_'+uuid4().hex[:16],password=secrets.token_urlsafe(32))
        user=await register(db,login)
        db.add(ModelConsent(owner_id=user.id,granted=True,version=1))
        await db.commit()
    # Credentials stay in an ignored local file, never in the shareable evidence report.
    access=Path('.local/live-access.json')
    access.parent.mkdir(exist_ok=True)
    import os
    with os.fdopen(os.open(access,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as handle:
        json.dump(login.model_dump(),handle)
    report['username']=user.username
    first=await run(user.id,'search',{'spec':{'keywords':'Python 应用开发实习','cities':['杭州'],'confirmed':True,'max_queries':2,'max_results':4,'max_extracts':3}})
    report['runs'].append({'id':str(first.id),'kind':first.kind,'status':first.status,'result':first.result,'error':first.error_code})
    async with Session() as db:
        job=await db.scalar(select(JobVersion).where(JobVersion.owner_id==user.id).order_by(JobVersion.created_at).limit(1))
    if job:
        # Resume import follows the same model run used by the product.
        from offerpilot.modules.profiles.models import ResumeVersion,ProfileVersion
        async with Session() as db:
            r=ResumeVersion(owner_id=user.id,title='真实验收专用合成简历',text='使用 Python 完成合成 API 原型。')
            db.add(r);await db.flush()
            parse=await enqueue(db,user.id,'resume_parse',{'resume_id':str(r.id)},str(uuid4()),resume_id=r.id)
            await db.commit()
        await once('explicit-live-acceptance')
        async with Session() as db:
            parse=await db.get(AgentRun,parse.id)
            if parse.status!='succeeded':raise RuntimeError('Live resume parse failed; inspect run metadata')
            profile=await db.get(ProfileVersion,UUID(str(parse.result['profile_version_id'])))
            from offerpilot.modules.profiles.schemas import ProfileInput,Fact,Preferences
            from offerpilot.modules.profiles.service import create_version
            facts=[Fact.model_validate(f) for f in profile.facts]
            # The harness may attest only the supplied synthetic sentence, never arbitrary model output.
            if not facts or any(f.text != r.text or f.evidence.quote != r.text or f.evidence.paragraph_id != 'p1' for f in facts):
                raise RuntimeError('Synthetic fact differs from supplied text; human review required before confirmation')
            for fact in facts:fact.status='user_confirmed'
            confirmed=await create_version(db,user.id,ProfileInput(resume_version_id=r.id,preferences=Preferences(),facts=facts,reason='验收脚本核对已知合成原文；不代表真实用户事实审核'))
        report['runs'].append({'id':str(parse.id),'kind':parse.kind,'status':parse.status,'result':parse.result,'error':parse.error_code})
        study=await run(user.id,'study',{'job_version_id':str(job.id),'basis_revision':1,'count':5,'include_interview_search':True},confirmed.id)
        report['runs'].append({'id':str(study.id),'kind':study.kind,'status':study.status,'result':study.result,'error':study.error_code})
        if study.status=='succeeded':
            async with Session() as db:
                version=await db.scalar(select(StudyPackageVersion).where(StudyPackageVersion.package_id==UUID(str(study.result['study_package_id']))))
                question=await db.scalar(select(Question).where(Question.package_version_id==version.id))
                attempt=AnswerAttempt(owner_id=user.id,question_id=question.id,answer='合成回答：先说明幂等键、事务边界，再验证超时后的实际执行结果。')
                db.add(attempt);await db.commit()
            feedback=await run(user.id,'feedback',{'attempt_id':str(attempt.id)},confirmed.id)
            report['runs'].append({'id':str(feedback.id),'kind':feedback.kind,'status':feedback.status,'result':feedback.result,'error':feedback.error_code})
    else:report['limitations'].append('未读取到真实相关 JD 正文；本轮真实找岗验收未通过。')
    async with Session() as db:
        calls=await db.scalars(select(ProviderCall).where(ProviderCall.owner_id==user.id))
        report['calls']=[{'id':str(c.id),'run_id':str(c.run_id),'provider':c.provider,'model':c.model,'response_model':c.response_model,'prompt_version':c.prompt_version,'status':c.status,'usage':c.usage,'error':c.error_code} for c in calls]
    report['limitations'].append('需人工在 UI 打开来源核对 JD/题单/事实；未人工抽查前不得写 live_verified。第二来源与面经可读样本逐项核对。')
    Path('docs/live-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if not job or any(r['status'] != 'succeeded' for r in report['runs']):raise SystemExit('Live evidence recorded; key acceptance still incomplete')
    print('Real calls recorded in docs/live-evidence.json; UI credentials: .local/live-access.json (private). Manual source/claim review remains required.')


if __name__=='__main__':asyncio.run(main())
