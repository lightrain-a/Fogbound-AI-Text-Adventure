"""Headless UI checks on the actual localhost app; does not call the model."""
import json, urllib.request, urllib.error
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
results=[]
def check(name,condition):results.append({'name':name,'passed':bool(condition)});print(name,bool(condition),flush=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1060},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765/',wait_until='networkidle')
    page.wait_for_selector('#inventory .item')
    check('title',page.title().startswith('雾港末班车'))
    check('initial_inventory',page.locator('#inventory .item').count()==1)
    check('initial_buttons',page.locator('#actions button').count()==5)
    check('no_horizontal_overflow_desktop',page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
    page.locator('#save').click();page.wait_for_timeout(300)
    check('save_confirmation','保存' in page.locator('#busy').inner_text())
    page.locator('#reset').click();page.wait_for_timeout(300)
    page.locator('#load').click();page.wait_for_timeout(300)
    check('saved_game_loaded',page.locator('#inventory .item').count()==1)
    page.screenshot(path=str(OUT/'ui_start.png'),full_page=True)
    # Render a fake HTML tag as plain text in this temporary browser page only.
    page.evaluate("data.history[data.history.length-1].narration='<img src=x onerror=alert(1)>';render(data)")
    check('model_output_rendered_as_text',page.locator('#narration img').count()==0 and '<img' in page.locator('#narration').inner_text())
    page.reload(wait_until='networkidle');page.wait_for_selector('#inventory .item')
    page.set_viewport_size({'width':390,'height':844})
    check('no_horizontal_overflow_mobile',page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'))
    page.screenshot(path=str(OUT/'ui_mobile.png'),full_page=True)
    check('no_javascript_errors',not errors)
    check('browser_has_no_api_key',not page.evaluate("document.documentElement.outerHTML.includes('tk-')"))
    browser.close()
try:
    req=urllib.request.Request('http://127.0.0.1:8765/api/reset',data=b'{}',headers={'Content-Type':'application/json'})
    urllib.request.urlopen(req,timeout=5);check('csrf_rejection',False)
except urllib.error.HTTPError as e:check('csrf_rejection',e.code==403)
(OUT/'browser_checks.json').write_text(json.dumps({'checks':results,'all_passed':all(x['passed'] for x in results),'api_calls_made':0},ensure_ascii=False,indent=2),encoding='utf-8')
print('BROWSER_CHECKS_DONE',len(results),flush=True)
