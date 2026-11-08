
import json
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

OUTPUT = Path("data/news.json")


def fetch_news(query):
    params = urllib.parse.urlencode({
        "q": query,
        "hl": "en",
        "gl": "US",
        "ceid": "US:en",
    })
    url = "https://news.google.com/rss/search?" + params

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(
        request, timeout=20
    ) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    results = []

    for item in root.findall("./channel/item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        published = item.findtext("pubDate", "")
        source = item.findtext("source", "")

        try:
            dt = parsedate_to_datetime(published)
            published_iso = dt.astimezone(
                timezone.utc
            ).isoformat()
        except (TypeError, ValueError):
            published_iso = None

        if title and link:
            results.append({
                "title": title,
                "url": link,
                "source": source,
                "published_utc": published_iso,
                "query": query,
                "verification": "unverified",
            })

    return results


def main():
    articles = {}
    errors = []

    for query in QUERIES:
        try:
            for article in fetch_news(query):
                key = article["url"]
                articles[key] = article
            print(f"OK: {query}")
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            print(f"ERROR: {query}: {exc}")

    if not articles:
        raise RuntimeError(
            "No articles retrieved. Existing data preserved."
        )

    news = sorted(
        articles.values(),
        key=lambda x: x["published_utc"] or "",
        reverse=True
    )[:100]

    payload = {
        "generated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "RAW_NEWS_NOT_VERIFIED",
        "articles": news,
        "errors": errors,
    }

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(f"Saved {len(news)} articles to {OUTPUT}")


if __name__ == "__main__":
    main()
