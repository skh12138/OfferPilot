"""Real public recruitment search in the isolated 8082 stack; no private resume input."""
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


async def main():
    access = json.loads(Path('.local/live-access.json').read_text())
    origin = access['origin']
    if origin != 'http://localhost:8082':
        raise SystemExit('Only the isolated validation stack may be used')
    report = {'started_at': datetime.now(UTC).isoformat(), 'mode': 'live',
              'origin': origin, 'input': '帮我找找杭州开发相关实习',
              'checks': {}, 'limitations': []}
    async with httpx.AsyncClient(base_url=origin, timeout=20) as client:
        async def post(path, body):
            token = (await client.get('/api/v1/auth/csrf')).json()['csrf_token']
            response = await client.post('/api/v1'+path, json=body, headers={
                'Origin': origin, 'X-CSRF-Token': token, 'Idempotency-Key': str(uuid4())})
            if not response.is_success:
                raise RuntimeError(f'{path} HTTP {response.status_code}: {response.json().get("error", {}).get("code")}')
            return response.json()

        try:
            await post('/auth/login', {'username': access['username'], 'password': access['password']})
            capabilities = (await client.get('/api/v1/capabilities')).json()
            assert capabilities['mode'] == 'live' and capabilities['model_available'] and capabilities['search_available']
            await post('/me/model-consent', {'granted': False})
            source_id = None
            if '--organize-existing' in sys.argv:
                previous = json.loads(Path('docs/discovery-live-evidence.json').read_text())
                assert previous['input'] == report['input']
                source_id = previous.get('source_search_run_id', previous['run']['id'])
                report['source_search_run_id'] = source_id
                queued = await post('/search-runs/'+source_id+'/organize', {'public_info_ai_consent': True})
            else:
                queued = await post('/search-runs/natural', {
                    'text': report['input'], 'max_queries': 3, 'max_results': 8,
                    'max_extracts': 2, 'public_info_ai_consent': True})
            print('Real search queued:', queued['id'], flush=True)
            for _ in range(240):
                run = (await client.get('/api/v1/runs/'+queued['id'])).json()
                if run['status'] in {'succeeded', 'partial', 'failed', 'cancelled'}:
                    break
                await asyncio.sleep(2)
            else:
                raise RuntimeError('Real search exceeded bounded acceptance wait')
            report['run'] = {k: run.get(k) for k in ['id', 'kind', 'status', 'error_code', 'model', 'prompt_version', 'result']}
            candidates = (await client.get('/api/v1/search-runs/'+(source_id or run['id'])+'/candidates')).json()['items']
            report['candidates'] = candidates
            positions = [(c, p) for c in candidates for p in (c.get('intelligence') or {}).get('opportunities', [])]
            relevant = [(c, p) for c, p in positions if p['relevance'] != 'low']
            report['counts'] = {'sources': len(candidates), 'positions': len(positions),
                                'relevant_positions': len(relevant),
                                'positions_with_requirements': sum(bool(p['requirements']) for c, p in relevant),
                                'predicted_difficulties': sum(p['difficulty']['level'] != 'unknown' for c, p in relevant)}
            consent = (await client.get('/api/v1/me/model-consent')).json()['granted']
            report['checks']['private_model_consent_remains_false'] = not consent
            report['checks']['real_queue_completed'] = run['status'] in {'succeeded', 'partial'}
            report['checks']['multiple_source_linked_cards'] = len(relevant) >= 3
            report['checks']['requirements_available'] = any(p['requirements'] for c, p in relevant)
            report['checks']['separate_ai_predictions'] = any(p['difficulty']['level'] != 'unknown' for c, p in relevant)
            report['limitations'].append('Search excerpts are public source evidence, not a full JD. Live availability and all hiring requirements still require the original site.')
            report['limitations'].append('Difficulty is a model prediction based on public evidence, not a measured interview pass rate or a personal fit score.')
            print('Real result:', run['status'], report['counts'], flush=True)
        except Exception as exc:
            report['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
            print('Live validation failed:', type(exc).__name__, str(exc), flush=True)
    report['completed_at'] = datetime.now(UTC).isoformat()
    Path('docs/discovery-live-evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    if report.get('failure') or not all(report['checks'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
