import feedparser

def get_trade_news():
    urls = [
        "https://news.google.com/rss/search?q=Russia+import+trade&hl=en",
        "https://news.google.com/rss/search?q=Azerbaijan+import+economy&hl=en"
    ]

    all_news = []

    for url in urls:
        feed = feedparser.parse(url)

        for entry in feed.entries[:5]:
            all_news.append({
                "title": entry.title,
                "link": entry.link
            })

    return all_news
