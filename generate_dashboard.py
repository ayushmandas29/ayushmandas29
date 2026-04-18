import os
import json
import requests
from datetime import datetime, timedelta

TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = 'ayushmandas29'

def get_graphql_data():
    query = """
    query {
      user(login: "%s") {
        name
        login
        contributionsCollection {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalRepositoriesWithContributedCommits
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            stargazerCount
          }
        }
      }
      search(query: "author:%s type:pr is:merged", type: ISSUE, first: 1) {
        issueCount
      }
    }
    """ % (USERNAME, USERNAME)

    headers = {'Authorization': f'Bearer {TOKEN}'} if TOKEN else {}
    if not TOKEN:
        print("WARNING: No token provided. Skipping graphql request.")
        return None
        
    response = requests.post('https://api.github.com/graphql', json={'query': query}, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data: {response.text}")
        return None

def compute_metrics(data):
    if 'errors' in data:
        print("GraphQL Error:", data['errors'])
        return None

    user_node = data['data']['user']
    if not user_node:
        print("User not found.")
        return None

    collections = user_node['contributionsCollection']
    
    # 1. Basics
    total_commits = collections['totalCommitContributions']
    total_issues = collections['totalIssueContributions']
    total_prs = collections['totalPullRequestContributions']
    merged_prs = data['data']['search']['issueCount']
    repos_contributed_to = collections['totalRepositoriesWithContributedCommits']
    
    # Stars
    total_stars = sum([repo['stargazerCount'] for repo in user_node['repositories']['nodes']])
    
    # Calendar
    calendar = collections['contributionCalendar']
    current_streak = 0
    longest_streak = 0
    active_days = 0
    
    days = []
    for week in calendar['weeks']:
        for day in week['contributionDays']:
            days.append(day)
            
    today = datetime.utcnow().date()
    streak_temp = 0
    
    # Longest streak calculation
    for day in days:
        if day['contributionCount'] > 0:
            streak_temp += 1
            longest_streak = max(longest_streak, streak_temp)
            active_days += 1
        else:
            streak_temp = 0
            
    # Current streak calculation (iterate backwards)
    for day in reversed(days):
        if day['contributionCount'] > 0:
            current_streak += 1
        elif day['date'] != today.strftime("%Y-%m-%d"):
            # break if yesterday had 0 contributions
            if current_streak > 0:
                 break

    consistency_score = round((active_days / 365.0) * 100, 2)
    
    return {
        "username": USERNAME,
        "metrics": {
            "total_commits": total_commits,
            "total_prs": total_prs,
            "merged_prs": merged_prs,
            "total_issues": total_issues,
            "total_stars": total_stars,
            "repositories_contributed_to": repos_contributed_to,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "consistency_score": consistency_score,
            "active_days": active_days
        },
        "last_updated": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    if not TOKEN:
        # Fallback dummy data for local testing without token
         metrics = {
            "username": USERNAME,
            "metrics": {
                "total_commits": 0,
                "total_prs": 0,
                "merged_prs": 0,
                "total_issues": 0,
                "total_stars": 0,
                "repositories_contributed_to": 0,
                "current_streak": 0,
                "longest_streak": 0,
                "consistency_score": 0.0,
                "active_days": 0
            },
            "last_updated": datetime.utcnow().isoformat()
        }
         os.makedirs("dashboard", exist_ok=True)
         with open("dashboard/stats.json", "w") as f:
             json.dump(metrics, f, indent=4)
         print("Created fallback stats.json.")
    else:
        data = get_graphql_data()
        if data:
            metrics = compute_metrics(data)
            if metrics:
                os.makedirs("dashboard", exist_ok=True)
                with open("dashboard/stats.json", "w") as f:
                    json.dump(metrics, f, indent=4)
                print("Stats updated successfully.")
            else:
                print("Failed to compute metrics.")
        else:
            print("Failed to get data.")
