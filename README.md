# ProfGraph

AI professor intelligence for any LLM. Ratings, NLP-extracted teaching style, grade distributions, and data-backed recommendations -- served via MCP and REST API.

Students ask _"who should I take for CS 4348?"_ and get an answer grounded in 7,000+ historical student outcomes instead of hallucinated guesses.

## How It Works

```
Student -> Claude / ChatGPT / any LLM
              |
              v
         ProfGraph (MCP + REST API)
              |
              +-- RateMyProfessors GraphQL --> ratings, tags, reviews
              +-- NLP pipeline             --> teaching style classification
              +-- Nebula Trends API        --> grade distributions (FOIA data)
              +-- Prerequisite graph       --> course dependencies
              +-- Community intel (SQLite) --> crowdsourced syllabus data
```

## Quick Start

### Local (stdio, for Claude Code / Claude Desktop)

```bash
git clone https://github.com/oneKn8/profgraph.git
cd profgraph
pip install -e .
```

Add to Claude Desktop MCP config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "profgraph": {
      "command": "python3",
      "args": ["-m", "profgraph"],
      "cwd": "/path/to/profgraph"
    }
  }
}
```

### Hosted (HTTP, for ChatGPT / remote clients)

```bash
pip install -e ".[deploy]"
PROFGRAPH_TRANSPORT=streamable-http python -m profgraph
```

Server starts on `http://0.0.0.0:8000` with both MCP (`/mcp`) and REST API (`/api/*`).

### Docker

```bash
docker build -t profgraph .
docker run -p 8000:8000 profgraph
```

### Fly.io

```bash
fly volumes create profgraph_data --region dfw --size 1
fly launch
```

## 10 MCP Tools

| Tool | Description |
|------|-------------|
| `list_universities` | Show supported schools and data availability |
| `search_professors` | Find professors by name, optionally filter by department |
| `get_professor_profile` | Full profile: ratings, NLP teaching style, tags, courses, reviews |
| `get_grade_distribution` | Historical grade data by semester (FOIA/TPIA public records) |
| `compare_professors` | Side-by-side comparison table |
| `predict_grade` | Grade probability given student GPA vs historical distribution |
| `recommend_professor` | Ranked recommendations by learning style and priorities |
| `get_prerequisites` | Course prerequisite tree with depth traversal |
| `submit_intel` | Contribute syllabus data (exam weights, curve, textbook, notes) |
| `get_intel` | Retrieve community-contributed course intel |

## REST API (for ChatGPT Actions)

| Endpoint | Description |
|----------|-------------|
| `GET /api/universities` | List supported schools |
| `GET /api/search?university=utd&query=Smith` | Professor search |
| `GET /api/profile?university=utd&professor=Jason+Smith` | Full profile |
| `GET /api/grades?university=utd&course=CS+3341` | Grade distributions |
| `GET /api/predict?university=utd&course=CS+3341&professor=smith&gpa=3.2` | Grade prediction |
| `GET /api/prerequisites?course=CS+4348` | Prerequisite tree |
| `GET /api/openapi.json` | OpenAPI 3.1 spec (import into ChatGPT) |

**ChatGPT setup:** Create a custom GPT -> Add Action -> Import from URL -> `https://yourserver/api/openapi.json`

## Supported Universities

| University | Key | Professor Data | Grade Data |
|------------|-----|:--------------:|:----------:|
| UT Dallas | `utd` | yes | yes |
| Texas A&M | `tamu` | yes | -- |
| UT Austin | `utaustin` | yes | -- |
| UT Arlington | `uta` | yes | -- |
| U of Houston | `uh` | yes | -- |
| Rice University | `rice` | yes | -- |
| U of North Texas | `unt` | yes | -- |

All universities have full professor support (search, profiles, NLP teaching style, comparisons, recommendations). Grade distributions currently available for UTD via Nebula Trends API.

## NLP Teaching Style

Extracted from RMP review text using keyword pattern matching:

- **Exam style:** straightforward, mixed, ambiguous, tricky
- **Homework load:** light, moderate, heavy
- **Lecture quality:** clear, mixed, unclear
- **Curve likelihood:** none, low, medium, high, guaranteed
- **Accessibility:** high, medium, low
- **Boolean signals:** uses textbook, records lectures, provides practice exams
- **Warnings:** extracted from low-rated reviews (exam/HW mismatch, grading issues, disorganization)
- **Student types:** best for / challenging for classifications

## Example Output

```
$ profgraph search_professors utd "Jason Smith"

# Jason Smith
Computer Science | UTD

Rating: 3.3/5 | Difficulty: 4.3/5 | Would Take Again: 55%

## Teaching Style (NLP-extracted)
- Exam Style: ambiguous
- Homework Load: heavy
- Lecture Quality: clear
- Curve Likelihood: none
- Accessibility: high

## Teaching Style Tags
- Lots of homework (151x)
- Tough grader (104x)
- Accessible outside class (76x)
- Clear grading criteria (28x)
- Amazing lectures (28x)
```

## Data Sources

| Source | Method | Auth |
|--------|--------|------|
| RateMyProfessors | GraphQL API | Public token |
| UTD Nebula Trends | REST API | None |
| Prerequisites | Hardcoded (UTD CS 2025-2026 catalog) | N/A |
| Community Intel | SQLite (user-contributed) | N/A |

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `PROFGRAPH_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `PROFGRAPH_HOST` | `0.0.0.0` | HTTP server bind address |
| `PROFGRAPH_PORT` | `8000` | HTTP server port |
| `PROFGRAPH_RMP_AUTH` | `Basic dGVzdDp0ZXN0` | RMP auth token (public, configurable) |

## Development

```bash
pip install -e ".[dev]"
pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_e2e.py
```

54 unit tests (models, cache, NLP, prerequisites, intel). Live and E2E tests require network access.

## License

MIT
