import json
from pathlib import Path

from fastapi import APIRouter

from ..core.config import API_PUBLIC_BASE
from ..core.logging import get_logger
from ..logs.db import insert_event_log

logger = get_logger(__name__)
router = APIRouter(tags=["TMS Companion"])

RELEASES_DIR = Path(__file__).resolve().parents[2] / "releases" / "companion"
UPDATE_JSON = RELEASES_DIR / "update.json"


def resolve_apk_url(apk_url: str, api_public_base: str) -> str:
    """Path in update.json; full URL returned to the phone. Absolute URLs pass through."""
    raw = apk_url.strip()
    if not raw or "://" in raw:
        return raw
    return f"{api_public_base.rstrip('/')}/{raw.lstrip('/')}"


def _with_public_apk_url(data: dict) -> dict:
    data["apk_url"] = resolve_apk_url(str(data.get("apk_url") or ""), API_PUBLIC_BASE)
    return data


def _fallback_manifest() -> dict:
    return {
        "version_code": 1,
        "version_name": "1.0",
        "apk_url": "",
        "changelog": "",
    }


@router.get("/app/update.json")
def app_update():
    # Two distinct failure modes get distinct event types, since they imply
    # different fixes: "missing" means nobody has published a release yet
    # (expected on a fresh install); "unreadable" means update.json exists
    # but is malformed JSON (a real bug in the last publish step).
    if not UPDATE_JSON.is_file():
        logger.warning("companion manifest missing path=%s", UPDATE_JSON)
        insert_event_log(
            "companion.manifest_missing",
            "companion",
            "TMS Companion update manifest missing; serving fallback",
            severity="warning",
        )
        return _with_public_apk_url(_fallback_manifest())
    try:
        data = json.loads(UPDATE_JSON.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("companion manifest unreadable path=%s", UPDATE_JSON)
        insert_event_log(
            "companion.manifest_unreadable",
            "companion",
            "TMS Companion update manifest unreadable; serving fallback",
            severity="error",
        )
        return _with_public_apk_url(_fallback_manifest())
    logger.debug(
        "companion manifest served version_code=%s version_name=%s",
        data.get("version_code"),
        data.get("version_name"),
    )
    return _with_public_apk_url(data)
