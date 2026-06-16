def analyze_news(news_list):
    keywords = ["import", "trade", "customs", "supply", "energy", "food"]

    insights = []
    opportunities = []

    for news in news_list:
        title = news["title"].lower()

        if any(k in title for k in keywords):
            insights.append("📦 " + news["title"])

            if "food" in title or "wheat" in title:
                opportunities.append("✔ صادرات کشاورزی ایران")
            if "energy" in title or "oil" in title:
                opportunities.append("✔ صادرات انرژی ایران")
            if "metal" in title or "steel" in title:
                opportunities.append("✔ صادرات فولاد ایران")

    return insights, list(set(opportunities))
