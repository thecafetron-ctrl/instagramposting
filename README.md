# Instagram Carousel Generator

Generate Instagram carousel posts in the STRUCTURE brand style for logistics + AI content.

## Features

- **3 Post Templates**: Problem-First, Cost-Focused, System-Failure framing
- **Automatic Topic Discovery**: Uses SerpAPI to find fresh logistics + AI topics
- **Content Generation**: OpenAI GPT-4 generates slide content, captions, and hashtags
- **Image Rendering**: Generates 1080x1350 PNG slides with Montserrat font on black marble
- **Topic Deduplication**: Prevents topic reuse within configurable window
- **Post History**: SQLite database stores all generated posts

## Project Structure

```
instagram post creator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Settings and configuration
│   │   ├── database.py          # SQLite async setup
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── routes.py            # API endpoints
│   │   ├── templates.py         # Post template definitions
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── topic_discovery.py    # SerpAPI topic search
│   │       ├── content_generator.py  # OpenAI content generation
│   │       └── image_renderer.py     # Pillow image rendering
│   ├── assets/
│   │   ├── background.png       # Black marble texture
│   │   ├── logo.png             # STRUCTURE logo
│   │   └── fonts/Montserrat/    # Montserrat font files
│   ├── generated_images/        # Output directory
│   ├── requirements.txt
│   ├── .env
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Setup Instructions

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup assets (downloads Montserrat fonts)
python setup_assets.py
```

### 2. Add Your Assets

Replace the placeholder images in `backend/assets/` with your actual images:

1. **background.png**: Your black marble texture (1080x1350 or larger)
2. **logo.png**: Your STRUCTURE logo (transparent PNG)

The Montserrat fonts are already downloaded during setup.

### 3. Start Backend

```bash
cd backend
source venv/bin/activate
python run.py
# Or: python -m uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 5. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## API Endpoints

### POST /api/generate
Generate a new carousel post.

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "problem_first",
    "topic": null,
    "allow_reuse": false,
    "render_images": true
  }'
```

**Request Body:**
- `template_id`: "problem_first" | "cost_focused" | "system_failure"
- `topic`: Optional custom topic (null for auto-discovery)
- `allow_reuse`: Allow previously used topics
- `render_images`: Generate PNG images

### GET /api/templates
List available templates.

```bash
curl http://localhost:8000/api/templates
```

### GET /api/posts
List generated posts.

```bash
curl http://localhost:8000/api/posts?limit=20&offset=0
```

### GET /api/posts/{id}
Get a specific post.

```bash
curl http://localhost:8000/api/posts/1
```

### DELETE /api/posts/{id}
Delete a post and its images.

```bash
curl -X DELETE http://localhost:8000/api/posts/1
```

### GET /api/topics/used
List recently used topics.

```bash
curl http://localhost:8000/api/topics/used?limit=50
```

### GET /api/health
Health check.

```bash
curl http://localhost:8000/api/health
```

## Templates

### Problem-First
Leads with the core problem logistics teams face.
- Headline: "YOUR [PROBLEM AREA] IS [NEGATIVE STATE]"
- Focus: Symptoms and consequences

### Cost-Focused
Emphasizes financial impact and ROI.
- Headline: "[PROBLEM] IS COSTING YOU [MONEY/MARGIN]"
- Focus: Hidden costs and savings

### System-Failure
Frames current approaches as fundamentally broken.
- Headline: "YOUR [SYSTEM] WAS BUILT FOR A DIFFERENT ERA"
- Focus: Paradigm shift and modernization

## Slide Structure

### Slide 1 (Hook)
- ALL CAPS headline (max 14 words)
- Sentence case subheadline (max 14 words)
- Logo at top

### Slide 2 (Problem)
- Intro paragraph
- 4 bullet points
- Bold emphasis line
- Explanation paragraph

### Slide 3 (Solution)
- "How AI fixes this" section (3 mechanisms)
- "The real outcome" section (4 bullets)
- Bold punchline
- Logo at bottom

### Slide 4 (CTA)
- Comment "STRUCTURE"
- 90-day scaling playbook mention
- "without disruption" closing
- Logo at bottom

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| OPENAI_API_KEY | OpenAI API key | Required |
| SERPAPI_KEY | SerpAPI key | Required |
| BRAND_NAME | Brand name for CTAs | STRUCTURE |
| DEDUPLICATION_WINDOW | Days to prevent topic reuse | 30 |
| DATABASE_URL | SQLite database path | sqlite+aiosqlite:///./posts.db |
| BACKGROUND_IMAGE_PATH | Background image path | assets/background.png |
| LOGO_IMAGE_PATH | Logo image path | assets/logo.png |
| FONT_PATH | Montserrat fonts directory | assets/fonts/Montserrat |

## Sample Mock Topic API Response

If implementing your own topic API:

```json
{
  "topics": [
    {
      "topic": "ETA prediction accuracy in freight logistics",
      "context": "Studies show 30% of shipments miss their initial ETA...",
      "relevance_score": 0.95
    },
    {
      "topic": "Carrier performance monitoring",
      "context": "Manual carrier scorecards take 20+ hours monthly...",
      "relevance_score": 0.88
    }
  ]
}
```

## License

Private - STRUCTURE
