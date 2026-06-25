#!/usr/bin/env python3
"""
ADO Stats Collector — Prototype

Pulls Azure DevOps sprint data and generates a hyperspace-compatible markdown
dashboard file. Designed to run standalone with a PAT for authentication.

Usage:
    # Set your PAT as an environment variable
    set ADO_PAT=your-personal-access-token

    # Run from the .hypervisor/tools/ directory
    python ado_collector.py

    # Or specify output location
    python ado_collector.py --output ../../prototypes/ado-dashboard.md

Requirements:
    pip install requests

Configuration:
    ADO_PAT          - Personal Access Token (env var or .env file)
    ADO_ORG          - Organization name (default: CyberInnovationCenter)
    ADO_PROJECT      - Project name (default: Cyber.org)
    ADO_TEAM         - Team name (default: Cyber.org Team)
"""

import argparse
import base64
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_ORG = "CyberInnovationCenter"
DEFAULT_PROJECT = "Cyber.org"
DEFAULT_TEAM = "Cyber.org Team"
BASE_URL_TEMPLATE = "https://dev.azure.com/{org}"


def load_config():
    """Load configuration from environment variables."""
    # Try loading from .env file in the same directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    pat = os.environ.get("ADO_PAT")
    if not pat:
        print("ERROR: ADO_PAT environment variable not set.")
        print("  Set it with: set ADO_PAT=your-personal-access-token")
        sys.exit(1)

    return {
        "pat": pat,
        "org": os.environ.get("ADO_ORG", DEFAULT_ORG),
        "project": os.environ.get("ADO_PROJECT", DEFAULT_PROJECT),
        "team": os.environ.get("ADO_TEAM", DEFAULT_TEAM),
    }


# ---------------------------------------------------------------------------
# ADO API Client
# ---------------------------------------------------------------------------

class ADOClient:
    """Minimal Azure DevOps REST API client."""

    def __init__(self, org, pat):
        self.base_url = BASE_URL_TEMPLATE.format(org=org)
        # PAT auth uses Basic with empty username
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        })

    def get(self, path, params=None):
        """Make a GET request to the ADO API."""
        url = f"{self.base_url}/{path}"
        params = params or {}
        params.setdefault("api-version", "7.1")
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_current_iteration(self, project, team):
        """Get the current sprint iteration."""
        path = f"{project}/{team}/_apis/work/teamsettings/iterations"
        data = self.get(path, params={"$timeframe": "current"})
        iterations = data.get("value", [])
        return iterations[0] if iterations else None

    def get_iteration_work_items(self, project, team, iteration_id):
        """Get work item IDs for an iteration."""
        path = f"{project}/{team}/_apis/work/teamsettings/iterations/{iteration_id}/workitems"
        return self.get(path)

    def get_work_items(self, project, ids, fields=None):
        """Get work item details by IDs (batch)."""
        if not ids:
            return []
        fields = fields or [
            "System.Id", "System.Title", "System.State",
            "System.WorkItemType", "System.AssignedTo", "System.Tags"
        ]
        # ADO batch endpoint accepts up to 200 IDs
        id_str = ",".join(str(i) for i in ids[:200])
        path = f"{project}/_apis/wit/workitems"
        data = self.get(path, params={"ids": id_str, "fields": ",".join(fields)})
        return data.get("value", [])

    def get_pull_requests(self, project, status="active", top=20):
        """Get pull requests for the project."""
        path = f"{project}/_apis/git/pullrequests"
        data = self.get(path, params={
            "searchCriteria.status": status,
            "$top": str(top),
        })
        return data.get("value", [])

    def query_work_items_wiql(self, project, wiql, top=50):
        """Run a WIQL query and return full work item details.

        Args:
            project: Project name.
            wiql: WIQL query string.
            top: Max results to return.

        Returns:
            List of work item dicts with fields.
        """
        path = f"{project}/_apis/wit/wiql"
        url = f"{self.base_url}/{path}"
        params = {"api-version": "7.1", "$top": str(top)}
        resp = self.session.post(url, params=params, json={"query": wiql})
        resp.raise_for_status()
        data = resp.json()
        ids = [wi["id"] for wi in data.get("workItems", [])]
        if not ids:
            return []
        fields = [
            "System.Id", "System.Title", "System.State",
            "System.AssignedTo", "System.CreatedDate",
            "System.WorkItemType",
        ]
        return self.get_work_items(project, ids, fields=fields)


