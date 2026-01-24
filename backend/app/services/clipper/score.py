"""Scoring module - ranks candidate clips by engagement potential."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .segment import CandidateClip

logger = logging.getLogger(__name__)

BOOST_KEYWORDS = {
    'secret', 'hack', 'trick', 'amazing', 'incredible', 'insane', 'crazy',
    'mind-blowing', 'shocking', 'revealed', 'never', 'always', 'best',
    'worst', 'first', 'last', 'only', 'must', 'need', 'important',
    'love', 'hate', 'fear', 'excited', 'surprised', 'angry', 'happy',
    'sad', 'funny', 'hilarious', 'beautiful', 'terrible', 'awesome',
    'now', 'today', 'stop', 'start', 'watch', 'listen', 'look',
    'wait', 'learn', 'discover', 'find', 'get', 'make', 'try',
    'why', 'how', 'what', 'when', 'where', 'who', 'which',
    'one', 'two', 'three', 'five', 'ten', 'hundred', 'thousand',
    'but', 'however', 'actually', 'really', 'literally', 'basically',
}

GOOD_START_PATTERNS = [
    r'^(so|okay|alright|now|here)',
    r'^(the thing is|here\'s the|let me)',
    r'^(this is|that\'s|it\'s)',
    r'^(number \d|first|second|third)',
    r'^(i\'m going to|we\'re going to|you need to)',
]

GOOD_END_PATTERNS = [
    r'[.!?]$',
    r'right\?$',
    r'you know\?$',
]


@dataclass
class ScoredClip:
    """A candidate clip with scoring information."""
    clip: CandidateClip
    total_score: float
    speaking_rate_score: float
    keyword_score: float
    structure_score: float
    duration_score: float
    
    @property
    def start(self) -> float:
        return self.clip.start
    
    @property
    def end(self) -> float:
        return self.clip.end
    
    @property
    def duration(self) -> float:
        return self.clip.duration
    
    @property
    def text(self) -> str:
        return self.clip.text
    
    @property
    def words(self):
        return self.clip.words


def score_clips(clips: list[CandidateClip]) -> list[ScoredClip]:
    """Score candidate clips for engagement potential."""
    scored = []
    
    for clip in clips:
        speaking_rate_score = _score_speaking_rate(clip)
        keyword_score = _score_keywords(clip)
        structure_score = _score_structure(clip)
        duration_score = _score_duration(clip)
        
        total = (
            speaking_rate_score * 0.20 +
            keyword_score * 0.35 +
            structure_score * 0.25 +
            duration_score * 0.20
        )
        
        scored.append(ScoredClip(
            clip=clip,
            total_score=total,
            speaking_rate_score=speaking_rate_score,
            keyword_score=keyword_score,
            structure_score=structure_score,
            duration_score=duration_score,
        ))
    
    scored.sort(key=lambda x: x.total_score, reverse=True)
    
    logger.info(f"Scored {len(scored)} clips")
    return scored


def select_top_clips(
    scored_clips: list[ScoredClip],
    n: int = 10,
    min_gap: float = 5.0,
) -> list[ScoredClip]:
    """Select top N clips, avoiding overlapping segments."""
    selected = []
    
    for clip in scored_clips:
        if len(selected) >= n:
            break
        
        overlaps = False
        for sel in selected:
            if _clips_overlap(clip, sel, min_gap):
                overlaps = True
                break
        
        if not overlaps:
            selected.append(clip)
    
    logger.info(f"Selected {len(selected)} clips from {len(scored_clips)} candidates")
    return selected


def _score_speaking_rate(clip: CandidateClip) -> float:
    if clip.duration <= 0:
        return 0.0
    
    wps = clip.word_count / clip.duration
    
    if 2.5 <= wps <= 3.5:
        return 1.0
    elif 2.0 <= wps < 2.5 or 3.5 < wps <= 4.0:
        return 0.8
    elif 1.5 <= wps < 2.0 or 4.0 < wps <= 4.5:
        return 0.5
    else:
        return 0.2


def _score_keywords(clip: CandidateClip) -> float:
    text_lower = clip.text.lower()
    words_in_clip = set(re.findall(r'\b\w+\b', text_lower))
    
    matches = words_in_clip & BOOST_KEYWORDS
    
    if not matches:
        return 0.3
    
    keyword_count = len(matches)
    score = min(1.0, 0.3 + keyword_count * 0.15)
    
    return score


def _score_structure(clip: CandidateClip) -> float:
    text = clip.text.strip()
    text_lower = text.lower()
    
    score = 0.5
    
    for pattern in GOOD_START_PATTERNS:
        if re.match(pattern, text_lower):
            score += 0.25
            break
    
    for pattern in GOOD_END_PATTERNS:
        if re.search(pattern, text_lower):
            score += 0.25
            break
    
    first_word = text.split()[0] if text else ""
    if first_word and first_word[0].islower() and first_word not in ['i', 'iPhone', 'iPad']:
        score -= 0.2
    
    sentence_count = len(re.findall(r'[.!?]+', text))
    if sentence_count >= 2:
        score += 0.1
    
    return max(0.0, min(1.0, score))


def _score_duration(clip: CandidateClip) -> float:
    duration = clip.duration
    
    if 25 <= duration <= 45:
        return 1.0
    elif 20 <= duration < 25 or 45 < duration <= 55:
        return 0.8
    elif 15 <= duration < 20 or 55 < duration <= 60:
        return 0.6
    else:
        return 0.3


def _clips_overlap(clip1: ScoredClip, clip2: ScoredClip, min_gap: float) -> bool:
    if clip1.end + min_gap <= clip2.start:
        return False
    if clip2.end + min_gap <= clip1.start:
        return False
    return True
