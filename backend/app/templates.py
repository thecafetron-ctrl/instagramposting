"""
Post templates for Instagram carousel generation.
Each template defines a different framing/style while following the 4-slide STRUCTURE rules.
"""

TEMPLATES = {
    "problem_first": {
        "id": "problem_first",
        "name": "Problem-First",
        "description": "Leads with the core problem logistics teams face",
        "icon": "⚠️",
        "preview_style": "Bold problem statement that grabs attention",
        "slide_1": {
            "headline_style": "problem_statement",
            "example": "YOUR {PROBLEM_NOUN} IS BROKEN",
            "subheadline_style": "consequence"
        },
        "slide_2": {
            "intro_style": "situation_description",
            "bullets_emphasis": "symptoms",
            "emphasis_line_style": "consequence_warning",
            "closing_style": "root_cause"
        },
        "slide_3": {
            "section_1_header": "How AI fixes this",
            "mechanisms_style": "capability_first",
            "section_2_header": "The real outcome",
            "outcomes_style": "benefit_focused",
            "punchline_style": "transformation"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline (max 14 words) that directly states the problem. Format: 'YOUR [PROBLEM AREA] IS [NEGATIVE STATE]'. Examples: 'YOUR LOGISTICS COSTS ARE HIGH', 'YOUR SUPPLY CHAIN IS BLIND'.",
            "subheadline": "Create a subheadline (max 14 words) that explains WHY the problem exists or its consequence. Use sentence case.",
            "intro": "Write 1-2 sentences describing how most logistics teams currently handle this area (reactive, manual, etc).",
            "bullets": "List 4 specific symptoms/manifestations of this problem as bullet points. Keep each to 2-5 words.",
            "emphasis": "Write ONE bold statement (max 15 words) about the consequence of not addressing this. Make it impactful.",
            "explanation": "Write 2-3 sentences explaining why this happens (root cause). Reference traditional systems being passive/reactive.",
            "mechanisms": "Provide exactly 3 numbered items explaining HOW AI solves this. Each item has a bold capability name and 1-2 sentence explanation.",
            "outcomes": "List exactly 4 bullet points of business outcomes. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences that summarize the transformation. End with a forward-looking statement about AI in logistics."
        }
    },
    "cost_focused": {
        "id": "cost_focused",
        "name": "Cost-Focused",
        "description": "Emphasizes financial impact and ROI",
        "icon": "💰",
        "preview_style": "Money-driven headline that hits the bottom line",
        "slide_1": {
            "headline_style": "cost_statement",
            "example": "{TOPIC} IS COSTING YOU MILLIONS",
            "subheadline_style": "hidden_cost_reveal"
        },
        "slide_2": {
            "intro_style": "cost_breakdown",
            "bullets_emphasis": "cost_drivers",
            "emphasis_line_style": "financial_wake_up",
            "closing_style": "cost_accumulation"
        },
        "slide_3": {
            "section_1_header": "How AI cuts these costs",
            "mechanisms_style": "roi_focused",
            "section_2_header": "The financial impact",
            "outcomes_style": "savings_focused",
            "punchline_style": "investment_case"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline (max 14 words) focusing on cost/money impact. Format: '[PROBLEM AREA] IS COSTING YOU [MONEY/MARGIN/PROFIT]'. Make it financially alarming.",
            "subheadline": "Create a subheadline (max 14 words) revealing hidden or unexpected costs. Use sentence case.",
            "intro": "Write 1-2 sentences about where money bleeds in this logistics area without teams realizing.",
            "bullets": "List 4 specific cost drivers or financial leaks as bullet points. Keep each to 3-6 words.",
            "emphasis": "Write ONE bold statement (max 15 words) quantifying or dramatizing the financial impact.",
            "explanation": "Write 2-3 sentences explaining how these costs compound over time and why they stay hidden.",
            "mechanisms": "Provide exactly 3 numbered items explaining HOW AI reduces costs. Each has a bold mechanism name and 1-2 sentence ROI explanation.",
            "outcomes": "List exactly 4 bullet points of financial outcomes. Reference savings, efficiency, margin improvement. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences about the financial transformation. Position AI as a profit driver, not just a cost."
        }
    },
    "system_failure": {
        "id": "system_failure",
        "name": "System-Failure",
        "description": "Frames current approaches as fundamentally broken",
        "icon": "⚙️",
        "preview_style": "Legacy system critique that demands modernization",
        "slide_1": {
            "headline_style": "system_diagnosis",
            "example": "YOUR {SYSTEM} WAS BUILT FOR A DIFFERENT ERA",
            "subheadline_style": "obsolescence_statement"
        },
        "slide_2": {
            "intro_style": "legacy_critique",
            "bullets_emphasis": "system_failures",
            "emphasis_line_style": "paradigm_shift",
            "closing_style": "new_reality"
        },
        "slide_3": {
            "section_1_header": "What modern systems do differently",
            "mechanisms_style": "architecture_focused",
            "section_2_header": "The operational shift",
            "outcomes_style": "capability_focused",
            "punchline_style": "future_state"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline (max 14 words) declaring the current system/approach as outdated or broken. Format: 'YOUR [SYSTEM] WAS BUILT FOR [OLD PARADIGM]' or 'LEGACY [SYSTEMS] CANNOT [REQUIREMENT]'.",
            "subheadline": "Create a subheadline (max 14 words) stating what modern logistics requires. Use sentence case.",
            "intro": "Write 1-2 sentences critiquing how legacy systems approach this problem (batch processing, manual triggers, etc).",
            "bullets": "List 4 specific system failures or architectural limitations as bullet points. Keep each to 3-6 words.",
            "emphasis": "Write ONE bold statement (max 15 words) about why the old model fundamentally cannot work anymore.",
            "explanation": "Write 2-3 sentences about what has changed (data volume, customer expectations, speed requirements) that makes old systems obsolete.",
            "mechanisms": "Provide exactly 3 numbered items explaining the architectural/system differences with AI. Each has a bold principle name and 1-2 sentence explanation.",
            "outcomes": "List exactly 4 bullet points of operational capabilities enabled. Focus on what becomes possible. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences about the paradigm shift. Frame it as inevitable modernization."
        }
    },
    "question_hook": {
        "id": "question_hook",
        "name": "Question Hook",
        "description": "Opens with a provocative question to engage readers",
        "icon": "❓",
        "preview_style": "Thought-provoking question that demands attention",
        "slide_1": {
            "headline_style": "provocative_question",
            "example": "IS YOUR {PROCESS} ACTUALLY WORKING?",
            "subheadline_style": "reality_check"
        },
        "slide_2": {
            "intro_style": "uncomfortable_truth",
            "bullets_emphasis": "hidden_issues",
            "emphasis_line_style": "confrontational",
            "closing_style": "deeper_problem"
        },
        "slide_3": {
            "section_1_header": "Here's what actually works",
            "mechanisms_style": "solution_focused",
            "section_2_header": "What changes",
            "outcomes_style": "transformation_focused",
            "punchline_style": "new_standard"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline as a provocative QUESTION (max 14 words). Format: 'IS YOUR [PROCESS] [ACTUALLY/REALLY] [WORKING/EFFICIENT]?' or 'WHY IS YOUR [AREA] STILL [PROBLEM]?'. Make it challenge assumptions.",
            "subheadline": "Create a subheadline (max 14 words) that hints at the uncomfortable answer. Use sentence case.",
            "intro": "Write 1-2 sentences presenting an uncomfortable truth about how most logistics teams operate in this area.",
            "bullets": "List 4 hidden issues or inconvenient truths as bullet points. Keep each to 2-5 words.",
            "emphasis": "Write ONE bold statement (max 15 words) that directly confronts the reader about their current state.",
            "explanation": "Write 2-3 sentences revealing a deeper systemic problem they haven't considered.",
            "mechanisms": "Provide exactly 3 numbered items showing what actually works. Each has a bold principle name and 1-2 sentence explanation.",
            "outcomes": "List exactly 4 bullet points of transformation outcomes. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences establishing the new standard. Frame AI as the obvious answer."
        }
    },
    "speed_urgency": {
        "id": "speed_urgency",
        "name": "Speed & Urgency",
        "description": "Focuses on time savings and competitive speed",
        "icon": "⚡",
        "preview_style": "Time-critical messaging that creates urgency",
        "slide_1": {
            "headline_style": "time_crisis",
            "example": "YOU'RE LOSING {TIME} EVERY {PERIOD}",
            "subheadline_style": "speed_comparison"
        },
        "slide_2": {
            "intro_style": "time_waste_breakdown",
            "bullets_emphasis": "time_drains",
            "emphasis_line_style": "competitive_pressure",
            "closing_style": "speed_imperative"
        },
        "slide_3": {
            "section_1_header": "How AI accelerates everything",
            "mechanisms_style": "speed_focused",
            "section_2_header": "The time advantage",
            "outcomes_style": "speed_outcomes",
            "punchline_style": "competitive_edge"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline (max 14 words) about time/speed. Format: 'YOU'RE LOSING [TIME] EVERY [PERIOD]' or '[PROCESS] TAKES [X] LONGER THAN IT SHOULD'. Create urgency.",
            "subheadline": "Create a subheadline (max 14 words) comparing your speed to what's possible. Use sentence case.",
            "intro": "Write 1-2 sentences about how time is wasted in this logistics area and what it means competitively.",
            "bullets": "List 4 specific time drains or bottlenecks as bullet points. Keep each to 3-6 words.",
            "emphasis": "Write ONE bold statement (max 15 words) about the competitive pressure of being slow.",
            "explanation": "Write 2-3 sentences explaining why speed matters more now than ever in logistics.",
            "mechanisms": "Provide exactly 3 numbered items explaining HOW AI speeds things up. Each has a bold capability name and 1-2 sentence time-saving explanation.",
            "outcomes": "List exactly 4 bullet points of speed/time outcomes. Reference faster, instant, real-time. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences about the competitive advantage of speed. Position AI as the accelerator."
        }
    },
    "comparison": {
        "id": "comparison",
        "name": "Before/After",
        "description": "Shows stark contrast between old and new approaches",
        "icon": "⬅️➡️",
        "preview_style": "Side-by-side contrast that shows transformation",
        "slide_1": {
            "headline_style": "contrast_statement",
            "example": "MANUAL {PROCESS} VS AI {PROCESS}",
            "subheadline_style": "clear_winner"
        },
        "slide_2": {
            "intro_style": "old_way_description",
            "bullets_emphasis": "old_way_problems",
            "emphasis_line_style": "stark_contrast",
            "closing_style": "inevitable_choice"
        },
        "slide_3": {
            "section_1_header": "The AI difference",
            "mechanisms_style": "comparison_focused",
            "section_2_header": "What you gain",
            "outcomes_style": "transformation_focused",
            "punchline_style": "clear_choice"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline (max 14 words) as a comparison. Format: 'MANUAL [PROCESS] VS AI [PROCESS]' or '[OLD WAY] IS [X], AI IS [Y]'. Make the contrast clear.",
            "subheadline": "Create a subheadline (max 14 words) that declares which approach wins. Use sentence case.",
            "intro": "Write 1-2 sentences describing the old/manual way of handling this logistics area.",
            "bullets": "List 4 problems with the old approach as bullet points. Keep each to 2-5 words.",
            "emphasis": "Write ONE bold statement (max 15 words) showing the stark contrast between old and new.",
            "explanation": "Write 2-3 sentences explaining why the choice between approaches is now obvious.",
            "mechanisms": "Provide exactly 3 numbered items showing the AI difference. Each has a bold comparison point and 1-2 sentence explanation.",
            "outcomes": "List exactly 4 bullet points of gains from switching. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences making the choice clear. Frame manual processes as the past."
        }
    },
    "data_driven": {
        "id": "data_driven",
        "name": "Data-Driven",
        "description": "Uses statistics and numbers to make the case",
        "icon": "📊",
        "preview_style": "Statistics-led approach with hard numbers",
        "slide_1": {
            "headline_style": "statistic_shock",
            "example": "{X}% OF {TOPIC} FAILURES ARE PREVENTABLE",
            "subheadline_style": "data_context"
        },
        "slide_2": {
            "intro_style": "data_overview",
            "bullets_emphasis": "key_statistics",
            "emphasis_line_style": "data_conclusion",
            "closing_style": "data_implication"
        },
        "slide_3": {
            "section_1_header": "What the data shows works",
            "mechanisms_style": "evidence_based",
            "section_2_header": "Proven results",
            "outcomes_style": "measured_outcomes",
            "punchline_style": "data_backed_conclusion"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline (max 14 words) featuring a statistic. Format: '[X]% OF [TOPIC] [PROBLEM] ARE PREVENTABLE' or '[X] OUT OF [Y] [PROBLEMS] COULD BE AVOIDED'. Use realistic-sounding percentages.",
            "subheadline": "Create a subheadline (max 14 words) providing context for the statistic. Use sentence case.",
            "intro": "Write 1-2 sentences presenting data about this logistics challenge area.",
            "bullets": "List 4 key statistics or data points as bullet points. Keep each to 3-6 words.",
            "emphasis": "Write ONE bold statement (max 15 words) drawing a conclusion from the data.",
            "explanation": "Write 2-3 sentences explaining what the data implies and why it matters.",
            "mechanisms": "Provide exactly 3 numbered items showing evidence-based AI solutions. Each has a bold finding and 1-2 sentence explanation.",
            "outcomes": "List exactly 4 bullet points of measured/quantifiable outcomes. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences with a data-backed conclusion. Make the case irrefutable."
        }
    },
    "fear_of_missing_out": {
        "id": "fear_of_missing_out",
        "name": "FOMO",
        "description": "Highlights what competitors are already doing",
        "icon": "🏃",
        "preview_style": "Competitive pressure that creates urgency",
        "slide_1": {
            "headline_style": "competitor_awareness",
            "example": "YOUR COMPETITORS ARE ALREADY USING AI FOR {TOPIC}",
            "subheadline_style": "falling_behind"
        },
        "slide_2": {
            "intro_style": "market_shift",
            "bullets_emphasis": "competitor_advantages",
            "emphasis_line_style": "urgency_statement",
            "closing_style": "catch_up_imperative"
        },
        "slide_3": {
            "section_1_header": "What leaders are doing",
            "mechanisms_style": "best_practice_focused",
            "section_2_header": "The competitive advantage",
            "outcomes_style": "market_position",
            "punchline_style": "act_now"
        },
        "prompts": {
            "headline": "Create an ALL CAPS headline (max 14 words) about competitors. Format: 'YOUR COMPETITORS ARE ALREADY [USING AI FOR/AUTOMATING] [TOPIC]' or 'WHILE YOU [OLD WAY], THEY [NEW WAY]'. Create FOMO.",
            "subheadline": "Create a subheadline (max 14 words) about falling behind. Use sentence case.",
            "intro": "Write 1-2 sentences about how the market/industry is shifting toward AI in this area.",
            "bullets": "List 4 advantages competitors gain from AI as bullet points. Keep each to 3-6 words.",
            "emphasis": "Write ONE bold statement (max 15 words) creating urgency about being left behind.",
            "explanation": "Write 2-3 sentences about why catching up is imperative and what happens to those who wait.",
            "mechanisms": "Provide exactly 3 numbered items showing what industry leaders do. Each has a bold best practice and 1-2 sentence explanation.",
            "outcomes": "List exactly 4 bullet points of competitive advantages gained. Keep each to 6-10 words.",
            "punchline": "Write 1-2 bold sentences demanding action now. Frame AI adoption as survival."
        }
    }
}


def get_template(template_id: str) -> dict:
    """Get a template by ID."""
    if template_id not in TEMPLATES:
        raise ValueError(f"Template '{template_id}' not found. Available: {list(TEMPLATES.keys())}")
    return TEMPLATES[template_id]


def get_all_templates() -> list[dict]:
    """Get all available templates."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "icon": t.get("icon", "📄"),
            "preview_style": t.get("preview_style", "")
        }
        for t in TEMPLATES.values()
    ]
