#!/usr/bin/env python3
"""
ADO Stats Collector — Prototype

Pulls Azure DevOps sprint data and generates a hyperspace-compatible markdown
dashboard file.

Authentication:
    Primary:   Azure CLI cached credentials (run 'az login' first)
    Fallback:  ADO_PAT environment variable (Personal Access Token)

Usage:
    # Ensure you're logged in to Azure CLI
    az login

    # Run from the .hypervisor/tools/ directory
    python ado_collector.py

    # Or specify output location
    python ado_collector.py --output ../../prototypes/ado-dashboard.md

Requirements:
    pip install requests azure-identity

Configuration:
    ADO_ORG          - Organization name (default: CyberInnovationCenter)
    ADO_PROJECT      - Project name (default: Cyber.org)
    ADO_TEAM         - Team name (default: Cyber.org Team)
    ADO_PAT          - Personal Access Token (optional fallback if az login unavailable)
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


class ADOConfigError(Exception):
    """Raised when ADO configuration/auth is unavailable."""
    pass


def load_config():
    """Load configuration from environment variables.

    Auth priority:
      1. AzureCliCredential (cached 'az login' session) — preferred
      2. ADO_PAT environment variable — legacy fallback

    Returns:
        dict with org, project, team, and auth settings.

    Raises:
        ADOConfigError: If no auth method is available.
    """
    # Try loading from .env file in the same directory
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    pat = os.environ.get("ADO_PAT")

    # Determine auth method — prefer AzureCliCredential (uses cached az login)
    use_entra = False
    try:
        from azure.identity import AzureCliCredential  # noqa: F401
        use_entra = True
    except ImportError:
        pass

    if not use_entra and not pat:
        raise ADOConfigError(
            "No auth method available. "
            "Run 'az login' (requires azure-identity package), "
            "or set ADO_PAT environment variable."
        )

    return {
        "pat": pat,
        "use_entra": use_entra,
        "org": os.environ.get("ADO_ORG", DEFAULT_ORG),
        "project": os.environ.get("ADO_PROJECT", DEFAULT_PROJECT),
        "team": os.environ.get("ADO_TEAM", DEFAULT_TEAM),
    }


# ---------------------------------------------------------------------------
# ADO API Client
# ---------------------------------------------------------------------------

class ADOClient:
    """Minimal Azure DevOps REST API client.

    Supports two auth modes:
      - AzureCliCredential (cached 'az login' session) — preferred
      - PAT (Basic auth) — legacy fallback
    """

    # Azure DevOps resource ID for token scoping
    _ADO_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798/.default"

    def __init__(self, org, pat=None, use_entra=False):
        self.base_url = BASE_URL_TEMPLATE.format(org=org)
        self._credential = None
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        if use_entra:
            from azure.identity import AzureCliCredential
            self._credential = AzureCliCredential()
            self._refresh_token()
        elif pat:
            token = base64.b64encode(f":{pat}".encode()).decode()
            self.session.headers["Authorization"] = f"Basic {token}"
        else:
            raise ValueError("Either use_entra=True or provide a PAT")

    def _refresh_token(self):
        """Get a fresh bearer token from Entra ID."""
        token = self._credential.get_token(self._ADO_RESOURCE)
        self.session.headers["Authorization"] = f"Bearer {token.token}"

    def get(self, path, params=None):
        """Make a GET request to the ADO API."""
        url = f"{self.base_url}/{path}"
        params = params or {}
        params.setdefault("api-version", "7.1")
        resp = self.session.get(url, params=params)
        # Retry once with a fresh token on 401 (Entra tokens expire)
        if resp.status_code == 401 and self._credential:
            self._refresh_token()
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
        if resp.status_code == 401 and self._credential:
            self._refresh_token()
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

    def get_repos(self, project):
        """Get all git repositories in the project.

        Returns:
            List of repo dicts with id, name, defaultBranch.
        """
        path = f"{project}/_apis/git/repositories"
        data = self.get(path)
        return data.get("value", [])

    def get_recent_commits(self, project, repos=None, top=30):
        """Get recent commits across all branches and repos.

        Args:
            project: Project name.
            repos: List of repo dicts (from get_repos). Fetched if None.
            top: Max commits total to return.

        Returns:
            List of commit dicts sorted by date descending, merged across repos.
        """
        if repos is None:
            repos = self.get_repos(project)

        all_commits = []
        for repo in repos:
            repo_id = repo["id"]
            repo_name = repo.get("name", "unknown")
            try:
                path = f"{project}/_apis/git/repositories/{repo_id}/commits"
                data = self.get(path, params={"searchCriteria.$top": str(top)})
                for c in data.get("value", []):
                    all_commits.append({
                        "hash": c.get("commitId", "")[:7],
                        "full_hash": c.get("commitId", ""),
                        "author": c.get("author", {}).get("name", "Unknown"),
                        "message": (c.get("comment", "") or "").split("\n")[0][:80],
                        "repo": repo_name,
                        "branch": "",
                        "date": c.get("author", {}).get("date", ""),
                    })
            except Exception:
                continue

        all_commits.sort(key=lambda x: x["date"], reverse=True)
        return all_commits[:top]

    def get_branches_overview(self, project, repos=None, max_age_days=3):
        """Get active branches across all repos.

        Only returns branches with commits within max_age_days.
        Excludes default branches (main, master, dev, develop).

        Args:
            project: Project name.
            repos: List of repo dicts (from get_repos). Fetched if None.
            max_age_days: Max days since last commit to include.

        Returns:
            List of branch dicts with name, repo, author, last commit details.
        """
        from datetime import timedelta

        if repos is None:
            repos = self.get_repos(project)

        cutoff = datetime.now() - timedelta(days=max_age_days)
        default_names = {"main", "master", "dev", "develop"}
        branches = []

        for repo in repos:
            repo_id = repo["id"]
            repo_name = repo.get("name", "unknown")
            try:
                path = f"{project}/_apis/git/repositories/{repo_id}/refs"
                data = self.get(path, params={"filter": "heads/"})
                for ref in data.get("value", []):
                    # Extract branch name from "refs/heads/feature/xyz"
                    full_name = ref.get("name", "")
                    branch_name = full_name.replace("refs/heads/", "")
                    if branch_name in default_names:
                        continue

                    # Get the latest commit on this branch
                    object_id = ref.get("objectId", "")
                    if not object_id:
                        continue

                    # Fetch single commit details
                    commit_path = f"{project}/_apis/git/repositories/{repo_id}/commits/{object_id}"
                    try:
                        commit = self.get(commit_path)
                    except Exception:
                        continue

                    author_info = commit.get("author", {})
                    commit_date_str = author_info.get("date", "")
                    if not commit_date_str:
                        continue

                    # Parse date and filter by age
                    try:
                        # ADO dates: "2026-07-14T10:30:00Z"
                        commit_date = datetime.fromisoformat(
                            commit_date_str.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        continue

                    if commit_date < cutoff:
                        continue

                    branches.append({
                        "name": branch_name,
                        "repo": repo_name,
                        "author": author_info.get("name", "Unknown"),
                        "last_commit_hash": object_id[:7],
                        "last_commit_message": (commit.get("comment", "") or "").split("\n")[0][:80],
                        "last_commit_date": commit_date_str,
                    })
            except Exception:
                continue

        # Sort by most recent commit first
        branches.sort(key=lambda x: x["last_commit_date"], reverse=True)
        return branches

    def get_pipeline_runs(self, project, top=5):
        """Get recent completed pipeline/build runs.

        Args:
            project: Project name.
            top: Max runs to return.

        Returns:
            List of run dicts with name, status, result, duration, triggered by,
            finish time, and queue-time parameters.
        """
        import json as json_mod

        path = f"{project}/_apis/build/builds"
        data = self.get(path, params={
            "$top": str(top),
            "queryOrder": "finishTimeDescending",
            "statusFilter": "completed",
        })

        runs = []
        for build in data.get("value", []):
            # Parse queue-time parameters
            params_raw = build.get("parameters")
            params = {}
            if params_raw:
                try:
                    params = json_mod.loads(params_raw)
                except (json_mod.JSONDecodeError, TypeError):
                    pass

            # Calculate duration
            start_time = build.get("startTime", "")
            finish_time = build.get("finishTime", "")
            duration_min = 0
            if start_time and finish_time:
                try:
                    st = datetime.fromisoformat(start_time.replace("Z", "+00:00")).replace(tzinfo=None)
                    ft = datetime.fromisoformat(finish_time.replace("Z", "+00:00")).replace(tzinfo=None)
                    duration_min = round((ft - st).total_seconds() / 60, 1)
                except (ValueError, TypeError):
                    pass

            requested_for = build.get("requestedFor", {})
            runs.append({
                "id": build.get("id"),
                "name": build.get("definition", {}).get("name", "Unknown"),
                "status": build.get("status", ""),
                "result": build.get("result", ""),
                "duration_min": duration_min,
                "finished": finish_time,
                "triggered_by": requested_for.get("displayName", "Unknown"),
                "parameters": params,
            })

        return runs

    def get_active_pipeline_runs(self, project):
        """Get currently in-progress or queued pipeline/build runs.

        Returns:
            List of run dicts for active/queued builds.
        """
        import json as json_mod

        path = f"{project}/_apis/build/builds"
        data = self.get(path, params={
            "statusFilter": "inProgress,notStarted",
        })

        runs = []
        for build in data.get("value", []):
            params_raw = build.get("parameters")
            params = {}
            if params_raw:
                try:
                    params = json_mod.loads(params_raw)
                except (json_mod.JSONDecodeError, TypeError):
                    pass

            requested_for = build.get("requestedFor", {})
            runs.append({
                "id": build.get("id"),
                "name": build.get("definition", {}).get("name", "Unknown"),
                "status": build.get("status", ""),
                "started": build.get("startTime", ""),
                "queued": build.get("queueTime", ""),
                "triggered_by": requested_for.get("displayName", "Unknown"),
                "parameters": params,
            })

        return runs

    def get_burndown_history(self, org, project, iteration_path, start_date, finish_date):
        """Get daily burndown data from Analytics OData.

        Returns:
            List of dicts with 'date', 'total', 'remaining' for each day in the sprint.
        """
        from collections import defaultdict
        base = f"https://analytics.dev.azure.com/{org}/{project}/_odata/v3.0-preview/WorkItemSnapshot"
        apply_str = (
            f"filter(Iteration/IterationPath eq '{iteration_path}'"
            f" and DateValue ge {start_date}Z"
            f" and DateValue le {finish_date}Z"
            f" and (WorkItemType eq 'User Story' or WorkItemType eq 'Bug')"
            f" and State ne 'Removed'"
            f")/groupby((DateValue,StateCategory),aggregate(StoryPoints with sum as TotalPoints))"
        )
        resp = self.session.get(base, params={"$apply": apply_str, "$orderby": "DateValue"})
        if resp.status_code == 401 and self._credential:
            self._refresh_token()
            resp = self.session.get(base, params={"$apply": apply_str, "$orderby": "DateValue"})
        if resp.status_code != 200:
            return []

        rows = resp.json().get("value", [])
        daily = defaultdict(lambda: {"total": 0, "remaining": 0})
        for r in rows:
            date = r["DateValue"][:10]
            pts = r.get("TotalPoints") or 0
            daily[date]["total"] += pts
            if r.get("StateCategory") != "Completed":
                daily[date]["remaining"] += pts

        return [
            {"date": d, "total": daily[d]["total"], "remaining": daily[d]["remaining"]}
            for d in sorted(daily.keys())
        ]

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

    try:
        config = load_config()
    except ADOConfigError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    client = ADOClient(config["org"], pat=config.get("pat"), use_entra=config.get("use_entra", False))

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
