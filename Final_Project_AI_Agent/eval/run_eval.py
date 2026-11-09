"""Tiny runnable evaluation baseline. Students should replace it with real test scenarios."""
from agent import run_agent

def evaluate():
    cases=[("What assignments are due?", "get_assignments"), ("What is on my calendar?", "get_events"), ("Plan my week", "get_assignments")]
    hits=0
    for query, expected_tool in cases:
        result=run_agent(query)
        ok=any(t["tool"]==expected_tool for t in result["trace"])
        hits += ok
        print(f"{'PASS' if ok else 'FAIL'} {query} | tools: {[t['tool'] for t in result['trace']]}")
    print(f"Demo tool selection: {hits}/{len(cases)} cases")
    return hits==len(cases)

if __name__=="__main__":
    raise SystemExit(0 if evaluate() else 1)

# TODO (students): Create 15-25 application-specific scenarios including failure cases.
# TODO (students): Compare baseline vs modified agent with quantitative metrics.
