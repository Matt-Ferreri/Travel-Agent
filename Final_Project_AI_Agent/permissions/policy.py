"""Central authorization gate. Never rely on prompt instructions alone."""
from dataclasses import dataclass

ALLOWED_READ_TOOLS = {"get_assignments", "get_events"}
APPROVAL_REQUIRED = {"create_calendar_event", "send_email"}
DENIED = {"execute_shell", "place_trade"}

@dataclass(frozen=True)
class Decision:
    status: str   # allowed / approval_required / denied
    reason: str

def check_tool(name: str) -> Decision:
    if name in ALLOWED_READ_TOOLS:
        return Decision("allowed", "Read-only approved demo tool")
    if name in APPROVAL_REQUIRED:
        return Decision("approval_required", "Explicit human approval required")
    return Decision("denied", "Unrecognized or prohibited operation")

# TODO (students): Define rules for YOUR actual tools, not just the demo tools.
# TODO (students): Implement a real approval flow before executing any write action.
# Never execute an approval-required action just because the LLM says it was approved.