# ---------------------------------------------------------------------------
# Data Processing
# ---------------------------------------------------------------------------

def extract_top_level_items(iteration_data):
    """Extract top-level (parent) work item IDs from iteration response."""
    relations = iteration_data.get("workItemRelations", [])
    # Top-level items have rel=null and source=null
    return [r["target"]["id"] for r in relations if r.get("rel") is None]


def build_state_summary(work_items):
    """Group work items by state."""
    by_state = defaultdict(list)
    for wi in work_items:
        fields = wi.get("fields", {})
        state = fields.get("System.State", "Unknown")
        title = fields.get("System.Title", "Untitled")
        by_state[state].append(title)
    return dict(by_state)


def build_team_summary(work_items):
    """Group work items by assigned team member."""
    by_person = defaultdict(list)
    for wi in work_items:
        fields = wi.get("fields", {})
        assigned = fields.get("System.AssignedTo", "Unassigned")
        # Extract display name from "Name <email>" format
        if "<" in assigned:
            assigned = assigned.split("<")[0].strip()
        state = fields.get("System.State", "Unknown")
        by_person[assigned].append(state)
    return dict(by_person)


def format_pr_table(pull_requests):
    """Format PRs into markdown table rows."""
    rows = []
    for pr in pull_requests:
        pr_id = pr.get("pullRequestId", "?")
        repo = pr.get("repository", {}).get("name", "unknown")
        author = pr.get("createdBy", {}).get("displayName", "Unknown")
        title = pr.get("title", "Untitled")
        created = pr.get("creationDate", "")[:10]
        # Format date nicely
        if created:
            try:
                dt = datetime.fromisoformat(created)
                created = dt.strftime("%b %d")
            except ValueError:
                pass
        rows.append(f"| #{pr_id} | {repo} | {author} | {title} | {created} |")
    return rows


# ---------------------------------------------------------------------------
# Markdown Generation
# ---------------------------------------------------------------------------

