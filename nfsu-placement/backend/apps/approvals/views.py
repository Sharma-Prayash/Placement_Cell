from django.db.models import Q
from django.http import Http404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import ADMIN, COORDINATOR, IsApprover, IsStaff

from . import services
from .models import ChangeRequest


class ChangeRequestSerializer(serializers.ModelSerializer):
    proposer = serializers.CharField(source="proposer.username")
    approver = serializers.CharField(source="approver.username", default=None)

    class Meta:
        model = ChangeRequest
        fields = ["id", "entity", "action", "entity_id", "course", "before", "proposed", "reason", "proposer", "approver",
                  "status", "decision_note", "policy_preview", "created_at", "expires_at", "decided_at"]


class ChangeRequestListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        u = request.user
        qs = ChangeRequest.objects.select_related("proposer", "approver")
        if u.role == COORDINATOR:
            qs = qs.filter(Q(course=u.coordinator_course) | Q(proposer=u))
        elif u.role != ADMIN:
            qs = qs.filter(proposer=u)
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        page = list(qs[:200])
        data = ChangeRequestSerializer(page, many=True).data
        for row, cr in zip(data, page):
            row["proposed"] = services.redact(row["proposed"])
            row["can_approve"] = cr.status == "pending" and services.can_approve(u, cr)
        return Response(data)

    def post(self, request):
        d = request.data
        cr = services.propose(request.user, str(d.get("entity", "")), str(d.get("action", "")), d.get("entity_id"),
                              d.get("data") or {}, str(d.get("reason", "")), request=request)
        out = ChangeRequestSerializer(cr).data
        out["proposed"] = services.redact(out["proposed"])
        return Response(out, status=201)


class ChangeRequestDecisionView(APIView):
    permission_classes = [IsApprover]

    def post(self, request, pk, decision):
        cr = ChangeRequest.objects.filter(pk=pk).first()
        if not cr:
            raise Http404
        note = str(request.data.get("note", ""))
        if decision == "approve":
            cr = services.approve(request.user, cr, note, request=request)
        elif decision == "reject":
            cr = services.reject(request.user, cr, note, request=request)
        else:
            raise Http404
        out = ChangeRequestSerializer(cr).data
        out["proposed"] = services.redact(out["proposed"])
        return Response(out)
