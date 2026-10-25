from uuid import uuid4
from offerpilot.modules.discovery.opportunities import CandidateIntelligence, Opportunity, DifficultyPrediction, sanitize, check_scope
from offerpilot.modules.discovery.schemas import SpecInput
from offerpilot.modules.discovery.service import preserve_scope


def test_unsupported_facts_removed_but_predictions_remain_explicit():
    item=CandidateIntelligence(candidate_id=uuid4(),kind='position',opportunities=[Opportunity(title='Python实习生',company='不存在的巨头',cities=['杭州','上海'],salary='50000元/月',education='博士',requirements=['Python','五年经验'],difficulty=DifficultyPrediction(level='hard',reason='粗略预测需要准备算法'))])
    result=sanitize(item,'合成科技在杭州招聘Python实习生，要求了解Python。')
    p=result.opportunities[0]
    assert p.company is None and p.salary is None and p.education is None
    assert p.cities==['杭州'] and p.requirements==['Python']
    assert p.difficulty.level=='hard'


def test_directory_cannot_become_invented_vacancies():
    item=CandidateIntelligence(candidate_id=uuid4(),kind='listing',opportunities=[Opportunity(title='Python实习生',company=None)])
    assert not sanitize(item,'Python实习生招聘信息搜索结果').opportunities
    item.kind='irrelevant'
    assert not sanitize(item,'Python实习生').opportunities


def test_natural_scope_retains_explicit_city_days_and_limits():
    original=SpecInput(keywords='帮我找杭州开发实习，每周3天',max_queries=2,max_extracts=1,confirmed=True,natural_language=True)
    parsed=SpecInput(keywords='后端开发',cities=['上海'],days_per_week=5,max_queries=6,max_extracts=20)
    scope=preserve_scope(original,parsed)
    assert scope.cities==['杭州'] and scope.days_per_week==3
    assert scope.employment_type=='internship' and scope.max_queries==2 and scope.max_extracts==1


def test_city_districts_and_old_graduating_vacancies():
    for city in ['杭州','杭州市','杭州余杭区仓前','滨江区']:
        p=Opportunity(title='Python实习',cities=[city],relevance='high')
        check_scope(p,['杭州'])
        assert p.relevance=='high'
    other=Opportunity(title='Python实习',cities=['大连市'],relevance='high')
    check_scope(other,['杭州']);assert other.relevance=='low'
    old=Opportunity(title='Python实习生（2020届）',cities=['杭州'],relevance='high')
    check_scope(old,['杭州']);assert old.relevance=='low' and '较早' in old.relevance_reason
