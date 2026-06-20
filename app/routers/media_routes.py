"""Image media: serve stored images and accept cropped uploads.

Upload pipeline (defense-in-depth — the client also crops to a square first):
  - reject anything over MAX_UPLOAD_MB
  - open with Pillow (rejects non-images)
  - honour EXIF orientation, center-crop to a perfect SQUARE, resize, re-encode
    as JPEG (also strips metadata)
  - store via app.storage (S3 on EC2, local folder in dev)

Images are served back through /media/{key} so the S3 bucket can stay private.
"""
import io
import secrets

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app import storage
from app.activity import log_activity
from app.auth import require_login
from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter()

_ALLOWED_KINDS = {"avatar", "dashboard"}


def _process_to_square_jpeg(data: bytes) -> bytes:
    """Center-crop to a square and re-encode as JPEG. Raises ValueError if bad."""
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("Not a valid image file.")

    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    size = settings.IMAGE_SIZE_PX
    img = img.resize((size, size), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()


@router.get("/media/{key:path}")
def serve_media(key: str):
    item = storage.load(key)
    if item is None:
        return Response(status_code=404)
    data, content_type = item
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/media/upload")
async def upload_image(
    request: Request,
    image: UploadFile = File(...),
    kind: str = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if kind not in _ALLOWED_KINDS:
        return JSONResponse({"ok": False, "error": "Invalid upload kind."}, status_code=400)

    data = await image.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        return JSONResponse(
            {"ok": False, "error": f"Image is too large (max {settings.MAX_UPLOAD_MB} MB)."},
            status_code=413,
        )
    if not data:
        return JSONResponse({"ok": False, "error": "Empty file."}, status_code=400)

    try:
        jpeg = _process_to_square_jpeg(data)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    token = secrets.token_hex(8)
    if kind == "avatar":
        key = f"avatars/{user.id}-{token}.jpg"
    else:
        key = f"dashboards/{token}.jpg"

    storage.save(key, jpeg, "image/jpeg")
    url = f"/media/{key}"

    if kind == "avatar":
        # Replace the previous avatar and clean it up.
        old = user.avatar_url
        user.avatar_url = url
        db.commit()
        if old and old.startswith("/media/"):
            storage.delete(old[len("/media/"):])
        log_activity(db, "change_avatar", user=user,
                     ip_address=request.client.host if request.client else "")

    return JSONResponse({"ok": True, "url": url})
