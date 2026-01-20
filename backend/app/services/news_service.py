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
    Use OpenAI to improve headline ONLY if needed.
    Keeps good headlines, fixes unclear ones. No exclamation marks.
    User should understand what happened just by reading the title.
    """
    if not settings.openai_api_key:
        return original_title.upper()
    
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        prompt = f"""Evaluate and possibly improve this news headline for an Instagram news post.

Original headline: {original_title}
Context: {snippet[:300] if snippet else 'N/A'}

CRITICAL RULES:
1. The headline must clearly tell the reader WHAT HAPPENED - they should understand the news just from reading it
2. NO exclamation marks ever
3. Maximum 10 words
4. ALL CAPS
5. If the original headline is already clear and explanatory, KEEP IT (just make it ALL CAPS)
6. Only change it if it's vague, clickbaity, or doesn't explain what actually happened
7. Be factual and specific - include key details (company names, numbers, locations if relevant)
8. No hype words, no clickbait, no "THIS IS WHY" style hooks

GOOD HEADLINES (clear, tells you what happened):
- "AMAZON CUTS 18000 WAREHOUSE JOBS AMID SLOWDOWN"
- "OCEAN FREIGHT RATES DROP 40 PERCENT FROM PEAK"
- "NEW AI SYSTEM PREDICTS SUPPLY CHAIN DELAYS"
- "PORT OF LA CLEARS CONTAINER BACKLOG"

BAD HEADLINES (vague, clickbait, doesn't explain):
- "THIS CHANGES EVERYTHING FOR SHIPPING!" (vague, exclamation)
- "YOU WON'T BELIEVE WHAT HAPPENED" (clickbait)
- "MAJOR NEWS FOR LOGISTICS" (doesn't say what)

Return ONLY the final headline in ALL CAPS, nothing else."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.3,  # Lower temp for more factual output
        )
        
        hook = response.choices[0].message.content.strip()
        hook = hook.strip('"\'')
        # Remove any exclamation marks
        hook = hook.replace('!', '')
        return hook.upper()
        
    except Exception as e:
        print(f"OpenAI hook generation error: {e}")
        return original_title.upper().replace('!', '')


async def select_most_viral_topic(news_items: list[dict]) -> dict:
    """
    Use AI to select the news item most likely to go viral on Instagram.
    """
    if not settings.openai_api_key or not news_items:
        return news_items[0] if news_items else None
    
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Format news items for AI
        news_list = "\n".join([
            f"{i+1}. {item['title']} - {item.get('snippet', '')[:100]}"
            for i, item in enumerate(news_items[:10])
        ])
        
        prompt = f"""From these supply chain/logistics news items, pick the ONE most likely to go viral on Instagram.

Consider:
- Broad appeal (affects many people/businesses)
- Surprising or significant impact
- Clear, easy to understand
- Timely and relevant
- Would make people want to share/comment

NEWS ITEMS:
{news_list}

Return ONLY the number (1-{min(10, len(news_items))}) of the best item, nothing else."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.3,
        )
        
        result = response.choices[0].message.content.strip()
        # Extract number
        import re
        match = re.search(r'\d+', result)
        if match:
            index = int(match.group()) - 1
            if 0 <= index < len(news_items):
                return news_items[index]
        
        return news_items[0]
        
    except Exception as e:
        print(f"Viral topic selection error: {e}")
        return news_items[0] if news_items else None

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


async def search_news_serpapi(query: str = None, time_range: str = "1d") -> list[dict]:
    """
    Search for latest news using SerpAPI Google News.
    Returns list of news articles with title, snippet, source, link, and image.
    
    time_range options: today, 1d, 3d, 1w, 2w, 4w, anytime
    """
    serpapi_key = settings.serpapi_key
    
    if not serpapi_key:
        return get_fallback_news()
    
    if query is None:
        query = random.choice(NEWS_QUERIES)
    
    # Map time_range to SerpAPI tbs parameter
    time_params = {
        "today": "qdr:d",      # Past 24 hours
        "1d": "qdr:d",         # Past day
        "3d": "qdr:d3",        # Past 3 days (custom)
        "1w": "qdr:w",         # Past week
        "2w": "qdr:w2",        # Past 2 weeks (custom)
        "4w": "qdr:m",         # Past month
        "anytime": None,       # No filter
    }
    
    tbs = time_params.get(time_range, "qdr:d")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Build params
            params = {
                "q": query,
                "api_key": serpapi_key,
                "engine": "google_news",
                "gl": "us",
                "hl": "en",
            }
            
            # Add time filter if specified
            if tbs:
                params["tbs"] = tbs
            
            # Use Google News engine
            response = await client.get(
                "https://serpapi.com/search",
                params=params
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
    """Generate Instagram caption for news post - no emoji header."""
    title = news_item.get("title", "")
    snippet = news_item.get("snippet", "")
    source = news_item.get("source", "")
    
    caption = f"""{snippet}

This development is reshaping how supply chains and logistics operations evolve globally. Companies are watching closely as these changes affect how goods move from manufacturers to consumers.

The implications go beyond operational efficiency:

📦 Inventory management strategies are shifting
🚛 Transportation networks are adapting  
🏭 Warehouse automation is accelerating
📊 Real-time visibility is becoming essential
💰 Cost structures are being restructured

For businesses that move quickly, this is an opportunity. For those that don't adapt, it means falling behind.

At STRUCTURE, we help logistics companies navigate these challenges with AI-powered solutions that turn disruption into advantage.

💬 What's your take on this?
Drop a comment below 👇

Follow @structurelogistics for daily industry insights

{f'Source: {source}' if source else ''}

#supplychain #logistics #supplychainnews #freight #shipping #transportation #warehouseautomation #businessnews #industrynews #ecommerce #lastmiledelivery #freighttech #logisticstech #automation #supplychainmanagement #operations #innovation #technology
"""
    return caption.strip()


async def select_most_viral_topic(news_items: list) -> dict:
    """Use AI to select the most viral/engaging news topic from a list."""
    if not news_items:
        return None
    
    if len(news_items) == 1:
        return news_items[0]
    
    if not settings.openai_api_key:
        # Without AI, just pick the first one
        return news_items[0]
    
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Format news items for AI
        items_text = "\n".join([
            f"{i+1}. {item['title']} ({item.get('source', 'Unknown')})"
            for i, item in enumerate(news_items[:10])
        ])
        
        prompt = f"""Select the news item that would be MOST engaging for a logistics/supply chain Instagram audience.

Consider:
- Viral potential (surprising, important, or dramatic)
- Relevance to logistics professionals
- Clear impact on the industry
- Timely and actionable information

News items:
{items_text}

Return ONLY the number (1, 2, 3, etc.) of the best item. Nothing else."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.3,
        )
        
        choice = response.choices[0].message.content.strip()
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(news_items):
                return news_items[index]
        except ValueError:
            pass
        
        return news_items[0]
        
    except Exception as e:
        print(f"Error selecting viral topic: {e}")
        return news_items[0]


