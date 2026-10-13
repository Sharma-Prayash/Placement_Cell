from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from core.permissions import COORDINATOR, IsAdmin, IsStaff

from .models import PolicyConfig, PolicyFlag


class PolicyConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyConfig
        exclude = ["id"]


class PolicyConfigView(APIView):
    def get_permissions(self):
        return [IsStaff()] if self.request.method == "GET" else [IsAdmin()]

    def get(self, request):
        return Response(PolicyConfigSerializer(PolicyConfig.current()).data)

    def put(self, request):
        cfg = PolicyConfig.current()
        before = PolicyConfigSerializer(cfg).data
        s = PolicyConfigSerializer(cfg, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        audit.log(request.user, "policy.config_changed", "policy_config", 1, before=before, after=s.data, request=request)
        return Response(s.data)


class PolicyFlagListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = PolicyFlag.objects.select_related("student")
        if request.user.role == COORDINATOR:
            qs = qs.filter(student__course=request.user.coordinator_course)
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response([{"id": f.pk, "placement_id": f.student.placement_id, "name": f.student.name, "course": f.student.course,
                          "rule_code": f.rule_code, "explanation": f.explanation, "drives_remaining": f.drives_remaining,
                          "status": f.status, "created_at": f.created_at} for f in qs[:300]])
