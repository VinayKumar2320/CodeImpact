from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.schemas.github import GitHubCommitSummary

logger = get_logger(__name__)


@dataclass
class FileChurnStats:
    file_path: str
    commit_count_30d: int = 0
    distinct_authors_count: int = 0
    file_age_days: int = 0
    historical_churn_lines: int = 0


@dataclass
class RepositoryChurnMetrics:
    total_commits_analyzed: int = 0
    mean_change_frequency: float = 0.0
    max_change_frequency: int = 0
    distinct_contributors_count: int = 0
    mean_file_age_days: float = 0.0
    recent_change_concentration: float = 0.0  # Gini coefficient of edit distribution [0-1]
    file_churn_breakdown: list[FileChurnStats] = field(default_factory=list)


class GitChurnAnalyzer:
    """
    Computes file-level and repository-level historical churn, contributor diversity,
    and change concentration metrics from commit history.
    """

    def analyze_churn(
        self,
        commits_by_file: dict[str, list[GitHubCommitSummary]],
        window_days: int = 30,
        now: datetime | None = None,
    ) -> RepositoryChurnMetrics:
        current_time = now or datetime.now(UTC)
        cutoff_date = current_time - timedelta(days=window_days)

        file_breakdown: list[FileChurnStats] = []
        all_authors: set[str] = set()
        file_commit_counts: list[int] = []
        file_ages: list[int] = []

        for file_path, commits in commits_by_file.items():
            recent_commits = [c for c in commits if c.timestamp >= cutoff_date]
            file_authors = {c.author_name for c in commits}
            all_authors.update(file_authors)

            # Age of file: difference between current time and oldest commit
            file_age = 0
            if commits:
                oldest_commit = min(commits, key=lambda c: c.timestamp)
                file_age = max(0, (current_time - oldest_commit.timestamp).days)

            stats = FileChurnStats(
                file_path=file_path,
                commit_count_30d=len(recent_commits),
                distinct_authors_count=len(file_authors),
                file_age_days=file_age,
                historical_churn_lines=len(commits) * 15,  # heuristic average lines per commit
            )
            file_breakdown.append(stats)
            file_commit_counts.append(len(recent_commits))
            file_ages.append(file_age)

        # Compute Gini coefficient of change concentration
        concentration = self._compute_gini_coefficient(file_commit_counts)

        mean_freq = (
            round(sum(file_commit_counts) / len(file_commit_counts), 2)
            if file_commit_counts
            else 0.0
        )
        max_freq = max(file_commit_counts) if file_commit_counts else 0
        mean_age = round(sum(file_ages) / len(file_ages), 1) if file_ages else 0.0

        return RepositoryChurnMetrics(
            total_commits_analyzed=sum(len(c) for c in commits_by_file.values()),
            mean_change_frequency=mean_freq,
            max_change_frequency=max_freq,
            distinct_contributors_count=len(all_authors),
            mean_file_age_days=mean_age,
            recent_change_concentration=concentration,
            file_churn_breakdown=file_breakdown,
        )

    def _compute_gini_coefficient(self, values: list[int]) -> float:
        """
        Compute Gini coefficient [0.0 - 1.0] for change concentration across files.
        0.0 = completely equal distribution of changes across all files.
        1.0 = all changes concentrated in a single file.
        """
        if not values or len(values) <= 1:
            return 0.0

        sorted_values = sorted(values)
        n = len(sorted_values)
        total = sum(sorted_values)

        if total == 0:
            return 0.0

        cumulative_sum = 0
        sum_of_ranks = 0
        for i, val in enumerate(sorted_values):
            cumulative_sum += val
            sum_of_ranks += (2 * (i + 1) - n - 1) * val

        gini = sum_of_ranks / (n * total)
        return round(max(0.0, min(1.0, float(gini))), 3)


git_churn_analyzer = GitChurnAnalyzer()
