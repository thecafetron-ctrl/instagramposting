"""
Viral Analyzer - AI-powered analysis to find the most viral moments in a video transcript.
Uses GPT to analyze transcript and identify high-engagement segments.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from typing import List, Optional
import hashlib

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("OpenAI not installed - using fallback viral analysis")


@dataclass
class ViralMoment:
    """A potential viral clip identified from the transcript."""
    start_time: float
    end_time: float
    duration: float
    text: str
    virality_score: int  # 1-100
    virality_reason: str
    suggested_caption: str
    suggested_hashtags: List[str]
    hook: str  # The attention-grabbing first line
    category: str  # e.g., "controversial", "emotional", "educational", "funny"
    

def get_openai_client() -> Optional['OpenAI']:
    """Get OpenAI client if API key is available."""
    if not HAS_OPENAI:
        return None
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.warning("OPENAI_API_KEY not set - using fallback analysis")
        return None
    
    return OpenAI(api_key=api_key)


def analyze_transcript_for_virality(
    transcript_words: List[dict],
    num_clips: int = 10,
    min_duration: float = 15,
    max_duration: float = 60,
) -> List[ViralMoment]:
    """
    Analyze transcript to find the most viral-worthy moments.
    
    Args:
        transcript_words: List of word objects with 'word', 'start', 'end' keys
        num_clips: Number of top clips to identify (will return more candidates)
        min_duration: Minimum clip duration in seconds
        max_duration: Maximum clip duration in seconds
    
    Returns:
        List of ViralMoment objects sorted by virality score (highest first)
    """
    client = get_openai_client()
    
    if client:
        return _analyze_with_gpt(client, transcript_words, num_clips, min_duration, max_duration)
    else:
        return _analyze_fallback(transcript_words, num_clips, min_duration, max_duration)


def _analyze_with_gpt(
    client: 'OpenAI',
    transcript_words: List[dict],
    num_clips: int,
    min_duration: float,
    max_duration: float,
) -> List[ViralMoment]:
    """Use GPT to find viral moments."""
    
    # Build transcript text with timestamps
    segments = []
    current_segment = {"start": 0, "text": "", "words": []}
    
    for word in transcript_words:
        current_segment["words"].append(word)
        current_segment["text"] += word.get("word", "") + " "
        
        # Create segments every ~30 seconds for analysis
        if word.get("end", 0) - current_segment["start"] > 30:
            current_segment["end"] = word.get("end", 0)
            current_segment["text"] = current_segment["text"].strip()
            segments.append(current_segment)
            current_segment = {"start": word.get("end", 0), "text": "", "words": []}
    
    # Don't forget the last segment
    if current_segment["text"].strip():
        current_segment["end"] = transcript_words[-1].get("end", 0) if transcript_words else 0
        current_segment["text"] = current_segment["text"].strip()
        segments.append(current_segment)
    
    # Format transcript for GPT
    transcript_for_gpt = "\n".join([
        f"[{s['start']:.1f}s - {s['end']:.1f}s]: {s['text']}"
        for s in segments
    ])
    
    prompt = f"""Analyze this video transcript and identify the {num_clips * 2} most viral-worthy moments for short-form content (TikTok/Reels/Shorts).

TRANSCRIPT:
{transcript_for_gpt}

For each moment, identify a segment that is {min_duration}-{max_duration} seconds long.

Look for:
- Controversial or hot takes
- Emotional peaks (excitement, surprise, anger)
- Quotable/shareable statements  
- Cliffhangers or curiosity gaps
- Educational "aha" moments
- Funny or relatable content
- Strong hooks that grab attention in first 3 seconds

Return ONLY valid JSON array (no markdown, no explanation):
[
  {{
    "start_time": 45.2,
    "end_time": 72.5,
    "text": "exact quote from transcript",
    "virality_score": 85,
    "virality_reason": "Why this will go viral - be specific about engagement triggers",
    "suggested_caption": "Caption for the post (with emojis)",
    "suggested_hashtags": ["viral", "trending", "topic"],
    "hook": "The attention-grabbing first line",
    "category": "controversial|emotional|educational|funny|relatable|shocking"
  }}
]

