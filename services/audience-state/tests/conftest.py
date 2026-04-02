"""
Shared test helpers for the audience-state test suite.
"""
import json


def make_observation(
    count: int = 1,
    confidence: float = 0.9,
    pipeline_degraded: bool = False,
    frame_seq: int = 1,
    message_id: str = "obs-1",
    window_ms: int = 500,
    demographics: dict | None = None,
    attention: dict | None = None,
) -> dict:
    """Build a minimal valid ICD-2 cv-observation dict."""
    obs: dict = {
        "schema_version": "1.0.0",
        "message_type": "cv_observation",
        "message_id": message_id,
        "produced_at": "2026-01-01T00:00:00Z",
        "tenant_id": "tenant-01",
        "site_id": "site-01",
        "camera_id": "cam-01",
        "pipeline_id": "pipeline-01",
        "frame_seq": frame_seq,
        "window_ms": window_ms,
        "counts": {"present": count, "confidence": confidence},
        "quality": {
            "frames_processed": 30,
            "frames_dropped": 0,
            "pipeline_degraded": pipeline_degraded,
        },
        "privacy": {
            "contains_images": False,
            "contains_frame_urls": False,
            "contains_face_embeddings": False,
        },
    }
    if demographics is not None:
        obs["demographics"] = demographics
    if attention is not None:
        obs["attention"] = attention
    return obs


def raw(obs: dict) -> bytes:
    return json.dumps(obs).encode()
