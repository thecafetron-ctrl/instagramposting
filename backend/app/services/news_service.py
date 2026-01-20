"""
News discovery service for supply chain and logistics news.
Uses SerpAPI to find latest news articles.
"""

import httpx
import random
from datetime import datetime
from app.config import get_settings

settings = get_settings()

# News search queries for supply chain/logistics
NEWS_QUERIES = [
    "supply chain news today",
    "logistics industry news",
    "shipping freight news",
    "warehouse automation news",
    "global supply chain disruption",
    "freight transportation news",
    "ecommerce logistics news",
    "port shipping news",
    "trucking industry news",
    "air cargo freight news",
    "supply chain AI technology news",
    "retail logistics news",
    "last mile delivery news",
    "container shipping news",
]

# Categories for news posts
NEWS_CATEGORIES = [
    "SUPPLY CHAIN",
    "LOGISTICS",
    "FREIGHT",
    "SHIPPING",
    "TRANSPORTATION",
    "INDUSTRY NEWS",
    "BREAKING",
    "TECHNOLOGY",
]


async def search_news_serpapi(query: str = None) -> list[dict]:
    """
    Search for latest news using SerpAPI Google News.
    Returns list of news articles with title, snippet, source, link, and image.
    """
    serpapi_key = settings.serpapi_key
    
    if not serpapi_key:
        return get_fallback_news()
    
    if query is None:
        query = random.choice(NEWS_QUERIES)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Use Google News engine
            response = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": serpapi_key,
                    "engine": "google_news",
                    "gl": "us",
                    "hl": "en",
                }
            )
            response.raise_for_status()
            data = response.json()
            
            news_items = []
            
            # Extract from news results
            for result in data.get("news_results", [])[:10]:
                title = result.get("title", "")
                snippet = result.get("snippet", "") or result.get("description", "")
                source = result.get("source", {}).get("name", "")
                link = result.get("link", "")
                thumbnail = result.get("thumbnail", "")
                date = result.get("date", "")
                
                if title:
                    news_items.append({
                        "title": title,
                        "snippet": snippet,
                        "source": source,
                        "link": link,
                        "thumbnail": thumbnail,
                        "date": date,
                        "category": categorize_news(title, snippet),
                    })
            
            # If no news results, try organic results
            if not news_items:
                for result in data.get("organic_results", [])[:5]:
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")
                    
                    if title and is_news_relevant(title, snippet):
                        news_items.append({
                            "title": title,
                            "snippet": snippet,
                            "source": result.get("source", ""),
                            "link": result.get("link", ""),
                            "thumbnail": result.get("thumbnail", ""),
                            "date": "",
                            "category": categorize_news(title, snippet),
                        })
            
            return news_items if news_items else get_fallback_news()
            
        except Exception as e:
            print(f"SerpAPI News error: {e}")
            return get_fallback_news()


def is_news_relevant(title: str, snippet: str) -> bool:
    """Check if content is relevant to supply chain/logistics."""
    text = f"{title} {snippet}".lower()
    keywords = [
        "supply chain", "logistics", "freight", "shipping", "warehouse",
        "delivery", "transportation", "cargo", "port", "trucking",
        "inventory", "distribution", "fulfillment", "ecommerce"
    ]
    return any(kw in text for kw in keywords)


def categorize_news(title: str, snippet: str) -> str:
    """Categorize news based on content."""
    text = f"{title} {snippet}".lower()
    
    if any(kw in text for kw in ["port", "container", "ship", "ocean", "maritime"]):
        return "SHIPPING"
    elif any(kw in text for kw in ["truck", "freight", "carrier", "haul"]):
        return "FREIGHT"
    elif any(kw in text for kw in ["warehouse", "fulfillment", "inventory"]):
        return "LOGISTICS"
    elif any(kw in text for kw in ["ai", "automation", "technology", "robot"]):
        return "TECHNOLOGY"
    elif any(kw in text for kw in ["breaking", "urgent", "alert"]):
        return "BREAKING"
    elif any(kw in text for kw in ["air", "cargo", "flight"]):
        return "TRANSPORTATION"
    else:
        return "SUPPLY CHAIN"


def get_fallback_news() -> list[dict]:
    """Fallback news when API fails."""
    return [
        {
            "title": "Global Supply Chain Disruptions Continue to Impact Industries",
            "snippet": "Companies worldwide are adapting to ongoing supply chain challenges with new strategies and technologies.",
            "source": "Industry Report",
            "link": "",
            "thumbnail": "",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "category": "SUPPLY CHAIN",
        },
        {
            "title": "AI and Automation Reshaping Logistics Operations",
            "snippet": "Artificial intelligence is transforming how companies manage their supply chains and logistics operations.",
            "source": "Tech News",
            "link": "",
            "thumbnail": "",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "category": "TECHNOLOGY",
        },
        {
            "title": "Freight Rates Fluctuate Amid Market Uncertainty",
            "snippet": "Shipping and freight costs continue to see significant changes as the industry navigates economic pressures.",
            "source": "Freight Weekly",
            "link": "",
            "thumbnail": "",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "category": "FREIGHT",
        },
    ]


async def get_latest_news(count: int = 5) -> list[dict]:
    """Get multiple news items from different queries."""
    all_news = []
    queries_to_try = random.sample(NEWS_QUERIES, min(3, len(NEWS_QUERIES)))
    
    for query in queries_to_try:
        news = await search_news_serpapi(query)
        all_news.extend(news)
    
    # Deduplicate by title
    seen_titles = set()
    unique_news = []
    for item in all_news:
        title_lower = item["title"].lower()
        if title_lower not in seen_titles:
            seen_titles.add(title_lower)
            unique_news.append(item)
    
    return unique_news[:count]


def generate_news_caption(news_item: dict) -> str:
    """Generate Instagram caption for news post."""
    title = news_item.get("title", "")
    snippet = news_item.get("snippet", "")
    source = news_item.get("source", "")
    category = news_item.get("category", "SUPPLY CHAIN")
    
    caption = f"""🚨 {category} NEWS 🚨

{title}

{snippet}

This is what's happening in the logistics and supply chain industry right now.

Stay informed. Stay ahead.

Follow @structure for daily industry insights.

---

💬 What are your thoughts on this development?
Drop a comment below 👇

{source if source else ''}

#supplychain #logistics #news #freight #shipping #transportation #industry #business #supplychain management #logisticsnews #freightnews #shippingnews #industrynews #breakingnews #supplychainnews
"""
    return caption.strip()
