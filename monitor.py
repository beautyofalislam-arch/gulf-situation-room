import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

QUERIES = [
    '"Iran" "CENTCOM"',
    '"Iran" "Pentagon" military',
    '"Iran" "Qatar" security',
    '"Strait of Hormuz" tanker',
    '"UKMTO" Gulf incident',
    '"Ras Laffan" OR "Mesaieed" security',
]
OUTPUT = Path('data/news.json')


def fetch_news(query):
    params = urllib.parse.urlencode({'q': query, 'hl': 'en', 'gl': 'US', 'ceid': 'US:en'})
    req = urllib.request.Request('https://news.google.com/rss/search?' + params,
                                 headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        root = ET.fromstring(response.read())
    results = []
    for item in root.findall('./channel/item'):
        title = item.findtext('title', '').strip()
        link = item.findtext('link', '').strip()
        published = item.findtext('pubDate', '')
        source = item.findtext('source', '')
        try:
            published_iso = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            published_iso = None
        if title and link:
            results.append({'title': title, 'url': link, 'source': source,
                            'published_utc': published_iso, 'query': query,
                            'verification': 'unverified'})
    return results


def translate_title(title):
    """Unofficial public endpoint; may fail or rate-limit. Original is retained."""
    params = urllib.parse.urlencode({'client': 'gtx', 'sl': 'auto', 'tl': 'id',
                                     'dt': 't', 'q': title})
    req = urllib.request.Request('https://translate.googleapis.com/translate_a/single?' + params,
                                 headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=8) as response:
        data = json.load(response)
    translated = ''.join(segment[0] for segment in data[0] if segment and segment[0]).strip()
    if not translated:
        raise ValueError('Empty translation')
    return translated


def previous_translations():
    if not OUTPUT.exists():
        return {}
    try:
        old = json.loads(OUTPUT.read_text(encoding='utf-8'))
        return {a['title']: a['title_id'] for a in old.get('articles', [])
                if a.get('title') and a.get('title_id')
                and a.get('translation_status') == 'translated'}
    except (OSError, ValueError):
        return {}


def main():
    articles = {}
    errors = []
    for query in QUERIES:
        try:
            for article in fetch_news(query):
                articles[article['url']] = article
            print(f'OK: {query}')
        except Exception as exc:
            errors.append(f'{query}: {exc}')
            print(f'ERROR: {query}: {exc}')
    if not articles:
        raise RuntimeError('No articles retrieved. Existing data preserved.')
    news = sorted(articles.values(), key=lambda x: x['published_utc'] or '', reverse=True)[:100]
    cache = previous_translations()
    translated_count = 0
    for article in news:
        original = article['title']
        article['title_original'] = original
        if original in cache:
            article['title_id'] = cache[original]
            article['translation_status'] = 'translated'
            translated_count += 1
            continue
        try:
            article['title_id'] = translate_title(original)
            article['translation_status'] = 'translated'
            translated_count += 1
            time.sleep(0.15)
        except Exception as exc:
            article['title_id'] = original
            article['translation_status'] = 'unavailable'
            print(f'Translation unavailable: {type(exc).__name__}')
    print(f'Indonesian titles: {translated_count}/{len(news)}')
    payload = {'generated_utc': datetime.now(timezone.utc).isoformat(),
               'status': 'RAW_NEWS_NOT_VERIFIED', 'articles': news, 'errors': errors}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved {len(news)} articles to {OUTPUT}')


if __name__ == '__main__':
    main()
