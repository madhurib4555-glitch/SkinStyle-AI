"""In-memory store for uploaded selfies.

Selfies are biometric data, so they are deliberately never written to disk: the
try-on step needs the original bytes again after /analyze, and an in-process
dict with a TTL keeps that window as small as possible while avoiding a second
upload from the client.

The trade-off is that this is single-process only. Running more than one worker
means a try-on request can land on a process that lacks the image; for a
multi-instance deployment, back this with Redis (same interface, `put`/`get`).
"""

import secrets
import time
from collections import OrderedDict

from app.config import settings


class ImageStore:
    def __init__(self) -> None:
        # Ordered so the oldest entry is cheap to evict when at capacity.
        self._items: OrderedDict[str, tuple[float, bytes]] = OrderedDict()

    def put(self, image_bytes: bytes) -> str:
        self._evict_expired()

        # Bound memory even if traffic outpaces expiry.
        while len(self._items) >= settings.max_cached_uploads:
            self._items.popitem(last=False)

        image_id = secrets.token_urlsafe(16)
        self._items[image_id] = (time.monotonic(), image_bytes)
        return image_id

    def get(self, image_id: str) -> bytes | None:
        self._evict_expired()
        entry = self._items.get(image_id)
        return entry[1] if entry else None

    def _evict_expired(self) -> None:
        cutoff = time.monotonic() - settings.upload_ttl_seconds
        # Entries are insertion-ordered, so stop at the first live one.
        while self._items:
            image_id, (created, _) = next(iter(self._items.items()))
            if created >= cutoff:
                break
            del self._items[image_id]


store = ImageStore()
