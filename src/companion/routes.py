import json
from pathlib import Path

from fastapi import APIRouter

from ..core.logging import get_logger
from ..logs.db import insert_event_log

logger = get_logger(__name__)
router = APIRouter(tags=["TMS Companion"])

RELEASES_DIR = Path(__file__).resolve().parents[2] / "releases" / "companion"
UPDATE_JSON = RELEASES_DIR / "update.json"


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
        return _fallback_manifest()
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
        return _fallback_manifest()
    logger.info(
        "companion manifest served version_code=%s version_name=%s",
        data.get("version_code"),
        data.get("version_name"),
    )
    insert_event_log(
        "companion.manifest_served",
        "companion",
        f"TMS Companion manifest served v{data.get('version_name', '')}",
        context={
            "version_code": data.get("version_code"),
            "version_name": data.get("version_name"),
        },
    )
    return data
