"""
Content generation service using OpenAI to create carousel post content.
Supports variable slide counts (4-10 slides).
"""

import json
from openai import AsyncOpenAI
from app.config import get_settings
from app.templates import get_template

settings = get_settings()

client = AsyncOpenAI(
    api_key=settings.openai_api_key
)

BRAND_NAME = settings.brand_name


def build_system_prompt(template: dict) -> str:
    """Build the system prompt for content generation."""
    return f"""You are an expert B2B content strategist specializing in logistics and supply chain technology.
You write for executive decision-makers at logistics companies.

VOICE & TONE:
- Executive, direct, practical
- No emojis ever
- No hype language (no "revolutionary", "game-changing", "cutting-edge")
- Use specific, concrete language
- Write like a senior consultant presenting to a VP of Operations

BRAND: {BRAND_NAME}
- All CTAs must use: Comment "{BRAND_NAME}"
- The brand helps logistics companies deploy AI

TEMPLATE STYLE: {template['name']}
- {template['description']}

OUTPUT FORMAT:
You must respond with valid JSON only. No markdown, no explanation, just the JSON object.
"""


def build_generation_prompt(template: dict, topic: str, slide_count: int, enrichment: dict = None) -> str:
    """Build the user prompt for generating carousel content with variable slides."""
    prompts = template["prompts"]
    
    enrichment_context = ""
    if enrichment and enrichment.get("context"):
        enrichment_context = f"\nAdditional context about this topic: {enrichment['context']}"
        enrichment_context += "\nUse phrases like 'commonly shows up as' or 'often manifests as' rather than absolute claims."
    
    # Calculate how many middle slides we need
    middle_slides = slide_count - 2  # First and last are fixed
    
    # Build dynamic slide structure for the prompt
    middle_slide_instructions = ""
    middle_slide_json = ""
    
    for i in range(2, slide_count):  # Slides 2 through (slide_count - 1)
        slide_num = i
        if slide_num == 2:
            # First middle slide is always the problem intro - RICH CONTENT
            middle_slide_instructions += f"""
SLIDE {slide_num} (Problem introduction - FILL THE PAGE):
- intro: {prompts['intro']} Write 3-4 detailed sentences explaining the problem.
- bullets: 5-6 bullet points about specific problems/challenges. Each bullet should be a complete sentence.
- emphasis_line: {prompts['emphasis']} A powerful 1-2 sentence statement.
- explanation: 2-3 more sentences about why this matters.
IMPORTANT: This slide needs LOTS of content to fill the page. Don't be brief.
"""
            middle_slide_json += f'''
    "slide_{slide_num}": {{
        "type": "problem",
        "intro": "Detailed 3-4 sentence introduction paragraph about the problem.",
        "bullets": ["Complete sentence bullet 1", "Complete sentence bullet 2", "Complete sentence bullet 3", "Complete sentence bullet 4", "Complete sentence bullet 5"],
        "emphasis_line": "Bold emphasis statement that grabs attention.",
        "explanation": "2-3 more sentences explaining the root cause and why this matters to logistics teams."
    }},'''
        elif slide_num == slide_count - 1:
            # Last middle slide is always the solution with punchline - RICH CONTENT
            middle_slide_instructions += f"""
SLIDE {slide_num} (Solution outcomes - FILL THE PAGE):
- section_header: "{template['slide_3']['section_2_header']}"
- intro: 2-3 sentences introducing the outcomes
- outcomes: 5-6 specific outcomes/benefits. Each should be a complete sentence describing the transformation.
- punchline: Bold 2-3 sentence closing statement about transformation
IMPORTANT: This slide needs LOTS of content to fill the page. Don't be brief.
"""
            middle_slide_json += f'''
    "slide_{slide_num}": {{
        "type": "outcomes",
        "section_header": "{template['slide_3']['section_2_header']}",
        "intro": "2-3 sentences introducing what changes when AI is deployed.",
        "outcomes": ["Complete outcome 1", "Complete outcome 2", "Complete outcome 3", "Complete outcome 4", "Complete outcome 5"],
        "punchline": "Bold 2-3 sentence closing statement about the transformation this enables."
    }},'''
        elif slide_num == 3 or (middle_slides > 2 and slide_num == 3):
            # Slide 3 is usually mechanisms/how AI fixes - RICH CONTENT
            middle_slide_instructions += f"""
SLIDE {slide_num} (How AI fixes this - FILL THE PAGE):
- section_header: "{template['slide_3']['section_1_header']}"
- intro: 2-3 sentences introducing the AI solution approach
- mechanisms: 4 numbered mechanisms. Each has a title and 2-3 sentence description explaining how it works.
IMPORTANT: This slide needs LOTS of content to fill the page. Make descriptions detailed.
"""
            middle_slide_json += f'''
    "slide_{slide_num}": {{
        "type": "mechanisms",
        "section_header": "{template['slide_3']['section_1_header']}",
        "intro": "2-3 sentences about how AI approaches this problem differently.",
        "mechanisms": [
            {{"title": "Mechanism 1 name", "description": "2-3 detailed sentences explaining how this works."}},
            {{"title": "Mechanism 2 name", "description": "2-3 detailed sentences explaining how this works."}},
            {{"title": "Mechanism 3 name", "description": "2-3 detailed sentences explaining how this works."}},
            {{"title": "Mechanism 4 name", "description": "2-3 detailed sentences explaining how this works."}}
        ]
    }},'''
        else:
            # Additional middle slides - MORE content, not spread content
            if slide_num % 2 == 0:
                # Even slides: deep dive into specific problems
                middle_slide_instructions += f"""
SLIDE {slide_num} (Deep dive - Why this matters - FILL THE PAGE):
- header: "Why This Matters" or similar relevant header
- intro: 3-4 sentences explaining the deeper impact
- key_points: 5-6 bullet points with specific impacts, statistics, or consequences. Each should be a complete sentence.
- closing: 2-3 sentences summarizing the urgency
IMPORTANT: This is an ADDITIONAL slide with NEW content. Don't repeat previous slides. Fill the entire page.
"""
                middle_slide_json += f'''
    "slide_{slide_num}": {{
        "type": "context",
        "header": "Why This Matters",
        "intro": "3-4 detailed sentences explaining the deeper business impact.",
        "key_points": ["Impact point 1", "Impact point 2", "Impact point 3", "Impact point 4", "Impact point 5"],
        "closing": "2-3 sentences about why action is needed now."
    }},'''
            else:
                # Odd slides: more implementation/solution details
                middle_slide_instructions += f"""
SLIDE {slide_num} (Implementation details - FILL THE PAGE):
- header: "The Implementation" or "What Changes" or similar relevant header
- intro: 3-4 sentences about the implementation approach
- benefits: 5-6 specific capabilities or benefits. Each should be a complete sentence.
- summary: 2-3 sentence summary of the transformation
IMPORTANT: This is an ADDITIONAL slide with NEW content. Don't repeat previous slides. Fill the entire page.
"""
                middle_slide_json += f'''
    "slide_{slide_num}": {{
        "type": "benefits",
        "header": "What Changes",
        "intro": "3-4 detailed sentences about how implementation works.",
        "benefits": ["Capability 1", "Capability 2", "Capability 3", "Capability 4", "Capability 5"],
        "summary": "2-3 sentence summary of the complete transformation."
    }},'''
    
    return f"""Generate a {slide_count}-slide Instagram carousel post about this logistics + AI topic:

TOPIC: {topic}
{enrichment_context}

Generate content following this EXACT structure:

SLIDE 1 (Hook slide - FIRST):
- headline: {prompts['headline']}
- subheadline: {prompts['subheadline']}
{middle_slide_instructions}
SLIDE {slide_count} (CTA slide - LAST):
- MUST include: Comment "{BRAND_NAME}"
- MUST reference: "90-day scaling playbook"
- MUST include: "deploying AI across logistics workflows"
- MUST end with: "without disruption."
- Maximum 45 words total
- Centered, impactful CTA

Also generate:
- caption: 300-400 words, professional Instagram caption with DETAILED STRUCTURE and PARAGRAPHS:
  * Paragraph 1 (HOOK): 2-3 powerful sentences that grab attention and introduce the problem
  * Paragraph 2 (PROBLEM DEEP DIVE): 4-5 sentences explaining the real-world impact of this problem on logistics operations
  * Paragraph 3 (INDUSTRY CONTEXT): 3-4 sentences about why this matters now in the current industry landscape
  * Paragraph 4 (SOLUTION OVERVIEW): 4-5 sentences about how AI addresses this challenge
  * Paragraph 5 (TRANSFORMATION): 3-4 sentences about the outcomes and business impact
  * Paragraph 6 (CTA): Call to action - "Comment '{BRAND_NAME}' below to get the 90-day scaling playbook for deploying AI across logistics workflows without disruption."
  * IMPORTANT: Each paragraph MUST be separated by a blank line
  * Write in an authoritative, executive tone - no fluff, no hype
- hashtags: 15-25 relevant hashtags (logistics, supply chain, AI, automation focused). No spam hashtags.

Respond with this exact JSON structure:
{{
    "slide_1": {{
        "headline": "YOUR ALL CAPS HEADLINE HERE",
        "subheadline": "Your subheadline here in sentence case."
    }},{middle_slide_json}
    "slide_{slide_count}": {{
        "cta_text": "Comment \\"{BRAND_NAME}\\"\\n\\nTO GET THE 90-DAY SCALING PLAYBOOK FOR DEPLOYING AI ACROSS LOGISTICS WORKFLOWS WITHOUT DISRUPTION."
    }},
    "caption": {{
        "hook": "2-3 powerful sentences that grab attention.",
        "problem_deep_dive": "4-5 sentences explaining real-world impact of this problem.",
        "industry_context": "3-4 sentences about why this matters now.",
        "solution_overview": "4-5 sentences about how AI addresses this.",
        "transformation": "3-4 sentences about outcomes and business impact.",
        "cta": "Comment '{BRAND_NAME}' below to get the 90-day scaling playbook for deploying AI across logistics workflows without disruption."
    }},
    "hashtags": ["#logistics", "#supplychain", "#AI", "..."]
}}
"""


