"""
Phase 2 Content Generation tools: suggest_tags, similar_documents, outline_work_item.

These tools assist with content creation by analyzing text against the existing
corpus, tag registry, and project registry to provide structured suggestions.
"""

import re
from pathlib import Path

from rapidfuzz import fuzz

from .config import load_tags, load_projects
from .index import get_index_lock


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Similarity thresholds (tuned via testing)
TITLE_LIKELY_DUPLICATE = 85   # token_sort_ratio above this = likely duplicate
TITLE_REVIEW_THRESHOLD = 65   # title ratio above this triggers review
COMBINED_REVIEW_THRESHOLD = 0.55  # weighted score above this = review_existing

# Weights for combined similarity scoring
WEIGHT_TITLE = 0.55
WEIGHT_TAGS = 0.25
WEIGHT_CONTENT = 0.20

# Tag suggestion: keyword associations for each tag
# Maps tag name → set of keywords that indicate relevance
_TAG_KEYWORDS: dict[str, set[str]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_index_snapshot() -> list[dict]:
    """Thread-safe snapshot of the in-memory index."""
    from .index import _index
    with get_index_lock():
        return list(_index)


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase word set (for Jaccard comparison)."""
    return set(re.findall(r'[a-z0-9]+', text.lower()))


def _jaccard(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity coefficient between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _build_tag_keywords() -> dict[str, set[str]]:
    """Build keyword associations for tags from registry descriptions and names.

    Combines:
    - Words from the tag name itself (split on hyphens)
    - Words from the tag description
    - Manually-added technology/domain synonyms
    """
    registry = load_tags()
    keywords: dict[str, set[str]] = {}

    # Synonym expansions for common tags
    synonyms = {
        "portal": {"cyber-portal", "cyberportal", "portal", "cyber.org", "educator", "classroom"},
        "portal-cms": {"cms", "content", "curriculum", "course", "lesson"},
        "hypervisor": {"hyperspace", "hypervisor", "static site", "build.py", "mcp-server"},
        "range": {"range", "vm", "instance", "ec2", "guacamole", "rdp"},
        "django": {"django", "drf", "rest framework", "serializer", "model", "view", "migration", "middleware", "endpoint"},
        "react": {"react", "component", "hook", "usestate", "useeffect", "jsx", "tsx"},
        "nextjs": {"nextjs", "next.js", "pages", "getserversideprops", "app router"},
        "mantine": {"mantine", "modal", "button", "card", "ui library", "theme"},
        "terraform": {"terraform", "hcl", "tfvars", "module", "provider", "resource"},
        "python": {"python", "pip", "venv", "def", "class", "import"},
        "javascript": {"javascript", "typescript", "ts", "js", "npm", "node"},
        "mysql": {"mysql", "sql", "query", "database", "table", "column", "rds"},
        "aws": {"aws", "amazon", "s3", "ec2", "lambda", "ses", "iam", "cloudfront", "route53"},
        "mcp": {"mcp", "model context protocol", "fastmcp", "tool", "server"},
        "ux": {"ux", "ui", "user experience", "interface", "design", "layout", "responsive", "mobile"},
        "architecture": {"architecture", "design", "pattern", "modular", "microservice", "monolith"},
        "database": {"database", "schema", "migration", "model", "query", "index", "relation"},
        "infrastructure": {"infrastructure", "deploy", "cloud", "server", "hosting", "elastic beanstalk"},
        "devops": {"devops", "ci", "cd", "pipeline", "build", "deploy", "github actions"},
        "security": {"security", "auth", "encryption", "xss", "csrf", "injection", "vulnerability"},
        "permissions": {"permission", "rbac", "role", "access", "authorize", "deny", "grant"},
        "performance": {"performance", "load test", "latency", "cache", "optimize", "slow"},
        "accessibility": {"accessibility", "a11y", "wcag", "screen reader", "aria", "508"},
        "education": {"education", "curriculum", "course", "lesson", "student", "teacher", "educator"},
        "devtools": {"devtools", "tooling", "developer experience", "dx", "automation"},
        "code-review": {"code review", "pull request", "pr", "review"},
        "api": {"api", "endpoint", "rest", "request", "response", "http", "url"},
        "frontend": {"frontend", "component", "page", "css", "style", "render"},
        "analytics": {"analytics", "dashboard", "chart", "metric", "kpi", "tracking"},
        "search": {"search", "filter", "query", "fulltext", "autocomplete"},
        "migration": {"migration", "migrate", "schema change", "data transform"},
        "licensing": {"license", "organization", "subscription", "tier", "quota"},
        "ai": {"ai", "machine learning", "llm", "model", "embedding", "prompt"},
        "git": {"git", "branch", "commit", "merge", "rebase", "repository"},
        "artillery": {"artillery", "load test", "performance test", "stress test"},
        "guacamole": {"guacamole", "remote desktop", "rdp", "vnc", "ssh", "tunnel"},
        "kiro": {"kiro", "ide", "steering", "hook", "agent"},
    }

    for tag_name, tag_info in registry.items():
        kws = set()
        # Words from tag name
        kws.update(tag_name.replace("-", " ").split())
        # Words from description
        if tag_info.get("description"):
            kws.update(_tokenize(tag_info["description"]))
        # Add synonyms
        if tag_name in synonyms:
            for syn in synonyms[tag_name]:
                kws.update(_tokenize(syn))
        keywords[tag_name] = kws

    return keywords


def _get_tag_keywords() -> dict[str, set[str]]:
    """Get or build the tag keyword cache."""
    global _TAG_KEYWORDS
    if not _TAG_KEYWORDS:
        _TAG_KEYWORDS = _build_tag_keywords()
    return _TAG_KEYWORDS


# ---------------------------------------------------------------------------
# suggest_tags
# ---------------------------------------------------------------------------

def suggest_tags(content: str) -> dict:
    """Suggest tags from the registry based on content analysis.

    Analyzes the input text against tag keywords, descriptions, and historical
    usage patterns to produce confidence-ranked suggestions.

    Args:
        content: Text to analyze (title, description, or body content).

    Returns:
        Ranked tag suggestions with confidence scores and reasoning.
    """
    if not content or not content.strip():
        return {"suggestions": [], "error": "No content provided."}

    tag_keywords = _get_tag_keywords()
    content_tokens = _tokenize(content)
    content_lower = content.lower()

    # Score each tag
    scored: list[dict] = []
    for tag_name, keywords in tag_keywords.items():
        # Keyword overlap score
        # Filter out very short tokens (1-3 chars) that cause false positives
        meaningful_overlap = {w for w in (content_tokens & keywords) if len(w) > 3}
        multi_word_hits = []

        if not meaningful_overlap:
            # Also check for multi-word matches in the raw text
            for kw in keywords:
                if " " in kw and kw in content_lower:
                    multi_word_hits.append(kw)
            if not multi_word_hits:
                continue
            overlap = set(multi_word_hits)
        else:
            overlap = meaningful_overlap

        # Confidence: proportion of tag keywords matched, capped at 1.0
        raw_score = len(overlap) / max(len(keywords) * 0.3, 1)
        confidence = round(min(raw_score, 1.0), 2)

        # Boost: if the tag name itself appears in the content
        if tag_name in content_lower or tag_name.replace("-", " ") in content_lower:
            confidence = round(min(confidence + 0.3, 1.0), 2)

        # Build reason from top matching keywords
        top_matches = sorted(overlap, key=len, reverse=True)[:3]
        reason = f"Matches: {', '.join(top_matches)}"

        if confidence >= 0.2:
            scored.append({
                "tag": tag_name,
                "confidence": confidence,
                "reason": reason,
            })

    # Sort by confidence descending
    scored.sort(key=lambda x: x["confidence"], reverse=True)

    # Cap at top 8 suggestions
    return {
        "suggestions": scored[:8],
        "total_candidates": len(scored),
    }


# ---------------------------------------------------------------------------
# similar_documents
# ---------------------------------------------------------------------------

def similar_documents(title: str, content: str | None = None) -> dict:
    """Find existing documents that overlap with a proposed new document.

    Uses three signals:
    - Title fuzzy match (rapidfuzz token_sort_ratio)
    - Tag overlap (Jaccard on suggested tags)
    - Content token overlap (Jaccard on first ~500 words)

    Args:
        title: Proposed document title.
        content: Optional body content for deeper comparison.

    Returns:
        List of similar documents with similarity level and recommendation.
    """
    if not title or not title.strip():
        return {"similar": [], "recommendation": "proceed", "error": "No title provided."}

    entries = _get_index_snapshot()
    title_lower = title.lower()
    content_tokens = _tokenize(content[:2000]) if content else set()

    # Get suggested tags for the proposed content to compare tag overlap
    combined_text = f"{title} {content[:500] if content else ''}"
    proposed_tag_result = suggest_tags(combined_text)
    proposed_tags = set(s["tag"] for s in proposed_tag_result.get("suggestions", [])[:5])

    results: list[dict] = []

    for entry in entries:
        entry_title = entry.get("title", "")
        entry_tags = set(entry.get("tags", []))

        # Signal 1: Title similarity (rapidfuzz)
        title_score = fuzz.token_sort_ratio(title_lower, entry_title.lower()) / 100.0

        # Signal 2: Tag overlap (Jaccard)
        tag_score = _jaccard(proposed_tags, entry_tags) if proposed_tags else 0.0

        # Signal 3: Content overlap (Jaccard on tokens)
        content_score = 0.0
        if content_tokens:
            entry_snippet_tokens = _tokenize(entry.get("snippet", "") + " " + entry.get("description", ""))
            content_score = _jaccard(content_tokens, entry_snippet_tokens)

        # Weighted combined score
        combined = (
            WEIGHT_TITLE * title_score
            + WEIGHT_TAGS * tag_score
            + WEIGHT_CONTENT * content_score
        )

        if combined < 0.25:
            continue  # Not similar enough to report

        # Determine similarity level
        if title_score >= TITLE_LIKELY_DUPLICATE / 100.0 and tag_score >= 0.5:
            level = "high"
        elif combined >= COMBINED_REVIEW_THRESHOLD:
            level = "medium"
        else:
            level = "low"

        # Build reason
        reasons = []
        if title_score >= 0.6:
            reasons.append(f"title {int(title_score*100)}% match")
        if tag_score >= 0.3:
            shared = proposed_tags & entry_tags
            reasons.append(f"shared tags: {', '.join(sorted(shared))}")
        if content_score >= 0.2:
            reasons.append(f"content overlap {int(content_score*100)}%")

        results.append({
            "path": entry.get("path", ""),
            "title": entry_title,
            "type": entry.get("type", "document"),
            "similarity": level,
            "score": round(combined, 3),
            "title_match": int(title_score * 100),
            "reason": "; ".join(reasons) if reasons else "weak overlap",
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:10]  # Cap at 10

    # Determine recommendation
    recommendation = "proceed"
    if results:
        top = results[0]
        if top["similarity"] == "high":
            recommendation = "likely_duplicate"
        elif top["similarity"] == "medium":
            recommendation = "review_existing"

    return {
        "similar": results,
        "recommendation": recommendation,
        "proposed_tags": sorted(proposed_tags),
    }


# ---------------------------------------------------------------------------
# outline_work_item
# ---------------------------------------------------------------------------

def outline_work_item(description: str) -> dict:
    """Generate a structured work item outline from freeform text.

    Extracts keywords, matches against the tag registry and project list,
    and produces suggested title, tags, project, overview, AC stubs, and tasks.

    Args:
        description: Freeform text describing what needs to be built or fixed.

    Returns:
        Structured outline ready for review and refinement before create_document.
    """
    if not description or not description.strip():
        return {"error": "No description provided."}

    # --- Suggest title ---
    # Take first sentence or first 80 chars, title-case it
    first_line = description.strip().split("\n")[0]
    # Cut at first sentence boundary (period followed by space or end)
    sentence_end = re.search(r'\.\s', first_line)
    if sentence_end and sentence_end.start() < 80:
        first_line = first_line[:sentence_end.start()]
    # Strip common prefixes
    for prefix in ("we need to ", "we need ", "i want to ", "i want ", "add ", "implement ", "create ", "build ", "fix "):
        if first_line.lower().startswith(prefix):
            first_line = first_line[len(prefix):]
            break
    # Capitalize and truncate
    suggested_title = first_line[:80].strip().rstrip(".")
    if suggested_title:
        suggested_title = suggested_title[0].upper() + suggested_title[1:]

    # --- Suggest tags ---
    tag_result = suggest_tags(description)
    suggested_tags = [s["tag"] for s in tag_result.get("suggestions", [])[:4]]

    # --- Suggest project ---
    projects = load_projects()
    suggested_project = _infer_project(description, suggested_tags, projects)

    # --- Suggest overview (user story format) ---
    # Try to infer who/what/why
    suggested_overview = _generate_user_story(description)

    # --- Suggest AC stubs ---
    suggested_ac = _generate_ac_stubs(description, suggested_title)

    # --- Suggest tasks ---
    suggested_tasks = _generate_task_stubs(description, suggested_tags)

    # --- Check for similar existing documents ---
    similar = similar_documents(suggested_title, description)
    similar_existing = [
        {"title": s["title"], "path": s["path"], "similarity": s["similarity"]}
        for s in similar.get("similar", [])[:3]
    ]

    return {
        "suggested_title": suggested_title,
        "suggested_tags": suggested_tags,
        "suggested_project": suggested_project,
        "suggested_overview": suggested_overview,
        "suggested_ac": suggested_ac,
        "suggested_tasks": suggested_tasks,
        "similar_existing": similar_existing,
        "description_analyzed": description[:200],
    }


def _infer_project(description: str, tags: list[str], projects: list[str]) -> str:
    """Infer the most likely project from description and tags."""
    desc_lower = description.lower()

    # Direct keyword mapping
    if "portal-cms" in tags or "cms" in desc_lower or "curriculum" in desc_lower or "course" in desc_lower:
        return "Curriculum Management"
    if "range" in tags or "vm" in desc_lower or "instance" in desc_lower or "ec2" in desc_lower:
        return "CYBER Range"
    if "portal" in tags or "educator" in desc_lower or "classroom" in desc_lower:
        return "CYBERPortal Platform"
    if "hypervisor" in tags or "hyperspace" in desc_lower or "mcp" in desc_lower:
        return "General System Development"

    # Default
    return "General System Development"


def _generate_user_story(description: str) -> str:
    """Generate a user story from freeform description."""
    # Simple heuristic: if description is already story-format, use it
    desc_lower = description.lower()
    if "as a" in desc_lower and "i want" in desc_lower:
        return description.strip()

    # Otherwise, construct a generic one
    # Extract the core action from the description
    action = description.strip().split("\n")[0].rstrip(".")
    # Remove common prefixes
    for prefix in ("we need to ", "we need ", "i want to ", "i want ", "should ", "need to "):
        if action.lower().startswith(prefix):
            action = action[len(prefix):]
            break

    return f"As a user, I want {action.lower()}, so that the system better serves its intended purpose."


def _generate_ac_stubs(description: str, title: str) -> dict:
    """Generate acceptance criteria section stubs from description."""
    # Extract potential feature areas from the description
    lines = [l.strip() for l in description.split("\n") if l.strip()]

    # If description has bullet points or multiple sentences, use those
    if len(lines) >= 3:
        return {
            title: [
                f"{line.lstrip('- •').strip()}" for line in lines[:5]
                if len(line.strip()) > 10
            ]
        }

    # Generic stubs based on common patterns
    desc_lower = description.lower()
    criteria = []
    if "api" in desc_lower or "endpoint" in desc_lower:
        criteria.append("API endpoint returns expected response shape")
        criteria.append("Error cases return appropriate HTTP status codes")
    if "ui" in desc_lower or "page" in desc_lower or "component" in desc_lower:
        criteria.append("UI renders correctly on desktop and mobile viewports")
        criteria.append("Loading and error states are handled gracefully")
    if "auth" in desc_lower or "permission" in desc_lower:
        criteria.append("Unauthorized users receive 403 response")
        criteria.append("Permission checks enforce the correct access level")

    if not criteria:
        criteria = [
            "Core functionality works as described",
            "Edge cases are handled gracefully",
            "Changes do not break existing functionality",
        ]

    return {title: criteria}


def _generate_task_stubs(description: str, tags: list[str]) -> list[str]:
    """Generate task stubs based on description and inferred stack."""
    tasks = []
    desc_lower = description.lower()

    # Backend tasks
    if any(t in tags for t in ("django", "api", "database")) or any(
        kw in desc_lower for kw in ("model", "endpoint", "api", "backend", "migration")
    ):
        tasks.append("Add/update Django model and create migration")
        tasks.append("Implement API endpoint/view")
        tasks.append("Add serializer and validation")

    # Frontend tasks
    if any(t in tags for t in ("react", "nextjs", "mantine", "frontend", "ux")) or any(
        kw in desc_lower for kw in ("page", "component", "ui", "frontend", "form")
    ):
        tasks.append("Create/update React component")
        tasks.append("Connect to API and handle loading/error states")
        tasks.append("Add responsive styling")

    # Infrastructure tasks
    if any(t in tags for t in ("terraform", "infrastructure", "aws", "devops")):
        tasks.append("Update Terraform configuration")
        tasks.append("Test in dev environment")

    # Generic if nothing specific matched
    if not tasks:
        tasks = [
            "Investigate current implementation",
            "Implement core changes",
            "Verify changes work end-to-end",
        ]

    return tasks
