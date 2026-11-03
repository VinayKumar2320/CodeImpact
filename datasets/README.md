# CodeImpact Historical Datasets

## Purpose & Scope
This directory contains dataset specifications, collection manifests, schemas, and summary statistics for pull requests gathered to train and evaluate the post-merge regression risk prediction models.

## Dataset Fields
Each pull request record captures pre-merge characteristics alongside post-merge verification:

| Field Name | Type | Description |
|---|---|---|
| `repo_identifier` | string | `owner/repo` naming key |
| `pr_number` | integer | GitHub pull request identifier |
| `base_sha` | string (40 hex) | Target branch merge base commit SHA |
| `head_sha` | string (40 hex) | Pull request tip commit SHA |
| `created_at` | timestamp (ISO-8601) | PR creation timestamp |
| `merged_at` | timestamp (ISO-8601) | PR merge timestamp |
| `lines_added` | integer | Total line additions across all diff hunks |
| `lines_deleted` | integer | Total line deletions across all diff hunks |
| `files_changed_count` | integer | Total count of modified files |
| `functions_modified_count` | integer | AST-detected modified functions |
| `classes_modified_count` | integer | AST-detected modified classes |
| `cyclomatic_complexity_mean` | float | Mean cyclomatic complexity across modified functions |
| `cyclomatic_complexity_max` | integer | Maximum function cyclomatic complexity |
| `complexity_delta` | float | Change in cyclomatic complexity relative to base branch |
| `churn_frequency_30d` | integer | Historical commit count in the past 30 days on touched files |
| `distinct_authors_count` | integer | Distinct contributors who touched modified files in past 90 days |
| `dependency_fan_in` | integer | In-degree of modified functions (callers) in dependency graph |
| `dependency_fan_out` | integer | Out-degree of modified functions (callees) in dependency graph |
| `betweenness_centrality` | float | NetworkX betweenness centrality of modified functions |
| `test_coverage_ratio` | float | Pre-merge branch coverage ratio on modified functions [0-1] |
| `is_regression` | boolean | Binary post-merge ground truth label (1 = regression, 0 = stable) |
| `label_tier` | integer | Ground truth confidence: 1 (revert/issue), 2 (bugfix PR), 3 (excluded) |
| `label_provenance` | string | URL or commit hash establishing regression justification |
| `split` | string | Chronological partition: `train`, `val`, `test`, `cross_repo_test` |

## Regression Labeling Methodology
To avoid common pitfalls in mining software repositories (MSR), CodeImpact enforces a transparent multi-tier ground truth labeling hierarchy:
- **Tier 1 (Confirmed Incident / Revert)**: The pull request was explicitly reverted via `git revert`, or a subsequent issue tagged `type: regression` directly cited the merge commit.
- **Tier 2 (Associated Bug-Fix PR)**: A subsequent pull request modifying one or more of the same AST function nodes was merged within a 30-day post-merge observation window and referenced a bug fix.
- **Tier 3 (Ambiguous / Unconfirmed)**: Commits with vague messages (e.g., "fix typo", "minor update") or unconfirmed CI failures. *These are strictly excluded from supervised training* to prevent label contamination.

## Leakage Prevention Protocol
1. **Chronological Splitting**: For each repository, examples are sorted by `merged_at`. Train sets are strictly older than validation sets, which are strictly older than test sets.
2. **Cross-Repository Holdout**: Specific repositories (e.g. `pallets/flask`) are held out entirely from training to benchmark cross-project domain adaptation.
