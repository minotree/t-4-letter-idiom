"""Fetch public exact-match dictionary pages; never mark a meaning as reviewed automatically."""
import argparse
import csv
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://opendict.korean.go.kr'


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks = []

    def handle_data(self, data):
        self.chunks.append(data)


def plain(fragment):
    parser = Text()
    parser.feed(fragment)
    return ' '.join(''.join(parser.chunks).split())


def word_key(text):
    return re.sub(r'[^가-힣]', '', text)


def hanja_key(text):
    return unicodedata.normalize('NFKC', text).replace('爲', '為')


def extract(source, reading):
    # Work only inside the public result list, not sidebar/suggested words.
    result = re.search(r'<div class="search_result">(.*?)<div class="paging_area">', source, re.S)
    if not result:
        if '<div class="result_none">' in source and '우리말샘에 등록되어 있지 않습니다' in source:
            return []
        if '찾기 결과가 없습니다' in source or '검색 결과가 없습니다' in source:
            return []
        # A true no-result page uses this phrase; unexpected pages are not "not found".
        if re.search(r'찾기 결과.{0,30}없', plain(source)):
            return []
        raise ValueError('Public result section not recognized')
    entries = []
    for block in re.findall(r'<dl>(.*?)</dl>', result.group(1), re.S):
        title = re.search(r'<dt>(.*?)</dt>', block, re.S)
        if not title:
            continue
        head = re.search(r'class="search_word_type[123]_(?:17|16)"[^>]*>([^<]*)', title.group(1))
        if not head or word_key(html.unescape(head.group(1))) != word_key(reading):
            continue
        original = re.search(r'class="[^"]*hanja_font[^"]*"[^>]*>(.*?)</span>', title.group(1), re.S)
        hanja = plain(original.group(1)).strip('() ') if original else ''
        for detail in re.findall(r'<dd>(.*?)</dd>', block, re.S):
            definition = re.search(r'class="word_dis[^\"]*"[^>]*>(.*?)</span>', detail, re.S)
            link = re.search(r'href="(/dictionary/view\?[^\"]+)"', detail)
            if definition and link:
                entries.append({'reading': reading, 'hanja': hanja, 'definition': plain(definition.group(1)),
                                'url': BASE + html.unescape(link.group(1))})
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--supplement', action='store_true', help='Also search the public idiom/proverb tab when vocabulary has no exact result')
    parser.add_argument('--extra-terms', nargs='+', help='Fetch referenced roots/redirects into a separate evidence file')
    args = parser.parse_args()
    source = ROOT / 'sajaseongeo_image_working.csv'
    with source.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if args.extra_terms:
        rows = [{'reading': word, 'hanja': '', 'meaning': ''} for word in args.extra_terms]
    if args.limit:
        rows = rows[:args.limit]
    cache = ROOT / 'tmp/content-audit/dictionary-pages'
    cache.mkdir(parents=True, exist_ok=True)

    def fetch(row):
        reading = row['reading']
        url = BASE + '/search/searchResult?' + urllib.parse.urlencode({'query': reading, 'wordMatch': 'Y', 'rowsperPage': 100})
        path = cache / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        try:
            if path.exists():
                raw = path.read_bytes()
            else:
                request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; IdiomContentReview/1.0)'})
                with urllib.request.urlopen(request, timeout=25) as response:
                    raw = response.read()
                path.write_bytes(raw)
                time.sleep(.3)
            entries = extract(raw.decode('utf-8'), reading)
            supplemental = None
            reference_pages = [{'url': url, 'sha256': hashlib.sha256(raw).hexdigest()}]
            if not entries and args.supplement:
                for alternate in [url.replace('wordMatch=Y', 'wordMatch=N'), url + '&dicType=2']:
                    supplemental = alternate
                    extra_path = cache / (hashlib.sha256(supplemental.encode()).hexdigest() + '.html')
                    if extra_path.exists():
                        extra_raw = extra_path.read_bytes()
                    else:
                        with urllib.request.urlopen(urllib.request.Request(supplemental, headers={'User-Agent': 'Mozilla/5.0 (compatible; IdiomContentReview/1.0)'}), timeout=25) as response:
                            extra_raw = response.read()
                        extra_path.write_bytes(extra_raw)
                        time.sleep(.3)
                    reference_pages.append({'url': supplemental, 'sha256': hashlib.sha256(extra_raw).hexdigest()})
                    entries = extract(extra_raw.decode('utf-8'), reading)
                    if entries:
                        break
            matching = [entry for entry in entries if hanja_key(entry['hanja']) == hanja_key(row['hanja'])]
            return {'hanja': row['hanja'], 'reading': reading, 'current_meaning': row['meaning'],
                    'lookup_url': url, 'fetch_status': 'ok', 'page_sha256': hashlib.sha256(raw).hexdigest(),
                    'supplemental_lookup_url': supplemental,
                    'reference_pages': reference_pages,
                    'hanja_match': bool(matching), 'entries': matching or entries,
                    'review_status': 'pending_human_comparison'}
        except Exception as error:
            return {'hanja': row['hanja'], 'reading': reading, 'current_meaning': row['meaning'],
                    'lookup_url': url, 'fetch_status': 'error', 'error': str(error), 'entries': [],
                    'review_status': 'pending_human_comparison'}

    results = []
    with ThreadPoolExecutor(max_workers=min(max(args.workers, 1), 3)) as pool:
        futures = [pool.submit(fetch, row) for row in rows]
        for task in as_completed(futures):
            results.append(task.result())
            if len(results) % 30 == 0:
                print(f'Fetched {len(results)}/{len(rows)}', flush=True)
    order = {row['hanja']: index for index, row in enumerate(rows)}
    results.sort(key=lambda item: order[item['hanja']])
    report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'provider': '국립국어원 우리말샘 공개 검색',
              'automatic_meaning_approval': False, 'rows': results}
    destination = ROOT / 'data/content-audit' / ('dictionary-extra.json' if args.extra_terms else 'dictionary-sample.json' if args.limit else 'dictionary-reference.json')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'total': len(results), 'fetched': sum(row['fetch_status'] == 'ok' for row in results),
                      'hanja_match': sum(row.get('hanja_match', False) for row in results),
                      'with_definitions': sum(bool(row['entries']) for row in results),
                      'errors': [{'reading': row['reading'], 'error': row['error']} for row in results if row['fetch_status'] == 'error']}, ensure_ascii=False), flush=True)
    if any(row['fetch_status'] == 'error' for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
