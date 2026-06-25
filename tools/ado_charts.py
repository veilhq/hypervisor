"""
ADO Charts — SVG chart generators for the ADO dashboard.

Generates inline SVG that uses Hypervisor's CSS custom properties for theming.
Charts render in the terminal aesthetic: monospace labels, hard edges, no curves.

All SVGs use currentColor and var(--accent), var(--warm), var(--cool), var(--comp)
so they automatically adapt to the user's chosen accent color and theme mode.
"""

from collections import Counter


# ---------------------------------------------------------------------------
# Color palette — maps to Hypervisor CSS variables
# ---------------------------------------------------------------------------

# These are referenced as CSS vars in the SVG style blocks
CHART_COLORS = [
    "var(--accent)",      # green (primary)
    "var(--warm)",        # amber
    "var(--cool)",        # cyan
    "var(--comp)",        # red
    "var(--text-muted)",  # grey
    "var(--accent-dim)",  # dim green
]

# State-specific colors for burndown/status charts
STATE_COLORS = {
    "Closed": "var(--accent)",
    "Review": "var(--warm)",
    "In Progress": "var(--cool)",
    "Ready": "var(--text-muted)",
    "Hold": "var(--comp)",
    "Active": "var(--comp)",
    "New": "var(--text-dim)",
}


def _get_state_color(state):
    """Get the CSS variable color for a work item state."""
    return STATE_COLORS.get(state, "var(--text-dim)")


# ---------------------------------------------------------------------------
# Horizontal Bar Chart
# ---------------------------------------------------------------------------

