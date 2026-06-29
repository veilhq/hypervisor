"""ADO dashboard payload builder — shapes raw ADO data into the JSON structure
expected by the hypervisor dashboard UI.

Separated from hypervisor-app.py so the business logic is testable independently.
"""

from collections import defaultdict
from datetime import datetime


def build_dashboard_payload(iteration, work_items, pull_requests, work_requests=None, config=None, burndown_history=None):
    """Build the full dashboard response payload from raw ADO data.

    Args:
        iteration: Iteration dict from ADOClient.get_current_iteration()
        work_items: List of work item dicts from ADOClient.get_work_items()
        pull_requests: List of PR dicts from ADOClient.get_pull_requests()
        work_requests: List of work request dicts from WIQL query (optional)
        config: ADO config dict with org/project for building URLs (optional)
        burndown_history: List of daily burndown dicts from Analytics (optional)

    Returns:
        dict ready to be returned as JSON to the frontend.
    """
    attrs = iteration.get("attributes", {})
    start_date = attrs.get("startDate", "")[:10]
    finish_date = attrs.get("finishDate", "")[:10]

    # State counts and points
    state_counts = defaultdict(int)
    state_points = defaultdict(float)
    team_data = defaultdict(lambda: {"points": 0, "states": defaultdict(float)})
    total_points = 0
    risks = []

    for wi in work_items:
        f = wi.get("fields", {})
        state = f.get("System.State", "Unknown")
        pts = f.get("Microsoft.VSTS.Scheduling.StoryPoints", 0) or 0
        title = f.get("System.Title", "Untitled")
        wi_id = f.get("System.Id", "?")
        wi_type = f.get("System.WorkItemType", "")
        tags = f.get("System.Tags", "")
        assigned = f.get("System.AssignedTo", {})
        if isinstance(assigned, dict):
            person = assigned.get("displayName", "Unassigned")
        else:
            person = str(assigned).split("<")[0].strip() if assigned else "Unassigned"

        state_counts[state] += 1
        state_points[state] += pts
        total_points += pts
        team_data[person]["points"] += pts
        team_data[person]["states"][state] += pts

        # Detect risks
        if state == "Hold":
            risks.append({"type": "hold", "title": title, "id": wi_id, "assigned": person})
        if "Likely Carryover" in tags:
            risks.append({"type": "carryover", "title": title, "id": wi_id, "assigned": person})
        if state == "Active" and wi_type == "Bug":
            risks.append({"type": "bug", "title": title, "id": wi_id, "assigned": person})

    # Format PRs
    pr_list = []
    now = datetime.now()
    for pr in pull_requests:
        created = pr.get("creationDate", "")[:10]
        age_days = 0
        if created:
            try:
                age_days = (now - datetime.fromisoformat(created)).days
            except ValueError:
                pass
        pr_list.append({
            "id": pr.get("pullRequestId", "?"),
            "title": pr.get("title", "Untitled"),
            "repo": pr.get("repository", {}).get("name", "unknown"),
            "age_days": age_days,
        })

    # Format team data for response
    team_response = []
    for person, data in sorted(team_data.items()):
        team_response.append({
            "name": person,
            "points": data["points"],
            "states": dict(data["states"]),
        })

    # Remaining points (non-Closed)
    closed_points = state_points.get("Closed", 0)
    remaining_points = total_points - closed_points

    # Burndown data — provides today's snapshot so the frontend can
    # accumulate a daily series in localStorage across the sprint.
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Format work requests
    wr_list = []
    if work_requests:
        for wr in work_requests:
            f = wr.get("fields", {})
            assigned = f.get("System.AssignedTo", {})
            if isinstance(assigned, dict):
                person = assigned.get("displayName", "Unassigned")
            else:
                person = str(assigned).split("<")[0].strip() if assigned else "Unassigned"
            created = f.get("System.CreatedDate", "")[:10]
            wr_list.append({
                "id": f.get("System.Id", "?"),
                "title": f.get("System.Title", "Untitled"),
                "state": f.get("System.State", "Unknown"),
                "assigned": person,
                "created": created,
                "url": wr.get("url", ""),
            })

    return {
        "ok": True,
        "generated": datetime.now().isoformat(),
        "ado_base_url": f"https://dev.azure.com/{config['org']}/{config['project']}" if config else "",
        "sprint": {
            "name": iteration.get("name", "Unknown"),
            "start": start_date,
            "finish": finish_date,
        },
        "kpis": {
            "total_points": total_points,
            "remaining_points": remaining_points,
            "pct_burned": round((closed_points / total_points * 100) if total_points else 0),
            "active_prs": len(pull_requests),
        },
        "burndown": {
            "total_points": total_points,
            "remaining_points": remaining_points,
            "date": today_str,
            "history": burndown_history or [],
        },
        "states": dict(state_counts),
        "state_points": {k: v for k, v in state_points.items()},
        "team": team_response,
        "prs": pr_list,
        "risks": risks,
        "work_requests": wr_list,
    }
