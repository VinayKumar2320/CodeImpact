from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.github import GitHubCommitSummary
from app.services.analysis.churn_analyzer import GitChurnAnalyzer


def test_git_churn_analyzer_metrics():
    now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC)

    commits_auth = [
        GitHubCommitSummary(
            sha="c1",
            author_name="Alice",
            message="Add login",
            timestamp=now - timedelta(days=5),
        ),
        GitHubCommitSummary(
            sha="c2",
            author_name="Bob",
            message="Fix auth leak",
            timestamp=now - timedelta(days=12),
        ),
        GitHubCommitSummary(
            sha="c3",
            author_name="Alice",
            message="Refactor token",
            timestamp=now - timedelta(days=45),  # outside 30d
        ),
    ]

    commits_util = [
        GitHubCommitSummary(
            sha="c4",
            author_name="Charlie",
            message="Add string helper",
            timestamp=now - timedelta(days=2),
        ),
    ]

    commits_by_file = {
        "app/auth.py": commits_auth,
        "app/util.py": commits_util,
    }

    analyzer = GitChurnAnalyzer()
    metrics = analyzer.analyze_churn(commits_by_file, window_days=30, now=now)

    assert metrics.total_commits_analyzed == 4
    assert metrics.distinct_contributors_count == 3
    assert len(metrics.file_churn_breakdown) == 2

    auth_breakdown = next(b for b in metrics.file_churn_breakdown if b.file_path == "app/auth.py")
    assert auth_breakdown.commit_count_30d == 2  # c1 and c2
    assert auth_breakdown.distinct_authors_count == 2
    assert auth_breakdown.file_age_days == 45


def test_gini_coefficient_calculation():
    analyzer = GitChurnAnalyzer()
    # Equal distribution
    assert analyzer._compute_gini_coefficient([5, 5, 5, 5]) == 0.0
    # Skewed distribution
    assert analyzer._compute_gini_coefficient([0, 0, 0, 20]) > 0.5
