import { defineConfig } from '@playwright/test';
export default defineConfig({
 testDir:'./tests/e2e',timeout:60000,expect:{timeout:15000},fullyParallel:false,workers:1,
 reporter:[['list'],['html',{open:'never'}]],
 use:{baseURL:'http://localhost:5179',trace:'retain-on-failure',screenshot:'only-on-failure',channel:process.env.PLAYWRIGHT_CHANNEL||undefined},
 webServer:[
  {command:'.venv/bin/uvicorn offerpilot.api.app:app --host 127.0.0.1 --port 8011 --no-access-log',url:'http://127.0.0.1:8011/api/v1/health/ready',reuseExistingServer:false},
  {command:'.venv/bin/python -m offerpilot.worker.main',wait:{stdout:/OfferPilot worker ready/},reuseExistingServer:false},
  {command:'pnpm --dir apps/web dev --port 5179',url:'http://localhost:5179',reuseExistingServer:false},
 ],
});
