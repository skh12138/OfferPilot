// Inspect real public cards in the isolated stack, without exposing login credentials.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';

const access = JSON.parse(await fs.readFile('.local/live-access.json', 'utf8'));
const evidence = JSON.parse(await fs.readFile('docs/discovery-live-evidence.json', 'utf8'));
assert.equal(access.origin, 'http://localhost:8082');
const browser = await chromium.launch({channel:'chrome'});
try {
  const context = await browser.newContext({baseURL:access.origin});
  const csrf = (await (await context.request.get('/api/v1/auth/csrf')).json()).csrf_token;
  const response = await context.request.post('/api/v1/auth/login', {
    data:{username:access.username,password:access.password},
    headers:{Origin:access.origin,'X-CSRF-Token':csrf},
  });
  assert(response.ok(), 'Validation account login failed');
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/discover?run='+(evidence.source_search_run_id||evidence.run.id));
  const cards=page.getByRole('article',{name:/招聘机会：/});
  await cards.first().waitFor();
  const count = await cards.count();
  assert(count>=3, 'Expected multiple source-linked cards');
  for(const width of [390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    await page.screenshot({path:`docs/screenshots/${width}-discovery-live.png`,fullPage:true,animations:'disabled'});
    await cards.first().screenshot({path:`docs/screenshots/${width}-discovery-live-card.png`,animations:'disabled'});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth), `Overflow at ${width}`);
  }
  await page.reload();
  await cards.first().waitFor();
  assert.equal(await cards.count(),count);
  assert.equal(errors.length,0,'Browser runtime errors');
  await fs.writeFile('docs/discovery-browser-evidence.json',JSON.stringify({
    time:new Date().toISOString(),origin:access.origin,mode:'live',run_id:evidence.run.id,
    source_search_run_id:evidence.source_search_run_id||evidence.run.id,
    visible_cards:count,widths:[390,768,1440],refresh_preserves_results:true,
    no_horizontal_overflow:true,page_errors:errors,personal_input:'none',
  },null,2)+'\n');
  console.log('Real cards rendered at 390/768/1440:',count);
} finally {
  await browser.close();
}
