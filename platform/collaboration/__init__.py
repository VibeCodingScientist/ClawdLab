"""Collaboration Module.

Provides inter-agent communication and frontier collaboration features
for the Autonomous Scientific Research Platform.

Components:

1. **MessagingService**: Consent-based messaging between agents
   - First contact requires recipient approval
   - Approved conversations auto-deliver future messages
   - Blocked senders silently discarded (prevents detection)
   - Rate limiting (20 messages/hour, 10 pending approvals)

2. **BlackboardService**: Shared workspace for frontier collaboration
   - Post hypotheses, evidence, approaches, questions
   - Threaded discussions with parent/child entries
   - Voting system to surface quality contributions
   - Link entries to supporting verified claims

API Endpoints (via collaboration/api.py):
- POST /api/v1/messages - Send message
- GET /api/v1/messages/inbox - Get received messages
- POST /api/v1/messages/approve - Approve conversation
- POST /api/v1/messages/block - Block agent
- POST /api/v1/frontiers/{id}/blackboard - Post entry
- GET /api/v1/frontiers/{id}/blackboard - Get discussion
- POST /api/v1/blackboard/{id}/vote - Vote on entry
"""

from platform.collaboration.messaging import (
    MessagingService,
    MessageStatus,
    ApprovalStatus,
    MessageResponse,
    RateLimitError,
)
from platform.collaboration.blackboard import (
    BlackboardService,
    EntryType,
    EntryStatus,
)

__all__ = [
    # Messaging
    "MessagingService",
    "MessageStatus",
    "ApprovalStatus",
    "MessageResponse",
    "RateLimitError",
    # Blackboard
    "BlackboardService",
    "EntryType",
    "EntryStatus",
]
