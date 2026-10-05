import uuid
from typing import Any


def build_offer_payload(
    *,
    call_id: uuid.UUID,
    from_user_id: uuid.UUID,
    sdp: str,
    sdp_type: str = "offer",
) -> dict[str, Any]:
    """Формирует payload для события call:offer.

    sdp — SDP-строка от RTCPeerConnection.createOffer().
    """
    return {
        "call_id": str(call_id),
        "from_user_id": str(from_user_id),
        "type": sdp_type,
        "sdp": sdp,
    }