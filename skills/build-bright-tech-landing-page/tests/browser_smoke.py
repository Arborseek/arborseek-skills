"""Optional real-browser tests; requires already installed Playwright and Chromium."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', type=Path, help='Optional new screenshot output directory')
    parser.add_argument('--channel', choices=('chrome', 'msedge'), help='Use an already installed browser instead of bundled Chromium')
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=False)
    url = (Path(__file__).resolve().parents[1] / 'examples/landing-page.html').as_uri()
    passed = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, channel=args.channel)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(10000)
            errors = []
            requests = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            for width in (360, 768, 1440):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.goto(url, wait_until='networkidle')
                assert page.locator('h1').is_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                if args.screenshots:
                    page.screenshot(path=str(args.screenshots / ('example-%s.png' % width)), full_page=True)
                passed.append('no horizontal overflow at %spx' % width)
            page.set_viewport_size({'width': 360, 'height': 900})
            menu = page.get_by_role('button', name='导航菜单')
            nav = page.get_by_role('navigation', name='页面导航')
            assert not nav.is_visible()
            menu.focus()
            page.keyboard.press('Enter')
            assert menu.get_attribute('aria-expanded') == 'true' and nav.is_visible()
            page.keyboard.press('Tab')
            assert nav.get_by_role('link', name='工作流程').evaluate('(el) => el === document.activeElement')
            page.keyboard.press('Escape')
            assert not nav.is_visible() and menu.evaluate('(el) => el === document.activeElement')
            passed.append('keyboard open, Tab navigation, Escape focus restoration')
            menu.click()
            nav.get_by_role('link', name='工作流程').click()
            assert not nav.is_visible()
            assert page.locator('#process').evaluate('(el) => el === document.activeElement')
            page.set_viewport_size({'width': 1440, 'height': 900})
            nav.get_by_role('link', name='工作流程').focus()
            page.set_viewport_size({'width': 360, 'height': 900})
            page.wait_for_function("document.activeElement.id === 'menu-toggle'")
            passed.append('link selection and breakpoint focus behavior')
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.hero-copy').evaluate('(el) => getComputedStyle(el).animationName') == 'none'
            assert page.locator('html').evaluate('(el) => getComputedStyle(el).scrollBehavior') == 'auto'
            passed.append('reduced motion disables animation and smooth scrolling')
            page.locator('h1').evaluate("el => el.textContent = 'IndustrialInspectionWorkflowWithAVeryLongUnbrokenHeading' ")
            page.add_style_tag(content='html { font-size: 200%; }')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            passed.append('long heading and 200% root text size: no horizontal overflow')
            nojs = browser.new_context(java_script_enabled=False, viewport={'width': 360, 'height': 900})
            fallback = nojs.new_page()
            fallback.goto(url, wait_until='networkidle')
            assert fallback.get_by_role('navigation', name='页面导航').is_visible()
            assert fallback.locator('h1').is_visible()
            passed.append('navigation and content remain available without JavaScript')
            assert not errors, errors
            assert not [item for item in requests if item.startswith(('http:', 'https:'))], requests
            passed.append('no page errors or external network requests')
        finally:
            browser.close()
    print(json.dumps({'status': 'passed', 'checks': passed,
                      'scope': 'bundled example in headless Chromium; not five-client or deployed-site acceptance'},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
