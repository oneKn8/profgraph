# ProfGraph

AI Professor Intelligence MCP Server.

Gives any LLM instant, pre-computed professor intelligence -- teaching style,
grade distributions, exam patterns -- so students get data-backed course
recommendations instead of hallucinated guesses.

## Quick Start

```bash
pip install -e .
profgraph
```

## MCP Tools

- `search_professors(university, query)` -- Find professors by name
- `get_professor_profile(university, professor)` -- Detailed ratings, tags, reviews
- `get_grade_distribution(university, course, professor?)` -- Historical grade data
- `compare_professors(university, professors[])` -- Side-by-side comparison

## Supported Universities

- UTD (University of Texas at Dallas)

## Data Sources

- RateMyProfessors (reviews, ratings, teaching style tags)
- UTD Nebula Trends (grade distributions from public FOIA/TPIA records)
