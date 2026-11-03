from __future__ import annotations

from app.services.analysis.ast_parser import PythonASTParser
from app.services.dependencies.graph_builder import DependencyGraphBuilder


def test_dependency_graph_builder_call_and_containment():
    parser = PythonASTParser()

    auth_code = """
def validate_token(tok: str) -> bool:
    return len(tok) > 10

def generate_token():
    return "tok_1234567890"
"""
    payment_code = """
from auth import validate_token

def process_payment(tok: str, amt: int) -> bool:
    if not validate_token(tok):
        return False
    return True
"""
    notify_code = """
from payment import process_payment

def send_receipt(tok: str):
    return process_payment(tok, 100)
"""
    m1 = parser.parse_source(auth_code, "app/auth.py")
    m2 = parser.parse_source(payment_code, "app/payment.py")
    m3 = parser.parse_source(notify_code, "app/notify.py")

    builder = DependencyGraphBuilder()
    # Mark validate_token as modified
    res = builder.build_graph([m1, m2, m3], modified_func_ids={"validate_token"})

    assert res.total_nodes > 0
    assert res.total_edges > 0
    assert res.modified_nodes_count >= 1

    # Verify that callers process_payment and send_receipt are identified as affected!
    callers = res.potentially_affected_callers
    caller_str = " ".join(callers)

    assert "process_payment" in caller_str
    assert "send_receipt" in caller_str

    # Serialized graph exists
    assert "nodes" in res.serialized_graph
    assert "edges" in res.serialized_graph
    assert len(res.serialized_graph["nodes"]) == res.total_nodes
