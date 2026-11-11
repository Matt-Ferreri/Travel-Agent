"""Central authorization gate. Never rely on prompt instructions alone."""
from dataclasses import dataclass

ALLOWED_READ_TOOLS = {"get_weather", "mcp_get_weather", "lookup_places"}
APPROVAL_REQUIRED = {
    "save_itinerary",
    "send_itinerary_email",
    "book_tickets",
    "create_calendar_event",
}
DENIED = {"execute_shell", "place_trade", "charge_card"}


@dataclass(frozen=True)
class Decision:
    status: str  # allowed / approval_required / denied
    reason: str


def check_tool(name: str) -> Decision:
    if name in ALLOWED_READ_TOOLS:
        return Decision("allowed", "Read-only approved travel tool")
    if name in APPROVAL_REQUIRED:
        return Decision("approval_required", "Explicit human approval required before side effects")
    if name in DENIED:
        return Decision("denied", "Prohibited operation")
    return Decision("denied", "Unrecognized or prohibited operation")

# TODO (Milestone 3+): Implement a real UI approval flow before executing write actions.
# Never execute an approval-required action just because the LLM says it was approved.
