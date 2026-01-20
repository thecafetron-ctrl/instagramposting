"""
News discovery service for supply chain and logistics news.
Uses SerpAPI to find latest news articles.
Uses OpenAI to generate engaging hook headlines.
"""

import httpx
import random
from datetime import datetime
from openai import AsyncOpenAI
from app.config import get_settings

settings = get_settings()


async def generate_hook_headline(original_title: str, snippet: str = "") -> str:
    """
    Use OpenAI to generate an engaging hook headline from the news.
    Makes it punchy, attention-grabbing, and suitable for Instagram.
    """
    if not settings.openai_api_key:
        return original_title
    
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        prompt = f"""Transform this news headline into a punchy, attention-grabbing Instagram hook.

Original headline: {original_title}
Context: {snippet[:200] if snippet else 'N/A'}

Requirements:
- Maximum 12 words
- Make it dramatic and engaging
- Use power words that grab attention
- Keep it factual but compelling
- No clickbait, but make people want to read more
- Focus on the impact or significance
- ALL CAPS style

Examples of good hooks:
- "AMAZON JUST CHANGED EVERYTHING FOR SUPPLY CHAINS"
- "THIS IS WHY SHIPPING COSTS ARE EXPLODING"
- "THE AI REVOLUTION HITTING LOGISTICS RIGHT NOW"
- "GLOBAL TRADE CRISIS: WHAT YOU NEED TO KNOW"

Return ONLY the new headline, nothing else."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.8,
        )
        
        hook = response.choices[0].message.content.strip()
        # Clean up any quotes
        hook = hook.strip('"\'')
        return hook.upper()
        
    except Exception as e:
        print(f"OpenAI hook generation error: {e}")
        return original_title.upper()

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

---

Here's what this means for the industry:

This development is a significant shift in how supply chains and logistics operations are evolving. Companies across the globe are watching closely as these changes could reshape how goods move from manufacturers to consumers.

The implications extend beyond just operational efficiency. We're seeing a fundamental transformation in:

📦 Inventory management strategies
🚛 Transportation and freight networks  
🏭 Warehouse automation systems
📊 Real-time tracking and visibility
💰 Cost structures across the supply chain

For businesses that adapt quickly, this represents an opportunity to gain competitive advantage. For those that don't, it could mean falling behind in an increasingly fast-paced market.

---

At STRUCTURE, we help logistics companies navigate these exact challenges. Our AI-powered solutions are designed to turn industry disruptions into operational advantages.

Whether it's optimizing routes, predicting demand, or automating warehouse operations – we're building the technology that keeps supply chains moving.

---

💬 What's your take on this news?
How is your company adapting to these changes?
Drop a comment below 👇

📌 Save this post for reference
🔔 Follow @structurelogistics for daily industry insights

{f'Source: {source}' if source else ''}

#supplychain #logistics #supplychainnews #logisticsnews #freight #shipping #transportation #warehouseautomation #supplychain management #businessnews #industrynews #ecommerce #lastmiledelivery #freighttech #logisticstech #ai #automation #futureoflogistics #supplychainmanagement #operations #businessgrowth #innovation #disruption #technology
"""
    return caption.strip()


async def generate_ai_news_caption(news_item: dict) -> str:
    """Use OpenAI to generate a detailed, engaging caption about the news."""
    if not settings.openai_api_key:
        return generate_news_caption(news_item)
    
    title = news_item.get("title", "")
    snippet = news_item.get("snippet", "")
    source = news_item.get("source", "")
    category = news_item.get("category", "SUPPLY CHAIN")
    
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        prompt = f"""Write a comprehensive Instagram caption about this supply chain/logistics news.

NEWS HEADLINE: {title}
DETAILS: {snippet}
SOURCE: {source}
CATEGORY: {category}

Requirements:
1. Start with "🚨 {category} NEWS 🚨" and the headline
2. Explain what this news actually means in 2-3 detailed paragraphs
3. Discuss the implications for the logistics industry
4. Include specific impacts on: shipping, warehousing, costs, technology
5. Add a section about how AI and automation relate to this
6. End with a call to action asking for thoughts
7. Include "Follow @structurelogistics for daily industry insights"
8. Add relevant hashtags at the end (20+ hashtags)
9. Make it 400-500 words total
10. Use line breaks between paragraphs
11. Include emojis strategically (📦🚛🏭📊💰 etc)
12. Sound professional but engaging

Return ONLY the caption, no explanations."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7,
        )
        
        caption = response.choices[0].message.content.strip()
        return caption
        
    except Exception as e:
        print(f"OpenAI caption generation error: {e}")
        return generate_news_caption(news_item)
