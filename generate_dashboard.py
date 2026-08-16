import json
import os
import re
from datetime import datetime, timezone, timedelta

import requests

TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = "ayushmandas29"
GRAPHQL_URL = "https://api.github.com/graphql"
IST = timezone(timedelta(hours=5, minutes=30))


def get_graphql_data():
    query = f"""
    query {{
      user(login: "{USERNAME}") {{
        name
        login
        contributionsCollection {{
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalRepositoriesWithContributedCommits
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{
                contributionCount
                date
              }}
            }}
          }}
        }}
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {{
          nodes {{
            stargazerCount
          }}
        }}
      }}
    }}
    """

    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not available")

    response = requests.post(
        GRAPHQL_URL,
        json={"query": query},
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    if payload.get("errors"):
        raise RuntimeError(payload["errors"])

    return payload["data"]["user"]


def calculate_streak(calendar):
    days = [
        day
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]
    days.sort(key=lambda day: day["date"])

    counts = {day["date"]: day["contributionCount"] for day in days}
    today = datetime.now(IST).date()

    # GitHub's current streak can continue through today when today has
    # no contribution yet; otherwise start from the most recent day.
    if counts.get(today.isoformat(), 0) > 0:
        cursor = today
    else:
        cursor = today - timedelta(days=1)

    current_streak = 0
    while counts.get(cursor.isoformat(), 0) > 0:
        current_streak += 1
        cursor -= timedelta(days=1)

    longest_streak = 0
    running = 0
    active_days = 0

    for day in days:
        if day["contributionCount"] > 0:
            running += 1
            active_days += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0

    return current_streak, longest_streak, active_days


def compute_metrics(user):
    collections = user["contributionsCollection"]
    calendar = collections["contributionCalendar"]

    current_streak, longest_streak, active_days = calculate_streak(calendar)

    total_stars = sum(
        repo["stargazerCount"]
        for repo in user["repositories"]["nodes"]
    )

    return {
        "username": USERNAME,
        "metrics": {
            "total_commits": collections["totalCommitContributions"],
            "total_prs": collections["totalPullRequestContributions"],
            "total_reviews": collections["totalPullRequestReviewContributions"],
            "total_issues": collections["totalIssueContributions"],
            "total_stars": total_stars,
            "repositories_contributed_to": collections[
                "totalRepositoriesWithContributedCommits"
            ],
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "consistency_score": round((active_days / 365.0) * 100, 2),
            "active_days": active_days,
        },
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def update_readme(metrics):
    with open("README.md", "r", encoding="utf-8") as file:
        readme = file.read()

    m = metrics["metrics"]

    table_html = f"""<!-- START_CUSTOM_METRICS -->
<div align="center">
  <h3>⚡ GitHub Analytics</h3>
  <table width="100%">
    <tr align="center">
      <td><b>Total Commits:</b><br>{m['total_commits']}</td>
      <td><b>Pull Requests:</b><br>{m['total_prs']}</td>
      <td><b>Reviews:</b><br>{m['total_reviews']}</td>
      <td><b>Stargazers:</b><br>{m['total_stars']}</td>
    </tr>
    <tr align="center">
      <td><b>Longest Streak:</b><br>{m['longest_streak']} days</td>
      <td><b>Current Streak:</b><br>{m['current_streak']} days</td>
      <td><b>Active Days:</b><br>{m['active_days']}</td>
      <td><b>Consistency:</b><br>{m['consistency_score']}%</td>
    </tr>
  </table>
  <p><i>Automatically synchronized from GitHub contribution data.</i></p>
</div>
<!-- END_CUSTOM_METRICS -->"""

    pattern = r"<!-- START_CUSTOM_METRICS -->.*?<!-- END_CUSTOM_METRICS -->"
    updated = re.sub(pattern, table_html, readme, flags=re.DOTALL)

    with open("README.md", "w", encoding="utf-8") as file:
        file.write(updated)


def main():
    user = get_graphql_data()
    if not user:
        raise RuntimeError(f"GitHub user '{USERNAME}' was not found")

    metrics = compute_metrics(user)

    os.makedirs("dashboard", exist_ok=True)
    with open("dashboard/stats.json", "w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=4)

    update_readme(metrics)

    print(f"Current streak: {metrics['metrics']['current_streak']} days")
    print(f"Longest streak: {metrics['metrics']['longest_streak']} days")


if __name__ == "__main__":
    main()
