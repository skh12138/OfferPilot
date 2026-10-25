import {expect,type Page} from '@playwright/test';
export async function capture(page:Page,name:string,widths=[1440,390]){
 const original=page.viewportSize();
 try{for(const width of widths){await page.setViewportSize({width,height:900});await page.evaluate(async()=>{if(document.activeElement instanceof HTMLElement)document.activeElement.blur();window.scrollTo({top:0,behavior:'instant'});await document.fonts.ready;await new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));});await page.waitForTimeout(100);await page.screenshot({path:`docs/ui-redesign/screenshots/after/${name}-${width}.png`,fullPage:await page.getByRole('dialog').count()===0,animations:'disabled'});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name+' overflow').toBe(true);}}
 finally{if(original)await page.setViewportSize(original);}
}
