"""Browser regression checks; run against a locally generated calendar site."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def run(url, executable, output):
    output.mkdir(parents=True, exist_ok=True)
    report = {'viewports': [], 'scenarios': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
        context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        for width in [360, 390, 768, 1280]:
            page.set_viewport_size({'width': width, 'height': 1000})
            page.goto(url, wait_until='networkidle')
            page.wait_for_selector('.map-target')
            page.evaluate('document.fonts.ready')
            assert page.locator('#city-list button').count() == 116
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            assert page.evaluate('document.fonts.check(\'400 16px "PT Sans"\') && document.fonts.check("500 30px Literata")')
            heights, tops, counts = [], [], {}
            for region in ['all', 'west', 'south', 'center', 'east']:
                page.locator(f'[data-view={region}]').click()
                box = page.locator('#map').bounding_box()
                heights.append(box['height']); tops.append(page.locator('.workspace').bounding_box()['y'] + page.evaluate('scrollY'))
                assert page.locator(f'[data-view={region}]').get_attribute('aria-pressed') == 'true'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                geometry = page.evaluate('''() => {
                  const map = document.querySelector('#map').getBoundingClientRect();
                  const targets = [...document.querySelectorAll('.map-target')];
                  const labels = [...document.querySelectorAll('[data-label-for]')].map(e => e.getBoundingClientRect().toJSON());
                  return {targets: targets.map(e => ({rect:e.getBoundingClientRect().toJSON(),ids:e.dataset.members.split(' ')})),
                    points:[...document.querySelectorAll('[data-point]')].map(e=>e.dataset.point),labels,map:map.toJSON()};
                }''')
                members = [i for target in geometry['targets'] for i in target['ids']]
                assert len(members) == len(set(members))
                assert set(members) == set(geometry['points'])
                if region == 'all': assert len(members) == 116
                counts[region] = len(geometry['targets'])
                for i, target in enumerate(geometry['targets']):
                    r = target['rect']; m = geometry['map']
                    assert r['width'] >= 44 and r['height'] >= 44
                    assert r['left'] >= m['left'] and r['right'] <= m['right'] and r['top'] >= m['top'] and r['bottom'] <= m['bottom']
                    for other in geometry['targets'][i+1:]:
                        t = other['rect']
                        assert min(r['right'], t['right']) <= max(r['left'], t['left']) or min(r['bottom'], t['bottom']) <= max(r['top'], t['top']), ('overlap', width, region)
                for i, r in enumerate(geometry['labels']):
                    m = geometry['map']
                    assert r['left'] >= m['left'] and r['right'] <= m['right'] and r['top'] >= m['top'] and r['bottom'] <= m['bottom'], ('clipped label',width,region)
                    for t in geometry['labels'][i+1:]:
                        assert min(r['right'], t['right']) <= max(r['left'], t['left']) or min(r['bottom'], t['bottom']) <= max(r['top'], t['top']), ('labels overlap',width,region)
                page.locator('#map').screenshot(path=str(output/f'map-{region}-{width}.png'))
            assert len(set(heights)) == 1 and max(tops)-min(tops) < 1, (heights,tops)
            assert heights[0] == (320 if width <= 700 else 430)
            for city in ['moscow', 'kaliningrad', 'murmansk', 'vladivostok', 'anadyr']:
                page.locator(f'#city-list [data-city={city}]').click()
                assert page.url.endswith('#'+city)
                assert page.locator(f'#city-list [data-city={city}]').get_attribute('aria-pressed') == 'true'
                assert page.locator(f'[data-label-for={city}]').count() == 1
                assert page.locator('#calendar-url').input_value() == f'https://brodov.net/sun-calendar/{city}.ics'
                assert page.locator('#subscribe').get_attribute('href') == f'webcal://brodov.net/sun-calendar/{city}.ics'
                assert page.locator('#download').get_attribute('href') == city+'.ics'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                m=page.locator('#map').bounding_box();r=page.locator(f'[data-label-for={city}]').bounding_box()
                assert r['x']>=m['x'] and r['x']+r['width']<=m['x']+m['width']
                page.locator('#map').screenshot(path=str(output/f'selected-{city}-{width}.png'))
            page.reload(wait_until='networkidle');page.wait_for_selector('[data-label-for=anadyr]')
            assert page.locator('#city-title').inner_text() == 'Анадырь'
            page.locator('#search').fill('могилёв');a=page.locator('#city-list button:visible').all_text_contents()
            page.locator('#search').fill('МОГИЛЕВ');assert a == page.locator('#city-list button:visible').all_text_contents() and len(a)==1
            page.locator('#search').fill('несуществующийгород');assert page.locator('#empty').is_visible()
            page.locator('#search').fill('')
            page.locator('#city-list [data-city=moscow]').click()
            page.locator('[data-view=all]').click()
            page.evaluate('scrollTo(0,0)')
            page.screenshot(path=str(output/f'design-{width}.png'),full_page=True)
            report['viewports'].append({'width':width,'map_height':heights[0],'targets_by_region':counts,'checks':'passed'})
        page.locator('#copy').click()
        page.wait_for_function('document.querySelector("#copy-status").textContent === "Ссылка скопирована"')
        assert page.evaluate('navigator.clipboard.readText()') == 'https://brodov.net/sun-calendar/moscow.ics'
        page.evaluate("() => {navigator.clipboard.writeText = async () => {throw new Error('denied')}}")
        page.locator('#copy').click()
        page.wait_for_function('document.activeElement.id === "calendar-url"')
        assert page.locator('#calendar-url').evaluate('(e)=>e.selectionEnd-e.selectionStart') == len(page.locator('#calendar-url').input_value())
        report['scenarios'] += ['clipboard success and denied/manual selection', '116 map cities reachable through nonoverlapping 44px targets', 'hash reload, city/list/map sync, links, ё/е, no results']
        # Native button keyboard semantics and visible focus; dialog Escape returns focus.
        group=page.locator('.map-target[aria-haspopup]').first
        group.focus();page.keyboard.press('Enter');assert page.locator('.map-popup').is_visible()
        page.keyboard.press('Escape');assert page.locator('.map-popup').count()==0
        assert page.evaluate('document.activeElement.matches(".map-target:focus-visible")')
        assert page.evaluate('getComputedStyle(document.activeElement).outlineStyle') != 'none'
        page.keyboard.press('Space');assert page.locator('.map-popup').is_visible()
        choice=page.locator('.popup-cities button').last;city=choice.get_attribute('data-city');choice.click()
        assert page.url.endswith('#'+city) and page.locator(f'#city-list [data-city={city}]').get_attribute('aria-pressed')=='true'
        page.locator('[aria-label="Приблизить карту"]').click()
        page.locator('[aria-label="Отдалить карту"]').click()
        page.locator('[aria-label="Сбросить масштаб области"]').click()
        page.locator('#subscribe').focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
        assert page.locator('#subscribe').evaluate('(e)=>e.matches(":focus-visible") && getComputedStyle(e).outlineStyle !== "none"')
        report['scenarios'] += ['Enter/Space, popup selection and Escape focus restoration, subscribe focus-visible, zoom controls']
        for failed in ['map.svg', 'map-projection.json', 'cities.json']:
            fallback=context.new_page();fallback.route('**/'+failed,lambda route:route.abort())
            fallback.goto(url,wait_until='networkidle')
            if failed=='cities.json':
                assert fallback.locator('#all-calendars').get_attribute('open') is not None
                assert fallback.locator('#all-calendars a').count()==116
                assert fallback.locator('.selection').is_hidden()
            else:
                assert fallback.locator('#city-list button').count()==116
                fallback.locator('#search').fill('Анадырь');fallback.locator('#city-list button:visible').click()
                assert fallback.locator('#subscribe').get_attribute('href').endswith('/anadyr.ics')
                assert 'временно недоступна' in fallback.locator('#map').inner_text()
            fallback.close()
        nojs=browser.new_context(java_script_enabled=False).new_page();nojs.goto(url,wait_until='networkidle')
        assert nojs.locator('#all-calendars a').count()==116 and nojs.locator('#all-calendars').get_attribute('open') is not None
        assert nojs.locator('#all-calendars a').first.is_visible()
        assert page.locator('meta[name="twitter:card"]').get_attribute('content')=='summary_large_image'
        image=page.locator('meta[property="og:image"]').get_attribute('content')
        assert image.startswith('https://brodov.net/sun-calendar/social-')
        assert page.locator('meta[name="twitter:image"]').get_attribute('content')==image
        assert not errors,errors
        report['scenarios'] += ['map and projection failures leave search/subscriptions working', 'city-data failure and no JavaScript expose 116 static ICS links', 'versioned absolute OG/Twitter metadata']
        browser.close()
    (output/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://localhost:8790/')
    parser.add_argument('--browser')
    parser.add_argument('--output',type=Path,default=Path('/tmp/sun-ui-review'))
    args=parser.parse_args();run(args.url,args.browser,args.output)