async def generate_carousel_content(
    topic: str,
    template_id: str,
    slide_count: int = 4,
    enrichment: dict = None
) -> dict:
    """
    Generate carousel post content using OpenAI.
    
    Args:
        topic: The logistics + AI topic
        template_id: Which template style to use
        slide_count: Number of slides (4-10)
        enrichment: Optional enrichment data about the topic
        
    Returns:
        dict with slide content, caption, and hashtags
    """
    # Clamp slide count to valid range
    slide_count = max(4, min(10, slide_count))
    
    template = get_template(template_id)
    
    system_prompt = build_system_prompt(template)
    user_prompt = build_generation_prompt(template, topic, slide_count, enrichment)
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=6000,  # More tokens for richer content
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse OpenAI response as JSON: {e}\nResponse: {content[:500]}")
    
    # Add slide count to result
    result["slide_count"] = slide_count
    
    # Validate required fields
    required_fields = ["slide_1", f"slide_{slide_count}", "caption", "hashtags"]
    for field in required_fields:
        if field not in result:
            raise ValueError(f"Missing required field: {field}")
    
    # Format all slide texts for storage
    result["slide_1_text"] = format_slide_1(result["slide_1"])
    
    # Format middle slides
    for i in range(2, slide_count):
        slide_key = f"slide_{i}"
        if slide_key in result:
            result[f"slide_{i}_text"] = format_middle_slide(result[slide_key], i)
        else:
            # Generate placeholder if missing
            result[f"slide_{i}_text"] = f"Content for slide {i}"
    
    # Format last slide (CTA)
    result[f"slide_{slide_count}_text"] = format_cta_slide(result[f"slide_{slide_count}"])
    
    result["hashtags_text"] = " ".join(result["hashtags"])
    
    # Format caption with line breaks
    result["caption_formatted"] = format_caption(result.get("caption", {}))
    
    return result


