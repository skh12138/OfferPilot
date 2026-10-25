import pytest
from offerpilot.api.errors import DomainError
from offerpilot.modules.jobs.schemas import JobExtraction
from offerpilot.modules.jobs.service import validate_extraction


def test_model_cannot_self_confirm_or_assert_user_field():
    data = JobExtraction.model_validate({
        'title': '合成岗位', 'classification': 'job_detail',
        'field_evidence': {'title': {'value': '合成岗位', 'review_status': 'confirmed',
            'source_kind': 'provider_extracted', 'paragraph_id': 'p1', 'quote': '合成岗位'}}
    })
    assert validate_extraction(data, '合成岗位').field_evidence['title'].review_status == 'unreviewed'
    data.field_evidence['title'].source_kind = 'user_asserted'
    with pytest.raises(DomainError, match='模型不能'):
        validate_extraction(data, '合成岗位')
    assert validate_extraction(data, '合成岗位', user_review=True).field_evidence['title'].evidence_status == 'user_asserted'
