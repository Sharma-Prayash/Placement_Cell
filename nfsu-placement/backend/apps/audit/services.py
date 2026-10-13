import hashlib
import json

from django.db import connection, transaction
from django.utils import timezone

from .models import AuditLog

GENESIS = "0" * 64
_LOCK_ID = 703126  # Postgres advisory lock key that serialises chain appends


def _digest(prev_hash, ts, actor_label, role, action, entity, entity_id, before, after, ip):
    payload = json.dumps(
        [prev_hash, ts.isoformat(), actor_label, role, action, entity, str(entity_id), before, after, ip],
        sort_keys=True, default=str, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def log(actor, action, entity="", entity_id="", before=None, after=None, request=None, label=None):
    """Append one audit row. Call inside the same transaction as the change it describes."""
    from core.ratelimit import client_ip

    ip = client_ip(request) if request is not None else ""
    actor_obj = actor if getattr(actor, "pk", None) else None
    actor_label = actor.username if actor_obj else (label or ("public" if request is not None else "system"))
    role = getattr(actor_obj, "role", "") if actor_obj else actor_label
    before = json.loads(json.dumps(before, default=str)) if before is not None else None
    after = json.loads(json.dumps(after, default=str)) if after is not None else None

    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK_ID])
        last = AuditLog.objects.order_by("-id").values_list("hash", flat=True).first()
        prev_hash = last or GENESIS
        ts = timezone.now()
        h = _digest(prev_hash, ts, actor_label, role, action, entity, entity_id, before, after, ip)
        return AuditLog.objects.create(
            ts=ts, actor=actor_obj, actor_label=actor_label, role=role, action=action, entity=entity,
            entity_id=str(entity_id), before=before, after=after, ip=ip, prev_hash=prev_hash, hash=h,
        )


def verify_chain():
    """Return (ok, first_bad_id, checked_count)."""
    prev = GENESIS
    count = 0
    for row in AuditLog.objects.order_by("id").iterator():
        expected = _digest(prev, row.ts, row.actor_label, row.role, row.action, row.entity, row.entity_id,
                           row.before, row.after, row.ip)
        if row.prev_hash != prev or row.hash != expected:
            return False, row.id, count
        prev = row.hash
        count += 1
    return True, None, count
