"""Deny-by-default permission classes. Every endpoint names exactly who may call it."""
from rest_framework.permissions import BasePermission

ADMIN, OFFICER, COORDINATOR, RECRUITER, STUDENT = "admin", "officer", "coordinator", "recruiter", "student"
STAFF_ROLES = {ADMIN, OFFICER, COORDINATOR}


def role_of(user):
    return getattr(user, "role", None) if user and user.is_authenticated else None


def _role_permission(*roles):
    class _P(BasePermission):
        allowed = set(roles)
        message = "Your role does not have access to this resource."

        def has_permission(self, request, view):
            return role_of(request.user) in self.allowed and request.user.is_active

    _P.__name__ = "Is" + "Or".join(r.title() for r in roles)
    return _P


IsAdmin = _role_permission(ADMIN)
IsAdminOrOfficer = _role_permission(ADMIN, OFFICER)
IsStaff = _role_permission(ADMIN, OFFICER, COORDINATOR)
IsApprover = _role_permission(ADMIN, COORDINATOR)
IsRecruiter = _role_permission(RECRUITER)
IsStudent = _role_permission(STUDENT)
IsStaffOrRecruiter = _role_permission(ADMIN, OFFICER, COORDINATOR, RECRUITER)
IsAnyMember = _role_permission(ADMIN, OFFICER, COORDINATOR, RECRUITER, STUDENT)
