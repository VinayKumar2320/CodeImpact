from __future__ import annotations

from typing import Any, cast

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.inference.predictor import RiskPredictionResult
from app.services.test_selection.optimizer import TestSelectionPlan

logger = get_logger(__name__)


class GitHubCheckRunPublisher:
    """
    Publishes informational GitHub Check Runs on pull requests
    with rich collapsible Markdown summaries and recommended test commands.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self.http_client = http_client

    def format_check_run_payload(
        self,
        prediction: RiskPredictionResult,
        test_plan: TestSelectionPlan,
        static_result: dict[str, Any],
        head_sha: str,
    ) -> dict[str, Any]:
        """Formats GitHub Check Run payload conforming to GitHub REST API."""
        tier = prediction.risk_tier.value
        score_pct = int(prediction.risk_score * 100)

        # Conclusion is informational ("neutral" or "success")
        conclusion = "neutral"
        if tier == "LOW":
            conclusion = "success"

        title = f"Risk: {tier} ({score_pct}%) | Tests: {test_plan.selected_tests_count} Recommended"

        summary_lines = [
            f"### 🛡️ CodeImpact Predictive Risk Assessment: **{tier}** ({score_pct}%)",
            "",
            f"**Model:** `{prediction.model_name}` v`{prediction.model_version}` | "
            f"**Confidence Interval:** `[{prediction.confidence_lower:.2f}, {prediction.confidence_upper:.2f}]` | "
            f"**Suite Time Savings:** **{test_plan.time_savings_percent:.1f}%**",
            "",
        ]

        # Top factors
        if prediction.top_risk_factors:
            summary_lines.append("**Top Contributing Risk Factors:**")
            for f in prediction.top_risk_factors[:3]:
                summary_lines.append(
                    f"- **{f.feature_name.replace('_', ' ').capitalize()}**: {f.human_explanation}"
                )
            summary_lines.append("")

        test_commands = " ".join([t.test_identifier for t in test_plan.recommended_tests])
        text_lines = [
            "### ⚡ Intelligent Test Selection",
            f"CodeImpact recommends executing **{test_plan.selected_tests_count}** of **{test_plan.total_suite_tests_count}** tests "
            f"saving **{test_plan.time_savings_percent:.1f}%** test execution time under budget.",
            "",
            "#### Quick Pytest Execution Command",
            "```bash",
            f"pytest {test_commands if test_commands else 'tests/'}",
            "```",
            "",
            "| Rank | Test Identifier | Evidence Level | Est. Duration |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for t in test_plan.recommended_tests[:10]:
            ev = t.evidence_level.replace("EVIDENCE_", "")
            text_lines.append(
                f"| #{t.rank} | `{t.test_identifier}` | `{ev}` | {t.estimated_duration_ms}ms |"
            )

        text_lines.extend(
            [
                "",
                "<details>",
                "<summary><b>🔍 Detailed Code Impact & Blast Radius</b></summary>",
                "",
                f"- **Files Modified:** {len(static_result.get('diff', {}).get('files', []))}",
                f"- **Affected Downstream Callers:** {static_result.get('dependencies', {}).get('affected_callers_count', 0)}",
                f"- **Betweenness Centrality:** {static_result.get('dependencies', {}).get('mean_betweenness_centrality', 0.0):.4f}",
                "",
                "</details>",
            ]
        )

        return {
            "name": "CodeImpact Change Risk Analyzer",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": title,
                "summary": "\n".join(summary_lines),
                "text": "\n".join(text_lines),
            },
        }

    async def publish(
        self,
        repo_full_name: str,
        commit_sha: str,
        payload: dict[str, Any],
        installation_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Submits Check Run payload to GitHub. If token is not provided (e.g. local dev),
        gracefully logs check run output locally.
        """
        if not installation_token:
            logger.info(
                f"[Local/Mock Mode] Check run prepared for {repo_full_name} @ {commit_sha[:7]}: "
                f"Title: {payload.get('output', {}).get('title')}"
            )
            return {"status": "published_locally", "payload": payload}

        url = f"{settings.GITHUB_API_BASE_URL}/repos/{repo_full_name}/check-runs"
        headers = {
            "Authorization": f"Bearer {installation_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        client = self.http_client or httpx.AsyncClient(timeout=15.0)
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            logger.info(f"Published GitHub Check Run for {repo_full_name} ({resp.status_code})")
            return cast(dict[str, Any], resp.json())
        except Exception as e:
            logger.error(f"Failed to publish GitHub Check Run to {url}: {e}")
            return {"status": "failed", "error": str(e)}
        finally:
            if not self.http_client:
                await client.aclose()


check_run_publisher = GitHubCheckRunPublisher()