def horizontal_bar_chart(data, title="", width=600, bar_height=28, gap=6):
    """Generate an SVG horizontal bar chart.

    Args:
        data: list of (label, value) tuples
        title: optional chart title
        width: total SVG width
        bar_height: height of each bar
        gap: vertical gap between bars

    Returns:
        SVG string ready for embedding in markdown.
    """
    if not data:
        return ""

    max_val = max(v for _, v in data)
    if max_val == 0:
        max_val = 1

    label_width = 120  # space for labels on the left
    value_width = 50   # space for value text on the right
    chart_width = width - label_width - value_width - 20
    title_height = 30 if title else 0
    chart_height = len(data) * (bar_height + gap) + title_height + 10

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {chart_height}" '
                 f'style="width:100%;max-width:{width}px;height:auto;font-family:var(--font);'
                 f'background:var(--bg-card);border:1px solid var(--border);margin:1rem 0">')

    # Title
    if title:
        lines.append(f'  <text x="{width//2}" y="20" text-anchor="middle" '
                     f'fill="var(--text-bright)" font-size="12" '
                     f'text-transform="uppercase" letter-spacing="1">{title}</text>')

    # Bars
    y_offset = title_height + 5
    for i, (label, value) in enumerate(data):
        y = y_offset + i * (bar_height + gap)
        bar_w = (value / max_val) * chart_width if max_val > 0 else 0
        color = CHART_COLORS[i % len(CHART_COLORS)]

        # Label
        lines.append(f'  <text x="{label_width - 8}" y="{y + bar_height // 2 + 4}" '
                     f'text-anchor="end" fill="var(--text)" font-size="11">{label}</text>')

        # Bar background (track)
        lines.append(f'  <rect x="{label_width}" y="{y}" width="{chart_width}" height="{bar_height}" '
                     f'fill="var(--bg-surface)" stroke="var(--border)" stroke-width="1"/>')

        # Bar fill
        if bar_w > 0:
            lines.append(f'  <rect x="{label_width}" y="{y}" width="{bar_w:.1f}" height="{bar_height}" '
                         f'fill="{color}" opacity="0.85"/>')

        # Value text
        lines.append(f'  <text x="{label_width + chart_width + 8}" y="{y + bar_height // 2 + 4}" '
                     f'fill="var(--text-muted)" font-size="11">{value}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Donut / Ring Chart
# ---------------------------------------------------------------------------

def donut_chart(data, title="", size=200):
    """Generate an SVG donut chart.

    Args:
        data: list of (label, value) tuples
        title: optional center text
        size: SVG width/height

    Returns:
        SVG string.
    """
    if not data:
        return ""

    total = sum(v for _, v in data)
    if total == 0:
        return ""

    cx, cy = size // 2, size // 2
    radius = size * 0.35
    stroke_width = size * 0.12
    inner_radius = radius - stroke_width / 2

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
                 f'style="width:{size}px;height:{size}px;font-family:var(--font);'
                 f'background:var(--bg-card);border:1px solid var(--border);margin:1rem 0">')

    # Background circle
    lines.append(f'  <circle cx="{cx}" cy="{cy}" r="{radius}" '
                 f'fill="none" stroke="var(--border)" stroke-width="{stroke_width}"/>')

    # Segments
    import math
    angle_offset = -90  # start from top
    circumference = 2 * math.pi * radius

    for i, (label, value) in enumerate(data):
        if value == 0:
            continue
        pct = value / total
        dash_len = pct * circumference
        gap_len = circumference - dash_len
        color = _get_state_color(label) if label in STATE_COLORS else CHART_COLORS[i % len(CHART_COLORS)]

        # Rotate to correct position
        rotation = angle_offset
        lines.append(f'  <circle cx="{cx}" cy="{cy}" r="{radius}" '
                     f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
                     f'stroke-dasharray="{dash_len:.2f} {gap_len:.2f}" '
                     f'stroke-dashoffset="0" '
                     f'transform="rotate({rotation:.1f} {cx} {cy})" opacity="0.9"/>')
        angle_offset += pct * 360

    # Center text
    if title:
        lines.append(f'  <text x="{cx}" y="{cy - 6}" text-anchor="middle" '
                     f'fill="var(--text-bright)" font-size="18" font-weight="bold">{total}</text>')
        lines.append(f'  <text x="{cx}" y="{cy + 12}" text-anchor="middle" '
                     f'fill="var(--text-muted)" font-size="10">{title}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stacked Progress Bar
# ---------------------------------------------------------------------------

def stacked_bar(data, width=600, height=32):
    """Generate a single stacked horizontal bar showing proportions.

    Args:
        data: list of (label, value) tuples
        width: SVG width
        height: bar height

    Returns:
        SVG string with bar + legend below.
    """
    if not data:
        return ""

    total = sum(v for _, v in data)
    if total == 0:
        return ""

    legend_height = 20 * ((len(data) + 2) // 3)  # 3 items per row
    svg_height = height + legend_height + 16

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {svg_height}" '
                 f'style="width:100%;max-width:{width}px;height:auto;font-family:var(--font);'
                 f'background:var(--bg-card);border:1px solid var(--border);margin:1rem 0;padding:8px">')

    # Stacked bar
    x_offset = 0
    bar_y = 4
    for i, (label, value) in enumerate(data):
        if value == 0:
            continue
        seg_width = (value / total) * (width - 16)
        color = _get_state_color(label) if label in STATE_COLORS else CHART_COLORS[i % len(CHART_COLORS)]

        lines.append(f'  <rect x="{x_offset + 8}" y="{bar_y}" '
                     f'width="{seg_width:.1f}" height="{height}" '
                     f'fill="{color}" opacity="0.85"/>')
        x_offset += seg_width

    # Border around the full bar
    lines.append(f'  <rect x="8" y="{bar_y}" width="{width - 16}" height="{height}" '
                 f'fill="none" stroke="var(--border)" stroke-width="1"/>')

    # Legend
    legend_y = height + 20
    items_per_row = 3
    for i, (label, value) in enumerate(data):
        row = i // items_per_row
        col = i % items_per_row
        lx = 12 + col * (width // items_per_row)
        ly = legend_y + row * 18
        color = _get_state_color(label) if label in STATE_COLORS else CHART_COLORS[i % len(CHART_COLORS)]
        pct = (value / total * 100) if total else 0

        # Color swatch
        lines.append(f'  <rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}" opacity="0.85"/>')
        # Label text
        lines.append(f'  <text x="{lx + 14}" y="{ly + 9}" fill="var(--text)" font-size="10">'
                     f'{label}: {value} ({pct:.0f}%)</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sparkline (mini line chart for trends)
# ---------------------------------------------------------------------------

def sparkline(values, width=200, height=40, color="var(--accent)"):
    """Generate a tiny inline sparkline SVG.

    Args:
        values: list of numeric values (time series)
        width: SVG width
        height: SVG height
        color: stroke color (CSS variable)

    Returns:
        Inline SVG string.
    """
    if not values or len(values) < 2:
        return ""

    min_v = min(values)
    max_v = max(values)
    v_range = max_v - min_v if max_v != min_v else 1
    padding = 4

    points = []
    for i, v in enumerate(values):
        x = padding + (i / (len(values) - 1)) * (width - 2 * padding)
        y = height - padding - ((v - min_v) / v_range) * (height - 2 * padding)
        points.append(f"{x:.1f},{y:.1f}")

    polyline = " ".join(points)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'style="width:{width}px;height:{height}px;display:inline-block;vertical-align:middle">'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="square"/>'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" '
        f'r="2.5" fill="{color}"/>'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Team Workload Grid
# ---------------------------------------------------------------------------

def team_grid(team_data, width=600):
    """Generate a grid showing team member workload with state-colored blocks.

    Args:
        team_data: dict of {name: [state1, state2, ...]}
        width: SVG width

    Returns:
        SVG string.
    """
    if not team_data:
        return ""

    block_size = 20
    gap = 4
    label_width = 140
    row_height = block_size + gap + 14  # block + gap + name text
    max_items = max(len(states) for states in team_data.values())
    chart_width = max(width, label_width + max_items * (block_size + gap) + 20)
    chart_height = len(team_data) * row_height + 20

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {chart_width} {chart_height}" '
                 f'style="width:100%;max-width:{chart_width}px;height:auto;font-family:var(--font);'
                 f'background:var(--bg-card);border:1px solid var(--border);margin:1rem 0;padding:8px">')

    for row_idx, (name, states) in enumerate(sorted(team_data.items())):
        y = 10 + row_idx * row_height

        # Name label
        lines.append(f'  <text x="8" y="{y + block_size // 2 + 4}" '
                     f'fill="var(--text-bright)" font-size="11">{name}</text>')

        # State blocks
        for col_idx, state in enumerate(sorted(states)):
            x = label_width + col_idx * (block_size + gap)
            color = _get_state_color(state)
            lines.append(f'  <rect x="{x}" y="{y}" width="{block_size}" height="{block_size}" '
                         f'fill="{color}" opacity="0.8" stroke="var(--border)" stroke-width="0.5"/>')
            # Tiny state initial inside the block
            initial = state[0].upper()
            lines.append(f'  <text x="{x + block_size // 2}" y="{y + block_size // 2 + 4}" '
                         f'text-anchor="middle" fill="var(--bg)" font-size="9" font-weight="bold">'
                         f'{initial}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PR Timeline
# ---------------------------------------------------------------------------

def pr_timeline(prs, width=600, row_height=28):
    """Generate a timeline showing PR age (days open).

    Args:
        prs: list of dicts with 'title', 'author', 'created', 'age_days'
        width: SVG width
        row_height: height per PR row

    Returns:
        SVG string.
    """
    if not prs:
        return ""

    max_age = max(pr.get("age_days", 1) for pr in prs)
    if max_age == 0:
        max_age = 1

    label_width = 200
    chart_width = width - label_width - 60
    svg_height = len(prs) * row_height + 20

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {svg_height}" '
                 f'style="width:100%;max-width:{width}px;height:auto;font-family:var(--font);'
                 f'background:var(--bg-card);border:1px solid var(--border);margin:1rem 0;padding:8px">')

    for i, pr in enumerate(prs):
        y = 10 + i * row_height
        age = pr.get("age_days", 0)
        bar_w = (age / max_age) * chart_width

        # Color based on age (green < 3 days, amber 3-7, red > 7)
        if age <= 2:
            color = "var(--accent)"
        elif age <= 7:
            color = "var(--warm)"
        else:
            color = "var(--comp)"

        # Truncated title
        title = pr.get("title", "")[:30]
        if len(pr.get("title", "")) > 30:
            title += "..."

        # Label
        lines.append(f'  <text x="{label_width - 8}" y="{y + row_height // 2 + 3}" '
                     f'text-anchor="end" fill="var(--text)" font-size="10">{title}</text>')

        # Bar
        lines.append(f'  <rect x="{label_width}" y="{y + 4}" '
                     f'width="{bar_w:.1f}" height="{row_height - 8}" '
                     f'fill="{color}" opacity="0.8"/>')

        # Age label
        lines.append(f'  <text x="{label_width + bar_w + 6}" y="{y + row_height // 2 + 3}" '
                     f'fill="var(--text-muted)" font-size="10">{age}d</text>')

    lines.append('</svg>')
    return "\n".join(lines)