def format_caption(caption_data) -> str:
    """Format caption with proper line breaks for Instagram."""
    if isinstance(caption_data, str):
        # Already a string, just return it
        return caption_data
    
    if isinstance(caption_data, dict):
        # New extended format
        hook = caption_data.get("hook", "")
        problem_deep_dive = caption_data.get("problem_deep_dive", caption_data.get("problem", ""))
        industry_context = caption_data.get("industry_context", "")
        solution_overview = caption_data.get("solution_overview", caption_data.get("solution", ""))
        transformation = caption_data.get("transformation", "")
        cta = caption_data.get("cta", f"Comment '{BRAND_NAME}' below to get the 90-day scaling playbook for deploying AI across logistics workflows without disruption.")
        
        parts = []
        if hook:
            parts.append(hook)
        if problem_deep_dive:
            parts.append(problem_deep_dive)
        if industry_context:
            parts.append(industry_context)
        if solution_overview:
            parts.append(solution_overview)
        if transformation:
            parts.append(transformation)
        if cta:
            parts.append(cta)
        
        return "\n\n".join(parts)
    
    return str(caption_data)


def format_slide_1(slide: dict) -> str:
    """Format slide 1 content as text."""
    return f"""[LOGO]

{slide['headline']}

{slide['subheadline']}"""


