"""
Topic discovery service using SerpAPI to find fresh logistics + AI topics.
"""

import httpx
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import UsedTopic
from app.config import get_settings

settings = get_settings()

# Logistics + AI topic search queries
SEARCH_QUERIES = [
    "AI logistics automation 2024 2025",
    "machine learning supply chain optimization",
    "predictive analytics freight management",
    "AI warehouse operations problems",
    "logistics exception management automation",
    "supply chain visibility AI solutions",
    "carrier management artificial intelligence",
    "demand forecasting machine learning logistics",
    "AI inventory optimization challenges",
    "last mile delivery AI automation",
    "freight routing optimization AI",
    "logistics cost reduction artificial intelligence",
    "supply chain disruption prediction AI",
    "real-time logistics tracking AI",
    "automated carrier selection logistics",
]

# Curated logistics problem topics (fallback + supplementary)
CURATED_TOPICS = [
    "ETA prediction accuracy in freight logistics",
    "Carrier performance monitoring and selection",
    "Demand forecasting for inventory positioning",
    "Exception management in shipment tracking",
    "Last-mile delivery route optimization",
    "Warehouse slotting and pick path optimization",
    "Freight rate prediction and negotiation",
    "Supply chain visibility across multiple carriers",
    "Inventory rebalancing across distribution centers",
    "Dock scheduling and appointment management",
    "Returns processing and reverse logistics",
    "Cross-border compliance and documentation",
    "Temperature-controlled shipment monitoring",
    "Capacity planning during demand spikes",
    "Carrier invoice auditing and dispute resolution",
    "Order consolidation and shipment batching",
    "Real-time transit risk assessment",
    "Customer delivery promise accuracy",
    "Freight claim prediction and prevention",
    "Multi-modal transportation optimization",
    "Supplier lead time variability management",
    "Safety stock optimization with demand sensing",
    "Network design and facility location",
    "Labor planning for warehouse operations",
    "Parcel carrier selection optimization",
    "Predictive maintenance for fleet management",
    "Load optimization and trailer utilization",
    "Seasonal demand pattern recognition",
    "Backorder prioritization and allocation",
    "Customer segmentation for delivery tiers",
]


async def get_used_topics(db: AsyncSession, window: int = None) -> set[str]:
    """Get topics used in the last N posts."""
    if window is None:
        window = settings.deduplication_window
    
    cutoff = datetime.utcnow() - timedelta(days=window)
    
    result = await db.execute(
        select(UsedTopic.topic)
        .where(UsedTopic.created_at >= cutoff)
    )
    
    return {row[0].lower() for row in result.fetchall()}


async def search_topics_serpapi(query: str) -> list[dict]:
    """Search for topics using SerpAPI."""
    serpapi_key = settings.serpapi_key
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": serpapi_key,
                    "engine": "google",
                    "num": 10,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            topics = []
            
            # Extract from organic results
            for result in data.get("organic_results", []):
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                
                # Extract topic from title/snippet
                topic = extract_topic_from_text(title, snippet)
                if topic:
                    topics.append({
                        "topic": topic,
                        "source": "serpapi",
                        "context": snippet[:200] if snippet else ""
                    })
            
            return topics
            
        except Exception as e:
            print(f"SerpAPI error: {e}")
            return []


def extract_topic_from_text(title: str, snippet: str) -> str | None:
    """Extract a clean logistics topic from search result text."""
    # Keywords that indicate logistics relevance
    logistics_keywords = [
        "logistics", "supply chain", "freight", "shipping", "warehouse",
        "delivery", "carrier", "inventory", "transportation", "distribution",
        "fulfillment", "tracking", "routing", "fleet", "shipment"
    ]
    
    ai_keywords = [
        "AI", "artificial intelligence", "machine learning", "ML", "predictive",
        "automation", "automated", "intelligent", "smart", "optimization"
    ]
    
    text = f"{title} {snippet}".lower()
    
    # Check for logistics + AI relevance
    has_logistics = any(kw in text for kw in logistics_keywords)
    has_ai = any(kw in text.lower() for kw in ai_keywords)
    
    if has_logistics and has_ai:
        # Clean up the title as the topic
        topic = title.strip()
        # Remove common prefixes/suffixes
        for remove in ["How ", "What ", "Why ", " - ", " | ", "..."]:
            topic = topic.replace(remove, " ")
        topic = " ".join(topic.split())[:100]
        return topic if len(topic) > 10 else None
    
    return None


def normalize_topic(topic: str) -> str:
    """Normalize topic for comparison."""
    return " ".join(topic.lower().split())


async def discover_fresh_topic(db: AsyncSession, allow_reuse: bool = False) -> dict:
    """
    Discover a fresh logistics + AI topic.
    Returns dict with 'topic' and optional 'enrichment' data.
    """
    used_topics = set() if allow_reuse else await get_used_topics(db)
    
    # Try SerpAPI first
    import random
    search_query = random.choice(SEARCH_QUERIES)
    
    serpapi_topics = await search_topics_serpapi(search_query)
    
    # Filter out used topics
    for item in serpapi_topics:
        normalized = normalize_topic(item["topic"])
        if normalized not in used_topics:
            return {
                "topic": item["topic"],
                "enrichment": {
                    "source": "serpapi",
                    "context": item.get("context", ""),
                    "search_query": search_query
                }
            }
    
    # Fallback to curated topics
    random.shuffle(CURATED_TOPICS)
    for topic in CURATED_TOPICS:
        normalized = normalize_topic(topic)
        if normalized not in used_topics:
            return {
                "topic": topic,
                "enrichment": {
                    "source": "curated",
                    "context": ""
                }
            }
    
    # All topics exhausted
    if allow_reuse:
        # Pick random curated topic
        return {
            "topic": random.choice(CURATED_TOPICS),
            "enrichment": {
                "source": "curated_reuse",
                "context": ""
            }
        }
    
    raise ValueError(
        f"All {len(CURATED_TOPICS)} topics have been used in the last {settings.deduplication_window} days. "
        "Set allow_reuse=True or wait for topic expiration."
    )


async def record_used_topic(db: AsyncSession, topic: str, post_id: int):
    """Record a topic as used."""
    used_topic = UsedTopic(
        topic=topic,
        post_id=post_id
    )
    db.add(used_topic)
    await db.commit()
