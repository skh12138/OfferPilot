import json
from pathlib import Path
import pytest
from offerpilot.providers.fixtures import FixtureProvider
from offerpilot.modules.jobs.schemas import JobExtraction

SAMPLES=json.loads(Path('fixtures/synthetic/jobs.json').read_text())


@pytest.mark.parametrize('sample',SAMPLES,ids=[s['id'] for s in SAMPLES])
async def test_synthetic_boundary_schema(sample):
    result=await FixtureProvider().generate_json('job_normalize',{}, {'text':sample['text']})
    job=JobExtraction.model_validate(result.data)
    assert sample['synthetic'] is True
    if sample['template_group']=='non-job':assert job.classification=='non_job'
    if sample['template_group']=='list-page':assert job.classification=='job_list'
    if sample['template_group']=='javascript':
        assert all('java' not in r.skills for r in job.requirements)
    if sample['template_group']=='missing-days':assert 'days_per_week' not in job.conditions
    if sample['template_group']=='mixed-units':assert 'duration_months' not in job.conditions