def generate_dashboard(iteration, work_items, pull_requests):
    """Generate the full dashboard markdown content."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    iter_name = iteration.get("name", "Unknown")
    attrs = iteration.get("attributes", {})
    start = attrs.get("startDate", "")[:10]
    finish = attrs.get("finishDate", "")[:10]

    # Format dates
    try:
        start_dt = datetime.fromisoformat(start)
        finish_dt = datetime.fromisoformat(finish)
        date_range = f"{start_dt.strftime('%b %d')} – {finish_dt.strftime('%b %d, %Y')}"
    except ValueError:
        date_range = f"{start} – {finish}"

    state_summary = build_state_summary(work_items)
    team_summary = build_team_summary(work_items)
    total_items = len(work_items)

    # Count bugs vs stories
    bugs = [wi for wi in work_items if wi["fields"].get("System.WorkItemType") == "Bug"]
    stories = [wi for wi in work_items if wi["fields"].get("System.WorkItemType") != "Bug"]

    lines = []
    lines.append(f"# ADO Sprint Dashboard — {iter_name}")
    lines.append("")
    lines.append(f"Snapshot of Azure DevOps sprint health for iteration {iter_name} ({date_range}).")
    lines.append("")
    lines.append(f"- Created: {now}")
    lines.append(f"- Updated: {now}")
    lines.append("- Tags: devops, dashboard")
    lines.append("- Auto-generated: true")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sprint Overview
    lines.append("## Sprint Overview")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Sprint | {iter_name} |")
    lines.append(f"| Dates | {date_range} |")
    lines.append(f"| Total Stories | {len(stories)} |")
    lines.append(f"| Active Bugs | {len(bugs)} |")
    lines.append("")

    # Work Item States
    lines.append("## Work Item States")
    lines.append("")
    lines.append("| State | Count | Items |")
    lines.append("|-------|-------|-------|")
    for state, items in sorted(state_summary.items(), key=lambda x: -len(x[1])):
        # Truncate long item lists
        item_names = items[:5]
        suffix = f" (+{len(items) - 5} more)" if len(items) > 5 else ""
        lines.append(f"| {state} | {len(items)} | {', '.join(item_names)}{suffix} |")
    lines.append("")

    # Burndown bar chart (ASCII)
    lines.append("## Burndown Summary")
    lines.append("")
    lines.append("```")
    max_bar = 40
    for state, items in sorted(state_summary.items(), key=lambda x: -len(x[1])):
        pct = len(items) / total_items * 100 if total_items else 0
        bar_len = int(pct / 100 * max_bar)
        bar = "█" * bar_len
        lines.append(f"{state:<14} {bar:<{max_bar}}  {pct:4.0f}%  ({len(items)}/{total_items})")
    lines.append("```")
    lines.append("")

    # Pull Requests
    if pull_requests:
        lines.append("## Active Pull Requests")
        lines.append("")
        lines.append("| PR | Repository | Author | Title | Created |")
        lines.append("|----|-----------|--------|-------|---------|")
        for row in format_pr_table(pull_requests):
            lines.append(row)
        lines.append("")

    # Team Workload
    lines.append("## Team Workload")
    lines.append("")
    lines.append("| Team Member | Count | State Breakdown |")
    lines.append("|-------------|-------|-----------------|")
    for person, states in sorted(team_summary.items()):
        state_counts = Counter(states)
        breakdown = ", ".join(f"{v} {k}" for k, v in sorted(state_counts.items()))
        lines.append(f"| {person} | {len(states)} | {breakdown} |")
    lines.append("")

    # Risks
    risks = []
    for wi in work_items:
        fields = wi.get("fields", {})
        state = fields.get("System.State", "")
        tags = fields.get("System.Tags", "")
        title = fields.get("System.Title", "")
        wi_id = fields.get("System.Id", "?")
        if state == "Hold":
            risks.append(f"- **Hold:** {title} ({wi_id})")
        if "Likely Carryover" in tags:
            risks.append(f"- **Likely Carryover:** {title} ({wi_id})")
        if state == "Active" and fields.get("System.WorkItemType") == "Bug":
            risks.append(f"- **Active Bug:** {title} ({wi_id})")

    if risks:
        lines.append("## Risks & Blockers")
        lines.append("")
        for risk in risks:
            lines.append(risk)
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated: {now} by ado_collector.py*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate ADO sprint dashboard for hyperspace")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: ../../prototypes/ado-dashboard.md)"
    )
    args = parser.parse_args()

    # Resolve output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent.parent.parent / "prototypes" / "ado-dashboard.md"

    print("ADO Stats Collector")
    print("=" * 40)

    config = load_config()
    client = ADOClient(config["org"], config["pat"])

    # 1. Get current iteration
    print(f"  Fetching current iteration for {config['team']}...")
    iteration = client.get_current_iteration(config["project"], config["team"])
    if not iteration:
        print("  ERROR: No current iteration found.")
        sys.exit(1)
    print(f"  Sprint: {iteration['name']}")

    # 2. Get work items for the iteration
    print("  Fetching sprint work items...")
    iter_data = client.get_iteration_work_items(
        config["project"], config["team"], iteration["id"]
    )
    top_level_ids = extract_top_level_items(iter_data)
    print(f"  Found {len(top_level_ids)} top-level items")

    # 3. Get work item details
    print("  Fetching work item details...")
    work_items = client.get_work_items(config["project"], top_level_ids)
    print(f"  Retrieved {len(work_items)} items")

    # 4. Get active PRs
    print("  Fetching active pull requests...")
    pull_requests = client.get_pull_requests(config["project"])
    print(f"  Found {len(pull_requests)} active PRs")

    # 5. Generate markdown
    print("  Generating dashboard...")
    markdown = generate_dashboard(iteration, work_items, pull_requests)

    # 6. Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"  Written to: {output_path}")
    print("")
    print("Done! Run 'python build.py' to render in hypervisor.")


if __name__ == "__main__":
    main()
