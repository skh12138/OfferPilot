"""Read a bounded selection of public recruitment URLs; no policy auto-approval."""
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

from offerpilot.infrastructure.config import settings
from offerpilot.providers.base import ProviderError
from offerpilot.providers.tavily import TavilyContentProvider, TavilySearchProvider
from offerpilot.providers.urls import canonical_url, validate_public_dns


async def main():
    key = settings().tavily_api_key.get_secret_value()
    report = {'time': datetime.now(UTC).isoformat(), 'purpose':'bounded public-source readability probe; no policy approval', 'sources':[]}
    bodies = {}
    async with httpx.AsyncClient(follow_redirects=False) as client:
        search = TavilySearchProvider(client, key)
        content = TavilyContentProvider(client, key)
        queries = [
            ('jobs.bytedance.com', 'site:jobs.bytedance.com "Python" "实习" "职位描述"'),
            ('career.huawei.com', 'site:career.huawei.com "软件" "岗位职责"'),
            ('www.nowcoder.com', 'site:www.nowcoder.com/discuss "Python" "面经"'),
        ]
        for domain, query in queries:
            record={'domain':domain,'query':query}
            try:
                found=await search.search(query,3)
                record['search_usage']=found.usage.model_dump()
                record['candidates']=[{'url':h.url,'title':h.title} for h in found.results]
                urls=[canonical_url(h.url) for h in found.results if domain in h.url][:1]
                if not urls:
                    record['status']='no_target_result'
                else:
                    await validate_public_dns(urls[0])
                    extracted=await content.extract(urls)
                    record['extract_usage']=extracted.usage.model_dump()
                    record['extract']=[{'url':u,'characters':len(extracted.texts.get(u,'')),'status':'readable' if extracted.texts.get(u) else 'unavailable'} for u in urls]
                    record['status']='readable' if extracted.texts else 'unavailable'
                    bodies.update(extracted.texts)
            except ProviderError as exc:
                record.update(status='failed',code=exc.code)
            report['sources'].append(record)
    Path('.local').mkdir(exist_ok=True)
    with os.fdopen(os.open('.local/source-probe-content.json',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as handle:
        json.dump(bodies,handle,ensure_ascii=False)
    Path('docs/live-source-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    asyncio.run(main())