async def generate_ai_news_caption(news_item: dict) -> str:
    """Use OpenAI to generate a detailed, engaging caption about the news."""
    if not settings.openai_api_key:
        return generate_news_caption(news_item)
    
    title = news_item.get("title", "")
    snippet = news_item.get("snippet", "")
    source = news_item.get("source", "")
    link = news_item.get("link", "")
    
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        prompt = f"""Write a comprehensive Instagram caption about this supply chain/logistics news.

NEWS HEADLINE: {title}
DETAILS: {snippet}
SOURCE: {source}

CRITICAL REQUIREMENTS:
1. DO NOT start with any emoji header like "🚨 NEWS 🚨" - just start directly with the content
2. First paragraph: Summarize what actually happened based on the details provided. Be accurate and factual.
3. Second paragraph: Explain what this means for businesses and the logistics industry
4. Third paragraph: Discuss the broader implications (costs, efficiency, technology, etc)
5. Use bullet points with emojis for key impacts (📦🚛🏭📊💰)
6. End with "Follow @structurelogistics for daily industry insights"
7. Add 15-20 relevant hashtags at the end
8. Make it 300-400 words total
9. Use line breaks between paragraphs
10. Be professional but engaging
11. Use ACCURATE information from the provided details - don't make things up

Return ONLY the caption text, nothing else."""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.5,
        )
        
        caption = response.choices[0].message.content.strip()
        return caption
        
    except Exception as e:
        print(f"OpenAI caption generation error: {e}")
        return generate_news_caption(news_item)
