from datetime import date
import pytest
from offerpilot.modules.jobs.rules import calendar_months,check_eligibility,skill_tokens,verify
from offerpilot.modules.jobs.schemas import Condition,JobExtraction
from offerpilot.modules.profiles.schemas import Preferences
from offerpilot.modules.discovery.service import search_queries
from offerpilot.modules.discovery.schemas import SpecInput
from offerpilot.providers.urls import canonical_url
from offerpilot.api.errors import DomainError


def test_days_missing_unrestricted_and_negotiable():
    job=JobExtraction(title='合成岗位',conditions={'days_per_week':Condition(value=4,review_status='confirmed')})
    overall,checks=check_eligibility(Preferences(days_per_week=3),job)
    assert overall=='fail' and checks[0].status=='fail'
    job.conditions['days_per_week'].strength='preferred'
    assert check_eligibility(Preferences(days_per_week=3),job)[1][0].status=='pass'
    job.conditions['days_per_week']=Condition(unrestricted=True,review_status='confirmed')
    assert check_eligibility(None,job)[1][0].status=='pass'
    assert check_eligibility(None,JobExtraction(title='缺字段'))[0]=='unknown'


def test_skill_and_calendar_boundaries():
    assert skill_tokens('JavaScript')=={'javascript'}
    assert skill_tokens('PyTorch')=={'pytorch'}
    assert calendar_months(date(2024,1,31),1)==date(2024,2,29)
    assert calendar_months(date(2025,1,31),1)==date(2025,2,28)


def test_negation_unknown_company_and_availability():
    job=JobExtraction(title='合成岗位',company='未知小公司')
    assert verify(job,'本招聘不收取培训费',date(2026,10,23))[:2]==('unknown','no_known_flags')
    assert verify(job,'请先支付3000元培训费',date(2026,10,23))[1]=='high_risk_flag'
    assert verify(job,'网络错误',date(2026,10,23))[0]=='unknown'


@pytest.mark.parametrize('url',['file:///etc/passwd','http://127.0.0.1/x','http://169.254.169.254/','http://localhost/x','https://user:password@example.com/x','https://example.com:8080/x','http://[::1]/x','https://example.com/?token=secret'])
def test_unsafe_urls(url):
    with pytest.raises(DomainError):canonical_url(url)


def test_canonical_preserves_job_id():
    assert canonical_url('https://example.com/job?id=7&utm_source=x#anchor')=='https://example.com/job?id=7'


def test_queries_do_not_expand_hard_scope():
    q=search_queries(SpecInput(keywords='Python',cities=['杭州'],days_per_week=3,max_queries=6))
    assert len(q)==6 and all('杭州' in s and '每周3天' in s for s in q)


async def test_dns_private_resolution_rejected(monkeypatch):
    import asyncio,socket
    from offerpilot.providers.urls import validate_public_dns
    async def private(*args,**kwargs):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))]
    monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',private)
    with pytest.raises(DomainError):await validate_public_dns('https://public-looking.example/job')


def test_csv_formula_and_salary_precision():
    from offerpilot.modules.control.exporting import csv_safe
    from offerpilot.modules.jobs.schemas import Salary
    for value in ['=SUM(1,1)','+command','-command','@command',' \t=1+1']:
        assert csv_safe(value).startswith("'")
    salary=Salary(minimum='200.10',maximum='300.20',unit='day',raw='200.10-300.20元/天')
    assert salary.model_dump(mode='json')['minimum']=='200.10' and salary.unit=='day'
