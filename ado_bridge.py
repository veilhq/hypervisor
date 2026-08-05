"""
ADO Bridge — Azure DevOps data fetching for the Hypervisor desktop app.

Extracted from hypervisor-app.py. All methods are standalone functions that
return dicts suitable for pushing to the frontend via PyWebView bridge.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_HYPERKIT_PYTHON = str(Path(__file__).parent.parent / ".hyperkit" / "python")
if _HYPERKIT_PYTHON not in sys.path:
    sys.path.insert(0, _HYPERKIT_PYTHON)

from hyper_logging import setup_logger  # noqa: E402

logger = setup_logger("hypervisor")

TOOLS_DIR = Path(__file__).parent / "tools"


def _get_client():
    """Import ADO modules and return (config, client) or raise."""
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        from ado_collector import load_config, ADOClient, ADOConfigError
    finally:
        if str(TOOLS_DIR) in sys.path:
            sys.path.remove(str(TOOLS_DIR))

    config = load_config()
    client = ADOClient(
        config["org"],
        pat=config.get("pat"),
        use_entra=config.get("use_entra", False),
    )
    return config, client


def refresh_ado_sprint():
    """Fetch core sprint data: iteration, work items, PRs, work requests, burndown.

    This is the fast-path call for the Sprint tab — skips source control
    and pipeline data entirely.

    Returns:
        dict with sprint payload or error information.
    """
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        from ado_collector import load_config, ADOClient, extract_top_level_items, ADOConfigError
        from ado_dashboard import build_dashboard_payload
        sys.path.remove(str(TOOLS_DIR)) if str(TOOLS_DIR) in sys.path else None
    except ImportError as e:
        return {"ok": False, "error": f"Failed to import ado modules: {e}"}

    try:
        config = load_config()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        client = ADOClient(config["org"], pat=config.get("pat"), use_entra=config.get("use_entra", False))

        # Step 1: Get current iteration
        iteration = client.get_current_iteration(config["project"], config["team"])
        if not iteration:
            return {"ok": False, "error": "No current iteration found."}

        attrs = iteration.get("attributes", {})
        iter_path = iteration.get("path", "")
        start_date = attrs.get("startDate", "")[:10]
        finish_date = attrs.get("finishDate", "")[:10]

        # Step 2: Get work item IDs
        iter_data = client.get_iteration_work_items(
            config["project"], config["team"], iteration["id"]
        )
        top_level_ids = extract_top_level_items(iter_data)

        # Step 3: Parallel fetch
        fields = [
            "System.Id", "System.Title", "System.State",
            "System.WorkItemType", "System.AssignedTo", "System.Tags",
            "Microsoft.VSTS.Scheduling.StoryPoints",
        ]

        wiql = (
            "SELECT [System.Id], [System.Title], [System.State], "
            "[System.AssignedTo], [System.CreatedDate] "
            "FROM WorkItems "
            "WHERE [System.TeamProject] = @project "
            "AND [System.WorkItemType] = 'Work Request' "
            "AND [System.State] <> 'Done' "
            "AND [System.State] <> 'Closed' "
            "AND [System.State] <> 'Removed' "
            "ORDER BY [System.CreatedDate] DESC"
        )

        work_items = []
        pull_requests = []
        work_requests = []
        burndown_history = []

        def fetch_work_items():
            return client.get_work_items(config["project"], top_level_ids, fields=fields)

        def fetch_pull_requests():
            return client.get_pull_requests(config["project"])

        def fetch_work_requests():
            return client.query_work_items_wiql(config["project"], wiql, top=50)

        def fetch_burndown():
            if iter_path and start_date and finish_date:
                return client.get_burndown_history(
                    config["org"], config["project"], iter_path, start_date, finish_date
                )
            return []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(fetch_work_items): "work_items",
                executor.submit(fetch_pull_requests): "pull_requests",
                executor.submit(fetch_work_requests): "work_requests",
                executor.submit(fetch_burndown): "burndown",
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    result = future.result()
                    if key == "work_items":
                        work_items = result
                    elif key == "pull_requests":
                        pull_requests = result
                    elif key == "work_requests":
                        work_requests = result
                    elif key == "burndown":
                        burndown_history = result
                except Exception as e:
                    logger.warning("Failed to fetch %s: %s", key, e)

        return build_dashboard_payload(
            iteration, work_items, pull_requests, work_requests, config,
            burndown_history,
        )

    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_ado_source():
    """Fetch source control data: repos, commits, branches, conflict detection.

    Returns:
        dict with source payload or error information.
    """
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        from ado_collector import load_config, ADOClient, ADOConfigError
        from ado_dashboard import detect_conflicts
        sys.path.remove(str(TOOLS_DIR)) if str(TOOLS_DIR) in sys.path else None
    except ImportError as e:
        return {"ok": False, "error": f"Failed to import ado modules: {e}"}

    try:
        config = load_config()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        client = ADOClient(config["org"], pat=config.get("pat"), use_entra=config.get("use_entra", False))
        repos = client.get_repos(config["project"])

        commits = []
        branches = []
        conflicts = []

        if repos:
            with ThreadPoolExecutor(max_workers=2) as executor:
                commit_future = executor.submit(
                    client.get_recent_commits, config["project"], repos, 30
                )
                branch_future = executor.submit(
                    client.get_branches_overview, config["project"], repos
                )

                try:
                    commits = commit_future.result()
                except Exception as e:
                    logger.warning("Failed to fetch commits: %s", e)

                try:
                    branches = branch_future.result()
                except Exception as e:
                    logger.warning("Failed to fetch branches: %s", e)

            if branches:
                try:
                    branch_diffs = client.get_branch_diffs(
                        config["project"], repos, branches
                    )
                    conflicts = detect_conflicts(branch_diffs)
                except Exception as e:
                    logger.warning("Failed to detect branch conflicts: %s", e)

        return {
            "ok": True,
            "commits": commits,
            "branches": branches,
            "conflicts": conflicts,
            "repo_count": len(repos),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_ado_dashboard():
    """Full dashboard refresh — fetches all tabs in parallel.

    Returns:
        dict with complete dashboard data or error information.
    """
    with ThreadPoolExecutor(max_workers=3) as executor:
        sprint_future = executor.submit(refresh_ado_sprint)
        source_future = executor.submit(refresh_ado_source)
        pipelines_future = executor.submit(refresh_ado_pipelines_full)

    sprint_data = sprint_future.result()
    if not sprint_data or not sprint_data.get("ok"):
        return sprint_data

    # Merge source data
    source_data = source_future.result()
    if source_data and source_data.get("ok"):
        sprint_data["commits"] = source_data.get("commits", [])
        sprint_data["branches"] = source_data.get("branches", [])
        sprint_data["conflicts"] = source_data.get("conflicts", [])
        sprint_data["repo_count"] = source_data.get("repo_count", 0)

    # Merge pipeline data
    pipeline_data = pipelines_future.result()
    if pipeline_data and pipeline_data.get("ok"):
        sprint_data["pipeline_runs"] = pipeline_data.get("pipeline_runs", [])
        sprint_data["active_pipelines"] = pipeline_data.get("active_pipelines", [])

    return sprint_data


def refresh_ado_pipelines_full():
    """Fetch both recent and active pipeline runs.

    Returns:
        dict with pipeline_runs and active_pipelines or error.
    """
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        from ado_collector import load_config, ADOClient, ADOConfigError
        sys.path.remove(str(TOOLS_DIR)) if str(TOOLS_DIR) in sys.path else None
    except ImportError as e:
        return {"ok": False, "error": f"Failed to import ado modules: {e}"}

    try:
        config = load_config()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        client = ADOClient(config["org"], pat=config.get("pat"), use_entra=config.get("use_entra", False))

        with ThreadPoolExecutor(max_workers=2) as executor:
            runs_future = executor.submit(client.get_pipeline_runs, config["project"], 5)
            active_future = executor.submit(client.get_active_pipeline_runs, config["project"])

            pipeline_runs = []
            active_pipelines = []
            try:
                pipeline_runs = runs_future.result()
            except Exception as e:
                logger.warning("Failed to fetch pipeline runs: %s", e)
            try:
                active_pipelines = active_future.result()
            except Exception as e:
                logger.warning("Failed to fetch active pipelines: %s", e)

        return {"ok": True, "pipeline_runs": pipeline_runs, "active_pipelines": active_pipelines}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_ado_pipelines():
    """Lightweight poll — fetch only active/queued pipeline runs.

    Used by the 60s auto-poll on the Pipelines tab.

    Returns:
        dict with active_pipelines list or error.
    """
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        from ado_collector import load_config, ADOClient, ADOConfigError
        sys.path.remove(str(TOOLS_DIR)) if str(TOOLS_DIR) in sys.path else None
    except ImportError as e:
        return {"ok": False, "error": f"Failed to import ado modules: {e}"}

    try:
        config = load_config()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    try:
        client = ADOClient(config["org"], pat=config.get("pat"), use_entra=config.get("use_entra", False))
        active_pipelines = client.get_active_pipeline_runs(config["project"])
        return {"ok": True, "active_pipelines": active_pipelines}
    except Exception as e:
        return {"ok": False, "error": str(e)}
