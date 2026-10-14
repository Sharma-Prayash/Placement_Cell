from django.urls import path

from apps.accounts import views as acc
from apps.analytics import views as ana
from apps.approvals import views as appr
from apps.assistant import views as ast
from apps.audit import views as aud
from apps.bulletin import views as bul
from apps.placements import views as pl
from apps.policy import views as pol
from apps.recruiters import views as rec
from apps.students import views as stu

urlpatterns = [
    # auth
    path("api/auth/csrf", acc.CsrfView.as_view()),
    path("api/auth/login", acc.LoginView.as_view()),
    path("api/auth/login/verify", acc.LoginVerifyView.as_view()),
    path("api/auth/login/resend", acc.LoginResendView.as_view()),
    path("api/auth/logout", acc.LogoutView.as_view()),
    path("api/auth/me", acc.MeView.as_view()),
    path("api/auth/activate", acc.ActivateView.as_view()),
    path("api/auth/mfa/setup", acc.MfaSetupView.as_view()),
    path("api/auth/mfa/confirm", acc.MfaConfirmView.as_view()),
    # public (no login)
    path("api/public/stats", ana.PublicStatsView.as_view()),
    path("api/public/bulletin", bul.PublicBulletinView.as_view()),
    path("api/public/recruit", rec.RecruiterInterestView.as_view()),
    path("api/public/assistant", ast.PublicAssistantView.as_view()),
    # common bulletin and the assistant (any signed-in member)
    path("api/bulletin", bul.BulletinView.as_view()),
    path("api/bulletin/<int:pk>/join", bul.JoinEventView.as_view()),
    path("api/assistant", ast.AssistantView.as_view()),
    # student
    path("api/student/me", stu.StudentMeView.as_view()),
    path("api/student/resume", stu.ResumeUploadView.as_view()),
    path("api/student/drives", pl.StudentDrivesView.as_view()),
    path("api/student/drives/<int:drive_id>/apply", pl.StudentApplyView.as_view()),
    path("api/student/offers", pl.StudentOffersView.as_view()),
    path("api/student/offers/<int:offer_id>/respond", pl.StudentRespondView.as_view()),
    # recruiter
    path("api/recruiter/drives", pl.RecruiterDrivesView.as_view()),
    path("api/recruiter/drives/<int:drive_id>/candidates", pl.RecruiterCandidatesView.as_view()),
    path("api/recruiter/talent", pl.RecruiterTalentPoolView.as_view()),
    path("api/recruiter/applications/<int:app_id>", pl.RecruiterApplicationView.as_view()),
    path("api/resumes/<str:placement_id>", stu.ResumeDownloadView.as_view()),
    # staff (Placement Cell)
    path("api/staff/students", stu.StaffStudentListView.as_view()),
    path("api/staff/students/<int:pk>", stu.StaffStudentDetailView.as_view()),
    path("api/staff/export", stu.StaffExportView.as_view()),
    path("api/staff/drives", pl.StaffDrivesView.as_view()),
    path("api/staff/offers", pl.StaffOffersView.as_view()),
    path("api/staff/evaluate", pl.StaffEvaluateView.as_view()),
    path("api/staff/changes", appr.ChangeRequestListView.as_view()),
    path("api/staff/changes/<int:pk>/<str:decision>", appr.ChangeRequestDecisionView.as_view()),
    path("api/staff/recruiters", rec.RecruiterListView.as_view()),
    path("api/staff/recruiters/<int:pk>/resend-activation", rec.RecruiterResendActivationView.as_view()),
    path("api/staff/recruiter-requests", rec.RecruiterRequestListView.as_view()),
    path("api/staff/recruiter-requests/<int:pk>/<str:decision>", rec.RecruiterRequestDecisionView.as_view()),
    path("api/staff/bulletin/pending", bul.BulletinModerationView.as_view()),
    path("api/staff/bulletin/<int:pk>/<str:decision>", bul.BulletinModerationView.as_view()),
    path("api/staff/bulletin/<int:pk>/attendance", bul.AttendanceListView.as_view()),
    path("api/staff/reports", ana.StaffReportView.as_view()),
    path("api/staff/assistant", ast.StaffAssistantView.as_view()),
    path("api/staff/policy", pol.PolicyConfigView.as_view()),
    path("api/staff/flags", pol.PolicyFlagListView.as_view()),
    path("api/staff/audit", aud.AuditLogView.as_view()),
    path("api/staff/audit/verify", aud.AuditVerifyView.as_view()),
]
