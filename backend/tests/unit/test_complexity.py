from __future__ import annotations

from app.services.analysis.complexity import ComplexityAnalyzer


def test_complexity_analyzer_cyclomatic_and_nesting():
    code = """
def simple_function(x):
    return x * 2

def complex_function(a, b, c):
    if a > 0:
        if b > 0:
            while c > 0:
                c -= 1
                if c == 5:
                    break
        else:
            for i in range(10):
                if i % 2 == 0:
                    pass
    return a + b
"""
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_source(code, "test.py")

    assert len(metrics.functions) == 2
    funcs = {f.name: f for f in metrics.functions}

    assert funcs["simple_function"].cyclomatic_complexity == 1
    assert funcs["simple_function"].nesting_depth == 0

    assert funcs["complex_function"].cyclomatic_complexity >= 6
    assert funcs["complex_function"].nesting_depth >= 3
    assert funcs["complex_function"].parameter_count == 3


def test_complexity_delta_computation():
    base_code = """
def calculate(x):
    return x + 1
"""
    head_code = """
def calculate(x):
    if x > 100:
        return x * 2
    elif x > 50:
        return x * 3
    elif x > 10:
        return x * 4
    elif x > 5:
        return x * 5
    elif x > 2:
        return x * 6
    elif x > 1:
        return x * 7
    elif x > 0:
        return x * 8
    elif x == 0:
        return 0
    elif x < -10:
        return -1
    else:
        return -2
"""
    analyzer = ComplexityAnalyzer()
    report = analyzer.compute_delta(base_code, head_code, "calc.py", ["calculate"])

    assert report.delta_average_cc > 0
    assert report.head_max_cc >= 10
    assert report.modified_high_complexity_count == 1
