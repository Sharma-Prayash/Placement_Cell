from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ADMIN, IsAdminOrOfficer

from .models import AuditLog
from .services import verify_chain

OFFICER_HIDDEN_PREFIXES = ("auth.",)


class AuditLogView(APIView):
    """Admins see everything; officers see record changes but not authentication events."""

    permission_classes = [IsAdminOrOfficer]

    def get(self, request):
        qs = AuditLog.objects.all()
        p = request.query_params
        if p.get("entity"):
            qs = qs.filter(entity=p["entity"])
        if p.get("action"):
            qs = qs.filter(action__startswith=p["action"][:40])
        if request.user.role != ADMIN:
            for prefix in OFFICER_HIDDEN_PREFIXES:
                qs = qs.exclude(action__startswith=prefix)
        rows = qs.values("id", "ts", "actor_label", "role", "action", "entity", "entity_id", "before", "after", "ip", "hash")[:300]
        return Response(list(rows))


class AuditVerifyView(APIView):
    permission_classes = [IsAdminOrOfficer]

    def get(self, request):
        ok, bad_id, count = verify_chain()
        return Response({"intact": ok, "first_broken_id": bad_id, "verified_records": count})
