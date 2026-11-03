from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter(tags=["Metrics"])

# Prometheus Metrics Definitions
ANALYSIS_TOTAL = Counter(
    "codeimpact_analyses_total", "Total number of pull request analyses conducted", ["status"]
)
ANALYSIS_DURATION_SECONDS = Histogram(
    "codeimpact_analysis_duration_seconds",
    "Distribution of analysis runtimes in seconds",
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)
PREDICTED_RISK_GAUGE = Gauge(
    "codeimpact_latest_risk_score", "Latest predicted change risk score [0-1]"
)
TESTS_RECOMMENDED_COUNT = Histogram(
    "codeimpact_tests_recommended_count",
    "Number of tests selected per PR",
    buckets=[1, 5, 10, 25, 50, 100, 250],
)


@router.get("/metrics", summary="Prometheus Metrics Scrape Target")
def get_metrics() -> Response:
    """
    Expose Prometheus-formatted operational metrics for observability.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
