"""Read-only checks for a complete static HTML file; not a browser or security audit."""
import argparse
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.ids = []
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.nodes.append((tag, attrs, self.getpos()[0]))
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def read_document(path):
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError('HTML exceeds the 5 MiB inspection limit')
    doc = Document()
    doc.feed(path.read_text(encoding='utf-8-sig'))
    doc.close()
    return doc


def inspect(path, root=None):
    path = Path(path).resolve()
    root = Path(root).resolve() if root else path.parent
    if path.suffix.lower() not in ('.html', '.htm'):
        raise ValueError('Expected a complete .html/.htm file, not a framework source component')
    if path != root and root not in path.parents:
        raise ValueError('Input is outside the selected site root')
    doc = read_document(path)
    failures, passed, external = [], [], []

    def check(ok, code, detail):
        (passed if ok else failures).append({'check': code, 'detail': detail})

    check(any(tag == 'html' and attrs.get('lang', '').strip() for tag, attrs, _ in doc.nodes),
          'language', 'html lang')
    # SVG title must not satisfy the page-title check: require a title in the head substring.
    source = path.read_text(encoding='utf-8-sig')
    head = source.lower().split('</head>', 1)[0] if '</head>' in source.lower() else ''
    head_doc = Document()
    head_doc.feed(head)
    check(bool(''.join(head_doc.title).strip()), 'title', 'nonempty document head title')
    check(any(tag == 'meta' and attrs.get('name', '').lower() == 'viewport'
              and 'width=device-width' in attrs.get('content', '').replace(' ', '').lower()
              for tag, attrs, _ in doc.nodes), 'viewport', 'device-width viewport')
    check(any(tag == 'main' for tag, _, _ in doc.nodes), 'main', 'main landmark')
    duplicates = [ident for ident, count in Counter(doc.ids).items() if count > 1]
    check(not duplicates, 'unique_ids', ', '.join(duplicates) or 'IDs are unique')
    cache = {path: doc}
    for tag, attrs, line in doc.nodes:
        if tag == 'img':
            check('alt' in attrs, 'image_alt', 'line %s' % line)
        for field in ('href', 'src', 'poster'):
            if field not in attrs:
                continue
            value = (attrs[field] or '').strip()
            label = 'line %s %s=%s' % (line, field, value)
            if not value:
                check(False, 'empty_reference', label)
                continue
            parsed = urlsplit(value)
            if parsed.scheme.lower() in ('javascript', 'vbscript', 'file'):
                check(False, 'unsafe_reference', label)
                continue
            if parsed.scheme or parsed.netloc:
                external.append(label)
                continue
            target = ((root / unquote(parsed.path).lstrip('/')) if parsed.path.startswith('/')
                      else (path.parent / unquote(parsed.path))) if parsed.path else path
            target = target.resolve()
            if target != root and root not in target.parents:
                check(False, 'outside_root', label)
                continue
            check(target.is_file(), 'local_file', label)
            if target.is_file() and parsed.fragment and target.suffix.lower() in ('.html', '.htm'):
                if target not in cache:
                    cache[target] = read_document(target)
                check(unquote(parsed.fragment) in cache[target].ids, 'anchor', label)
    return {'scope': 'static_html_only', 'file': str(path), 'site_root': str(root),
            'status': 'failed' if failures else 'passed', 'passed': passed, 'failed': failures,
            'unverified': ['browser layout and horizontal overflow', 'keyboard and JavaScript behavior',
                           'CSS url(), srcset, fonts, and contrast', 'build, backend, deployment',
                           'external and non-file references'], 'external_references': external}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--root', type=Path, help='Site root for /paths; defaults to the HTML directory')
    args = parser.parse_args(argv)
    try:
        result = inspect(args.html, args.root)
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({'status': 'input_error', 'error': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
