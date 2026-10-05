import uuid
from typing import Any


def build_ice_payload(
    *,
    call_id: uuid.UUID,
    from_user_id: uuid.UUID,
    candidate: str,
    sdp_mid: str | None = None,
    sdp_mline_index: int | None = None,
) -> dict[str, Any]:
    """Payload для события call:ice — один ICE-кандидат."""
    return {
        "call_id": str(call_id),
        "from_user_id": str(from_user_id),
        "candidate": candidate,
        "sdpMid": sdp_mid,
        "sdpMLineIndex": sdp_mline_index,
    }