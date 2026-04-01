"""Research prompt template for Claude Opus sessions."""

import json


def build_research_prompt(record: dict) -> str:
    """Build the deep research prompt for a single need signal."""
    record_json = json.dumps(record, indent=2)

    return f"""You are a market research analyst. You've received a product need signal found on Reddit. Your job is NOT to summarize the Reddit post -- it is to investigate the MARKET PROBLEM this signal reveals.

## Input Signal

```json
{record_json}
```

## Research Mission

This Reddit post is one data point. Investigate the broader market reality behind it. Use web search extensively for every section.

### Phase 1: Decode the Real Need
- What job is the user actually trying to get done? (Jobs-to-be-Done framework)
- What are the functional, emotional, and social dimensions of this need?
- Who else has this problem? What adjacent user segments share this pain?
- Is this a "vitamin" (nice to have) or "painkiller" (must solve)?

### Phase 2: Market Landscape
Use web search to find:
- What products/tools currently serve this need? (Go beyond what the post mentions)
- How do existing solutions fall short? What gaps remain?
- Pricing landscape (free tier, paid, enterprise)
- Recent entrants or emerging solutions (search "best [category] 2025/2026", "alternatives to [competitor]")
- What do review sites (G2, Capterra, Product Hunt) say?

### Phase 3: Opportunity Analysis
- Market size signals: how many people/businesses have this problem?
- Willingness to pay: what do people currently spend on adjacent solutions?
- Switching costs: how hard is it to leave current solutions?
- Defensibility: could a new entrant build a moat?
- Timing: why now? What trends make this solvable today?

### Phase 4: Divergent Insights
Think beyond the obvious:
- Broader market shifts or behavioral changes this reveals
- Underserved niches within the broader market
- Opportunities for a different business model (not just another SaaS)
- Potential for a "wedge" product that starts here but expands
- Adjacent problems the same user likely has

## Output Format

# [Descriptive title about the market problem, NOT the Reddit post title]

## Signal Summary
> One paragraph: original signal + what market problem it points to.

## The Real Need
- Jobs to be done analysis
- User segments affected
- Pain severity (1-10 with justification)

## Market Landscape
| Solution | Category | Pricing | Key Limitation |
|----------|----------|---------|----------------|

### Gaps in Current Solutions

## Opportunity Assessment
- **Market Size**: [estimate with reasoning]
- **Willingness to Pay**: [evidence from research]
- **Competition Intensity**: Low / Medium / High with reasoning
- **Timing**: Why now?
- **Verdict**: [1-2 sentence: worth pursuing?]

## Divergent Insights

## Key Sources
(URLs consulted during research)

---
IMPORTANT: Use web search for EVERY section. Every claim should be backed by research, not just inferred from the Reddit post. The post is a starting point, not the answer."""
