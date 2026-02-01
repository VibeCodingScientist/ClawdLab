"""Extended agent state enums — operational and research dimensions.

These replace the flat 6-state AgentStatus with two independent dimensions,
giving much richer visibility into what agents are doing.
"""

from enum import Enum


class AgentOperationalState(str, Enum):
    """Infrastructure-level: is the agent process running?"""

    PROVISIONING = "provisioning"
    ONLINE = "online"
    OFFLINE = "offline"
    CRASHED = "crashed"
    SUSPENDED = "suspended"


class AgentResearchState(str, Enum):
    """Research-level: what is the agent doing intellectually?"""

    IDLE = "idle"
    SCOUTING = "scouting"
    HYPOTHESIZING = "hypothesizing"
    EXPERIMENTING = "experimenting"
    ANALYZING = "analyzing"
    DEBATING = "debating"
    REVIEWING = "reviewing"
    WRITING = "writing"
    WAITING = "waiting"
    PARKED = "parked"


# Map research states to preferred workspace zones
RESEARCH_STATE_ZONES: dict[str, str] = {
    "idle": "ideation",
    "scouting": "library",
    "hypothesizing": "whiteboard",
    "experimenting": "bench",
    "analyzing": "bench",
    "debating": "roundtable",
    "reviewing": "library",
    "writing": "presentation",
    "waiting": "ideation",
    "parked": "ideation",
}
