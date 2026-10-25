"""Small, explicit real API probe. Output excludes credentials and response headers."""
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from offerpilot.infrastructure.config import settings
from offerpilot.providers.base import ProviderError
from offerpilot.providers.deepseek import DeepSeekLLMProvider
from offerpilot.providers.tavily import TavilyContentProvider, TavilySearchProvider
from offerpilot.providers.urls import validate_public_dns


async def main():
    cfg = settings()
    if cfg.app_mode != 'live':
        raise SystemExit('Real probe requires APP_MODE=live')
    report = {'time': datetime.now(UTC).isoformat(), 'mode': 'live', 'synthetic_personal_data': True}
    async with httpx.AsyncClient(follow_redirects=False) as client:
        async def model():
            try:
                result = await DeepSeekLLMProvider(client, cfg.deepseek_api_key.get_secret_value(), cfg.llm_model).generate_json(
                    'connectivity', {'type':'object','properties':{'status':{'type':'string','enum':['ok']}},'required':['status'],'additionalProperties':False},
                    {'instruction':'仅返回 status=ok；这是连接检查，不含个人资料'}, max_tokens=128,
                )
                return {'status':'passed' if result.data == {'status':'ok'} else 'unexpected_output', 'requested_model':cfg.llm_model, 'usage':result.usage.model_dump()}
            except ProviderError as exc:
                return {'status':'failed','code':exc.code,'requested_model':cfg.llm_model}
        async def search():
            try:
                result = await TavilySearchProvider(client, cfg.tavily_api_key.get_secret_value()).search('Python 实习 招聘 杭州', max_results=3)
                return {'status':'passed','query':'Python 实习 招聘 杭州','count':len(result.results),'candidates':[{'url':h.url,'title':h.title} for h in result.results], 'usage':result.usage.model_dump()}
            except ProviderError as exc:
                return {'status':'failed','code':exc.code}
        report['deepseek'], report['tavily_search'] = await asyncio.gather(model(), search())
        url='https://docs.tavily.com/'
        try:
            await validate_public_dns(url)
            result=await TavilyContentProvider(client,cfg.tavily_api_key.get_secret_value()).extract([url])
            report['tavily_extract']={'status':'passed' if result.texts.get(url) else 'content_unavailable','url':url,'characters':len(result.texts.get(url,'')), 'failures':result.failures,'usage':result.usage.model_dump()}
        except ProviderError as exc:
            report['tavily_extract']={'status':'failed','code':exc.code,'url':url}
    Path('docs/provider-live-health.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if any(report[name]['status'] != 'passed' for name in ['deepseek','tavily_search','tavily_extract']):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
