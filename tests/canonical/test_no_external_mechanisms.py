import ast
from pathlib import Path


def test_no_external_mechanisms_in_src_canonical():
    """
    Verifies that src_canonical strictly contains ONLY paper-mentioned algorithms.
    Prohibited unmentioned mechanisms from the Keith codebase:
    - active_route_elimination
    - ejection_chain / ejection
    - two_opt_star / 2-opt*
    - granular_neighborhood / granular
    """
    src_dir = Path("src_canonical")
    prohibited_keywords = [
        "active_route_elimination",
        "route_elimination",
        "ejection_chain",
        "ejection",
        "two_opt_star",
        "2-opt*",
        "granular_neighborhood",
        "granular",
    ]

    for py_file in src_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for kw in prohibited_keywords:
            assert kw not in content, f"Prohibited unmentioned mechanism '{kw}' found in {py_file}!"