Sort by virality_score descending. Be specific about timestamps."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap
            messages=[
                {"role": "system", "content": "You are a viral content expert who identifies the most engaging moments in videos. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Clean up response (remove markdown if present)
        if content.startswith("```"):
            content = re.sub(r'^```json?\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        moments_data = json.loads(content)
        
        moments = []
        for m in moments_data:
            moments.append(ViralMoment(
                start_time=float(m.get("start_time", 0)),
                end_time=float(m.get("end_time", 0)),
                duration=float(m.get("end_time", 0)) - float(m.get("start_time", 0)),
                text=m.get("text", ""),
                virality_score=int(m.get("virality_score", 50)),
                virality_reason=m.get("virality_reason", ""),
                suggested_caption=m.get("suggested_caption", ""),
                suggested_hashtags=m.get("suggested_hashtags", []),
                hook=m.get("hook", ""),
                category=m.get("category", "general"),
            ))
        
        # Sort by score
        moments.sort(key=lambda x: x.virality_score, reverse=True)
        
        logger.info(f"GPT identified {len(moments)} viral moments")
        return moments
        
    except Exception as e:
        logger.exception(f"GPT analysis failed: {e}")
        return _analyze_fallback(transcript_words, num_clips, min_duration, max_duration)


def _analyze_fallback(
    transcript_words: List[dict],
    num_clips: int,
    min_duration: float,
    max_duration: float,
) -> List[ViralMoment]:
    """Fallback analysis without GPT - uses heuristics."""
    
    if not transcript_words:
        return []
    
    # Build sentences from words
    sentences = []
    current_sentence = {"start": 0, "end": 0, "text": "", "words": []}
    
    for word in transcript_words:
        word_text = word.get("word", "")
        current_sentence["words"].append(word)
        current_sentence["text"] += word_text + " "
        current_sentence["end"] = word.get("end", 0)
        
        if not current_sentence["start"]:
            current_sentence["start"] = word.get("start", 0)
        
        # Split on sentence endings
        if any(word_text.rstrip().endswith(p) for p in ['.', '!', '?']):
            current_sentence["text"] = current_sentence["text"].strip()
            if current_sentence["text"]:
                sentences.append(current_sentence)
            current_sentence = {"start": 0, "end": 0, "text": "", "words": []}
    
    # Add remaining text
    if current_sentence["text"].strip():
        current_sentence["text"] = current_sentence["text"].strip()
        sentences.append(current_sentence)
    
    # Score sentences based on heuristics
    viral_keywords = {
        "controversial": ["actually", "wrong", "truth", "secret", "nobody", "everyone", "always", "never"],
        "emotional": ["amazing", "incredible", "love", "hate", "worst", "best", "changed", "life"],
        "educational": ["how to", "why", "because", "learn", "tip", "hack", "strategy", "method"],
        "funny": ["literally", "imagine", "wait", "hilarious", "crazy", "insane"],
        "shocking": ["shocking", "unbelievable", "can't believe", "exposed", "revealed"],
    }
    
    def score_sentence(text: str) -> tuple:
        text_lower = text.lower()
        score = 50  # Base score
        category = "general"
        reasons = []
        
        # Check for viral keywords
        for cat, keywords in viral_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    score += 5
                    category = cat
                    reasons.append(f"Contains '{kw}'")
        
        # Longer sentences with good content score higher
        word_count = len(text.split())
        if 10 <= word_count <= 30:
            score += 10
            reasons.append("Good length")
        
        # Questions are engaging
        if "?" in text:
            score += 10
            reasons.append("Contains question")
        
        # Exclamations show emotion
        if "!" in text:
            score += 5
            reasons.append("Shows emotion")
        
        # Numbers are engaging
        if any(c.isdigit() for c in text):
            score += 5
            reasons.append("Contains numbers/stats")
        
        return min(score, 95), category, reasons
    
    # Create segments of appropriate length
    moments = []
    i = 0
    
    while i < len(sentences):
        segment_sentences = [sentences[i]]
        segment_start = sentences[i]["start"]
        segment_end = sentences[i]["end"]
        
        # Add more sentences until we hit min duration
        j = i + 1
        while j < len(sentences) and (segment_end - segment_start) < min_duration:
            segment_sentences.append(sentences[j])
            segment_end = sentences[j]["end"]
            j += 1
        
        # If too short, skip
        duration = segment_end - segment_start
        if duration < min_duration:
            i += 1
            continue
        
        # If too long, trim
        while duration > max_duration and len(segment_sentences) > 1:
            segment_sentences.pop()
            segment_end = segment_sentences[-1]["end"]
            duration = segment_end - segment_start
        
        # Build the segment
        text = " ".join(s["text"] for s in segment_sentences)
        score, category, reasons = score_sentence(text)
        
        # Generate simple caption and hashtags
        first_words = text.split()[:10]
        caption = " ".join(first_words) + "..." if len(text.split()) > 10 else text
        
        hashtags = ["viral", "fyp", "trending"]
        if category != "general":
            hashtags.append(category)
        
        moments.append(ViralMoment(
            start_time=segment_start,
            end_time=segment_end,
            duration=duration,
            text=text,
            virality_score=score,
            virality_reason=" | ".join(reasons) if reasons else "Potential engaging content",
            suggested_caption=f"🔥 {caption}",
            suggested_hashtags=hashtags,
            hook=first_words[0] if first_words else "",
            category=category,
        ))
        
        # Move to next segment (with some overlap for variety)
        i = j if j > i else i + 1
    
    # Sort by score
    moments.sort(key=lambda x: x.virality_score, reverse=True)
    
    # Return more candidates than requested so user can choose
    return moments[:num_clips * 3]


def get_video_cache_key(youtube_url: str) -> str:
    """Generate a cache key for a YouTube video URL."""
    # Extract video ID if possible
    video_id = None
    
    patterns = [
        r'(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, youtube_url)
        if match:
            video_id = match.group(1)
            break
    
    if video_id:
        return f"yt_{video_id}"
    
    # Fallback to URL hash
    return f"url_{hashlib.md5(youtube_url.encode()).hexdigest()[:12]}"
