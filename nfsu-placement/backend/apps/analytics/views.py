from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from core.permissions import COORDINATOR, IsStaff

from .services import internal_report, public_report


class PublicStatsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(public_report())


class StaffReportView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        course = request.query_params.get("course")
        if request.user.role == COORDINATOR:
            course = request.user.coordinator_course
        audit.log(request.user, "report.viewed", "report", course or "university", request=request)
        return Response(internal_report(course=course, batch=request.query_params.get("batch")))
