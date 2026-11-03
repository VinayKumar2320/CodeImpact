from __future__ import annotations

from typing import Any, cast

import httpx

from app.core.config import settings
from app.core.logging import get_logger

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
        prediction: Any,
        test_plan: Any,
        static_result: dict[str, Any],
        head_sha: str,
    ) -> dict[str, Any]:
        """Formats GitHub Check Run payload conforming to GitHub REST API."""
        # Normalize prediction
        if hasattr(prediction, "risk_tier"):
            tier_val = getattr(prediction.risk_tier, "value", prediction.risk_tier)
            score = float(prediction.risk_score)
            model_name = getattr(prediction, "model_name", "RiskPredictor")
            model_ver = getattr(prediction, "model_version", "1.0.0")
            ci_lower = float(getattr(prediction, "confidence_lower", score * 0.9))
            ci_upper = float(getattr(prediction, "confidence_upper", min(1.0, score * 1.1)))
            raw_factors = getattr(prediction, "top_risk_factors", []) or []
        elif isinstance(prediction, dict):
            tier_val = prediction.get("risk_tier", "MEDIUM")
            if hasattr(tier_val, "value"):
                tier_val = tier_val.value
            score = float(prediction.get("risk_score", 0.5))
            model_name = prediction.get("model_name", "RiskPredictor")
            model_ver = prediction.get("model_version", "1.0.0")
            ci_lower = float(prediction.get("confidence_lower", score * 0.9))
            ci_upper = float(prediction.get("confidence_upper", min(1.0, score * 1.1)))
            raw_factors = prediction.get("top_risk_factors", []) or []
        else:
            tier_val = "MEDIUM"
            score = 0.5
            model_name = "RiskPredictor"
            model_ver = "1.0.0"
            ci_lower, ci_upper = 0.4, 0.6
            raw_factors = []

        tier = str(tier_val).upper()
        score_pct = int(score * 100)

        # Normalize test_plan
        if hasattr(test_plan, "selected_tests_count"):
            selected_count = test_plan.selected_tests_count
            total_count = test_plan.total_suite_tests_count
            time_savings = test_plan.time_savings_percent
            recs = test_plan.recommended_tests
        elif isinstance(test_plan, dict):
            selected_count = test_plan.get("selected_tests_count", 0)
            total_count = test_plan.get("total_suite_tests_count", 0)
            time_savings = test_plan.get("time_savings_percent", 0.0)
            recs = test_plan.get("recommended_tests", [])
        else:
            selected_count = 0
            total_count = 0
            time_savings = 0.0
            recs = []

        conclusion = "neutral"
        if tier == "LOW":
            conclusion = "success"

        title = f"Risk: {tier} ({score_pct}%) | Tests: {selected_count} Recommended"

        summary_lines = [
            f"### 🛡️ CodeImpact Predictive Risk Assessment: **{tier}** ({score_pct}%)",
            "",
            f"**Model:** `{model_name}` v`{model_ver}` | "
            f"**Confidence Interval:** `[{ci_lower:.2f}, {ci_upper:.2f}]` | "
            f"**Suite Time Savings:** **{time_savings:.1f}%**",
            "",
        ]

        if raw_factors:
            summary_lines.append("**Top Contributing Risk Factors:**")
            for f in raw_factors[:3]:
                fname = getattr(
                    f, "feature_name", f.get("feature_name", "") if isinstance(f, dict) else str(f)
                )
                expl = getattr(
                    f,
                    "human_explanation",
                    f.get("human_explanation", "") if isinstance(f, dict) else "",
                )
                summary_lines.append(f"- **{fname.replace('_', ' ').capitalize()}**: {expl}")
            summary_lines.append("")

        test_identifiers = []
        for t in recs:
            tid = getattr(
                t,
                "test_identifier",
                t.get("test_identifier", "") if isinstance(t, dict) else str(t),
            )
            if tid:
                test_identifiers.append(tid)

        test_commands = " ".join(test_identifiers)
        text_lines = [
            "### ⚡ Intelligent Test Selection",
            f"CodeImpact recommends executing **{selected_count}** of **{total_count}** tests "
            f"saving **{time_savings:.1f}%** test execution time under budget.",
            "",
            "#### Quick Pytest Execution Command",
            "```bash",
            f"pytest {test_commands if test_commands else 'tests/'}",
            "```",
            "",
            "| Rank | Test Identifier | Evidence Level | Est. Duration |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for t in recs[:10]:
            rank = getattr(t, "rank", t.get("rank", 1) if isinstance(t, dict) else 1)
            tid = getattr(
                t,
                "test_identifier",
                t.get("test_identifier", "") if isinstance(t, dict) else str(t),
            )
            ev = getattr(
                t, "evidence_level", t.get("evidence_level", "") if isinstance(t, dict) else ""
            ).replace("EVIDENCE_", "")
            dur = getattr(
                t,
                "estimated_duration_ms",
                t.get("estimated_duration_ms", 100) if isinstance(t, dict) else 100,
            )
            text_lines.append(f"| #{rank} | `{tid}` | `{ev}` | {dur}ms |")

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
