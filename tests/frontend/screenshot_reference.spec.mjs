import {test, expect} from '@playwright/test';
import path from 'node:path';
import {screenshotReferenceData} from './screenshot_reference_data.mjs';

const viewports = [['phone-320',320,740],['phone-393',393,852],['phone-430',430,932],['desktop',1440,900]];
const output = process.env.HKM_REFERENCE_SCREENSHOTS || 'test-results/photo-reference';
for (const [name,width,height] of viewports) {
  test(`original photo references: ${name}, long names, 1172 entities and unknown activation`,async ({page}, info)=>{
    await page.setViewportSize({width,height}); await page.emulateMedia({colorScheme:'dark'});
    await page.goto('/tests/frontend/browser_fixture.html?activation-error');
    const panel=page.locator('homekit-manager-panel');
    await expect(panel.getByText('Fixture Bridge',{exact:true})).toBeVisible();
    const reference=screenshotReferenceData();
    expect(reference.entities).toHaveLength(1172);expect(reference.overview.device_count).toBe(129);expect(reference.overview.configured_entities).toBe(368);
    await panel.evaluate((element, data)=>{
      element.entities=data.entities;element.overview=data.overview;element.draft=new Map([[data.presenceId,'excluded']]);
      element.bridge.title='Referenz-Bridge';element.bridges[0].title='Referenz-Bridge';
      element.activationStatus={state:'unknown',has_operation:true,persistent:false,message:'Der Ausgang des früheren Vorgangs ist nicht bestätigt.',automatic_retry:false,observations:{bridge_state:'loaded'}};
      element.statusMessage='1 Änderung als Entwurf vorgemerkt';element.render();
      const note=document.createElement('aside');note.textContent='Isolierte Referenzdaten – keine Live-Daten';note.setAttribute('data-reference-note','');
      note.style.cssText='padding:8px 14px;font:12px system-ui;background:#272f38;color:#eef2f6';document.body.prepend(note);
    }, reference);
    for (const [view,label] of [['home','HomeKit'],['devices','Geräte'],['changes','Änderungen'],['settings','Einstellungen']]) {
      await panel.getByRole('tab',{name:label,exact:true}).click();
      if (view==='home') {
        await expect(panel.locator('.status-grid')).toContainText('Schreiben');
        await expect(panel.locator('.status-grid')).toContainText('1');
        await expect(panel.locator('.lock-note')).toContainText('gesperrt');
      }
      if (view==='devices') {
        await expect(panel.locator('.area-card')).toHaveCount(11);
        const unassigned=panel.locator('.area-card').filter({has:page.locator('[data-area="Ohne Bereich"]')});
        await expect(unassigned.locator('.area-heading')).toContainText('72 Geräte · 581 Entitäten · 190 ohne Gerät');
        await expect(unassigned.locator('.area-metrics dd')).toHaveText(['248','168','378']);
        const kitchen=panel.locator('.area-card').filter({has:page.locator('[data-area="Küche"]')});
        await expect(kitchen.locator('.area-metrics dd')).toHaveText(['6','13','53']);
        const totals=await panel.evaluate(element=>({global:element.counts(element.entities).devices,areas:[...new Set(element.entities.map(e=>e.area_name))].map(area=>element.counts(element.entities.filter(e=>e.area_name===area)).devices)}));
        expect(totals.global).toBe(129);expect(Math.max(...totals.areas)).toBeLessThanOrEqual(totals.global);
      }
      if (view==='changes') {
        await expect(panel.locator('[data-activation-state=unknown]')).toHaveClass(/tone-neutral/);
        await expect(panel.locator('[data-apply]')).toBeDisabled();
        await expect(panel.locator('.change-row code')).toHaveText(reference.presenceId);
        const separate=await panel.locator('.change-row .entity-copy').evaluate(copy=>{const name=copy.querySelector('strong').getBoundingClientRect(),id=copy.querySelector('code').getBoundingClientRect();return id.top>=name.bottom-1&&id.right<=innerWidth;});
        expect(separate).toBe(true);
        await panel.locator('[data-apply]').scrollIntoViewIfNeeded();
        await expect(panel.locator('[data-apply]')).toBeInViewport();
        const actionsOverlap=await panel.evaluate(element=>{const lock=element.shadowRoot.querySelector('.lock-note').getBoundingClientRect();const actions=element.shadowRoot.querySelector('.sticky-actions').getBoundingClientRect();return actions.top<lock.bottom-1;});
        expect(actionsOverlap).toBe(false);
        const buttonsFit=await panel.locator('.sticky-actions > button').evaluateAll(buttons=>buttons.every(button=>{
          const range=document.createRange();range.selectNodeContents(button);const box=button.getBoundingClientRect();
          return [...range.getClientRects()].every(text=>text.left>=box.left+1 && text.right<=box.right-1);
        }));
        expect(buttonsFit).toBe(true);
        const buttonHeights=await panel.locator('.sticky-actions > button').evaluateAll(buttons=>buttons.map(button=>button.getBoundingClientRect().height));
        expect(Math.max(...buttonHeights)-Math.min(...buttonHeights)).toBeLessThanOrEqual(1);
      }
      if (view==='settings') {
        await expect(panel.locator('.settings-nav button')).toHaveCount(6);
        await expect(panel.locator('.settings-content')).toContainText('0.10.0');
      }
      const geometry=await panel.evaluate(element=>{const nav=element.shadowRoot.querySelector('.main-nav');return {page:document.documentElement.scrollWidth-innerWidth,nav:nav.scrollWidth-nav.clientWidth};});
      expect(geometry.page).toBeLessThanOrEqual(1);expect(geometry.nav).toBeLessThanOrEqual(1);
      await page.screenshot({path:path.join(output,info.project.name,`${name}-${view}.png`),fullPage:true});
    }
    expect(await page.evaluate(()=>window.fixtureCommands.includes('homekit_manager/apply_options_diff'))).toBe(false);
  });
}
