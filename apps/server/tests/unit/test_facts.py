from datetime import date
from uuid import uuid4
import pytest
from offerpilot.api.errors import DomainError
from offerpilot.modules.profiles.schemas import Evidence,Fact
from offerpilot.modules.preparation.schemas import BundlePayload,Claim
from offerpilot.modules.preparation.rules import validate_claims
from offerpilot.modules.interview.rules import next_review


@pytest.mark.parametrize('claim',['主导完成企业生产平台，提升效率50%。','使用 Java 完成任务列表。','已经完成计划中的 Agent 项目。'])
def test_valid_id_does_not_authorize_wrong_claim(claim):
    f=Fact(fact_id=uuid4(),text='参与使用 Vue3 完成任务列表。',status='user_confirmed',evidence=Evidence(paragraph_id='p1',quote='参与使用 Vue3 完成任务列表。',source_kind='resume_text'))
    payload=BundlePayload(claims=[Claim(text=claim,fact_ids=[f.fact_id],quotes=[f.text])],gaps=[],tasks=[],introduction='',contact_draft='')
    with pytest.raises(DomainError):validate_claims(payload,[f])


def test_review_clock_is_explicit():
    assert next_review(date(2026,12,31),'needs_review')==date(2027,1,1)
    assert next_review(date(2026,12,31),'confident')==date(2027,1,7)
