import os
import requests
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file
API_KEY = os.getenv("NEWS_API_KEY")  # Load API key from .env

def gather_news(query="Palantir", num_articles=5):
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&language=en&pageSize={num_articles}&apiKey={API_KEY}"

    response = requests.get(url)
    articles = response.json().get("articles", [])

    results = []
    for article in articles:
        title = article.get("title", "")
        description = article.get("description", "")
        article_url = article.get("url", "")
        results.append(f"📰 {title}\n{description}\n🔗 {article_url}\n")

    return results

