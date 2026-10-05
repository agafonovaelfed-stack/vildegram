import uuid
from typing import Any


def build_answer_payload(
    *,
    call_id: uuid.UUID,
    from_user_id: uuid.UUID,
    sdp: str,
    sdp_type: str = "answer",
) -> dict[str, Any]:
    """Payload для события call:answer.

    sdp — SDP-строка от RTCPeerConnection.createAnswer().
    """
    return {
        "call_id": str(call_id),
        "from_user_id": str(from_user_id),
        "type": sdp_type,
        "sdp": sdp,
    }