def format_middle_slide(slide: dict, slide_num: int) -> str:
    """Format a middle slide based on its type with proper spacing."""
    slide_type = slide.get("type", "problem")
    
    if slide_type == "problem":
        intro = slide.get('intro', '')
        bullets = "\n\n".join(f"• {b}" for b in slide.get('bullets', []))
        emphasis = slide.get('emphasis_line', '')
        explanation = slide.get('explanation', '')
        
        parts = [intro]
        if bullets:
            parts.append(bullets)
        if emphasis:
            parts.append(f"**{emphasis}**")
        if explanation:
            parts.append(explanation)
        
        return "\n\n".join(parts)
    
    elif slide_type == "mechanisms":
        header = slide.get('section_header', 'How AI fixes this')
        intro = slide.get('intro', '')
        mechanisms = "\n\n".join(
            f"{i+1}. **{m['title']}**\n{m['description']}"
            for i, m in enumerate(slide.get('mechanisms', []))
        )
        
        parts = [f"**{header}**"]
        if intro:
            parts.append(intro)
        parts.append(mechanisms)
        
        return "\n\n".join(parts)
    
    elif slide_type == "outcomes":
        header = slide.get('section_header', 'The real outcome')
        intro = slide.get('intro', '')
        outcomes = "\n\n".join(f"• {o}" for o in slide.get('outcomes', []))
        punchline = slide.get('punchline', '')
        
        parts = [f"**{header}**"]
        if intro:
            parts.append(intro)
        parts.append(outcomes)
        if punchline:
            parts.append(f"**{punchline}**")
        parts.append("[LOGO]")
        
        return "\n\n".join(parts)
    
    elif slide_type == "context":
        header = slide.get('header', 'Why This Matters')
        intro = slide.get('intro', '')
        key_points = "\n\n".join(f"• {p}" for p in slide.get('key_points', []))
        closing = slide.get('closing', '')
        
        parts = [f"**{header}**"]
        if intro:
            parts.append(intro)
        if key_points:
            parts.append(key_points)
        if closing:
            parts.append(f"**{closing}**")
        
        return "\n\n".join(parts)
    
    elif slide_type == "benefits":
        header = slide.get('header', 'What Changes')
        intro = slide.get('intro', '')
        benefits = "\n\n".join(f"• {b}" for b in slide.get('benefits', []))
        summary = slide.get('summary', '')
        
        parts = [f"**{header}**"]
        if intro:
            parts.append(intro)
        if benefits:
            parts.append(benefits)
        if summary:
            parts.append(f"**{summary}**")
        
        return "\n\n".join(parts)
    
    else:
        # Fallback for unknown types
        return str(slide)


def format_cta_slide(slide: dict) -> str:
    """Format CTA slide content as text."""
    return f"""{slide['cta_text']}

[LOGO]"""


# Legacy formatters for backwards compatibility
def format_slide_2(slide: dict) -> str:
    """Format slide 2 content as text (legacy)."""
    bullets = "\n".join(f"• {b}" for b in slide.get('bullets', []))
    return f"""{slide.get('intro', '')}

{bullets}

**{slide.get('emphasis_line', '')}**

{slide.get('explanation', '')}"""


def format_slide_3(slide: dict) -> str:
    """Format slide 3 content as text (legacy)."""
    mechanisms = "\n".join(
        f"{i+1}. **{m['title']}**\n   {m['description']}"
        for i, m in enumerate(slide.get('mechanisms', []))
    )
    outcomes = "\n".join(f"• {o}" for o in slide.get('outcomes', []))
    return f"""**{slide.get('section_1_header', '')}**

{mechanisms}

**{slide.get('section_2_header', '')}**

{outcomes}

**{slide.get('punchline', '')}**

[LOGO]"""


def format_slide_4(slide: dict) -> str:
    """Format slide 4 content as text (legacy)."""
    return f"""{slide['cta_text']}

[LOGO]"""
