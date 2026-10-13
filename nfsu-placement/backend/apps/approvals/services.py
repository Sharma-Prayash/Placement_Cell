"""Maker-checker service. Views never write placement records directly: they call
propose(), and a *different* authorised person calls approve().

Each entity/action pair has a handler that (1) validates the proposal and captures
the "before" snapshot, and (2) applies it inside one transaction with the audit entry.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit
from core.permissions import ADMIN, COORDINATOR, OFFICER

from .models import ChangeRequest

COURSE_SCOPED = {"student", "offer", "attendance", "flag"}
SENSITIVE_FIELDS = {"mobile"}  # encrypted at rest; never stored or logged in plaintext


def seal(data):
    """Encrypt sensitive values inside a proposal so the change_requests table holds ciphertext."""
    from core.fields import _fernet
    out = dict(data or {})
    for k in SENSITIVE_FIELDS & out.keys():
        if out[k]:
            out[k] = {"sealed": _fernet().encrypt(str(out[k]).encode()).decode()}
    return out


def unseal(data):
    from core.fields import _fernet
    out = dict(data or {})
    for k, v in out.items():
        if isinstance(v, dict) and "sealed" in v:
            out[k] = _fernet().decrypt(v["sealed"].encode()).decode()
    return out


def redact(data):
    """What humans and the audit log see for sensitive values."""
    if data is None:
        return None
    out = dict(data)
    for k in SENSITIVE_FIELDS & out.keys():
        v = out[k]
        plain = v if isinstance(v, str) else None
        out[k] = f"(changed, ends …{plain[-2:]})" if plain else "(encrypted value)"
    return out


def _jsonable(data):
    out = {}
    for k, v in data.items():
        out[k] = v.pk if hasattr(v, "pk") else (str(v) if v is not None and not isinstance(v, (int, bool, str, list, dict)) else v)
    return out


# ---------------------------------------------------------------- handlers
def _student_handler():
    from apps.students.models import Student
    from apps.students.serializers import STAFF_EDITABLE, StaffStudentWriteSerializer

    def prepare(action, entity_id, data):
        if action == "create":
            s = StaffStudentWriteSerializer(data=data)
            s.is_valid(raise_exception=True)
            return None, _jsonable(s.validated_data), s.validated_data["course"], None
        student = Student.objects.get(pk=entity_id)
        if action == "archive":
            return {"archived": False}, {"archived": True}, student.course, None
        s = StaffStudentWriteSerializer(student, data=data, partial=True)
        s.is_valid(raise_exception=True)
        before = {f: getattr(student, f) for f in s.validated_data if f in STAFF_EDITABLE}
        return redact(_jsonable(before)), _jsonable(s.validated_data), student.course, None

    def apply(cr, actor):
        from apps.accounts.models import Role, User
        if cr.action == "create":
            s = StaffStudentWriteSerializer(data=unseal(cr.proposed))
            s.is_valid(raise_exception=True)
            student = s.save()
            user = User.objects.create(username=student.placement_id, email=student.email, role=Role.STUDENT,
                                       first_name=student.name[:150])
            user.set_unusable_password()
            user.save()
            student.user = user
            student.save(update_fields=["user"])
            return student.pk
        student = Student.objects.get(pk=cr.entity_id)
        if cr.action == "archive":
            student.archived_at = timezone.now()
            student.save(update_fields=["archived_at"])
            if student.user:
                student.user.is_active = False
                student.user.save(update_fields=["is_active"])
            return student.pk
        s = StaffStudentWriteSerializer(student, data=unseal(cr.proposed), partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return student.pk

    return prepare, apply


def _offer_handler():
    from apps.placements.models import Offer, OfferStatusEvent
    from apps.placements.serializers import OfferUpdateSerializer, OfferWriteSerializer, acceptance_deadline
    from apps.policy.engine import BLOCK, DriveFacts
    from apps.policy.services import evaluate_for, flag_facts, load_config, offer_facts, student_facts
    from apps.policy.engine import evaluate

    def policy_check(validated, exclude=None):
        student = validated["student"]
        drive = validated.get("drive")
        facts = DriveFacts(validated["company"].id, validated["offer_type"], validated.get("ctc_lpa"),
                           tuple(drive.eligible_courses) if drive else (student.course,),
                           drive.min_cgpa if drive else 0, drive.max_backlogs if drive else 99)
        return evaluate(student_facts(student), facts, offer_facts(student, exclude), flag_facts(student), load_config())

    def prepare(action, entity_id, data):
        if action == "create":
            s = OfferWriteSerializer(data=data)
            s.is_valid(raise_exception=True)
            verdict = policy_check(s.validated_data)
            if verdict.decision == BLOCK:
                raise ValidationError({"policy": verdict.to_dict()})
            return None, _jsonable(s.validated_data), s.validated_data["student"].course, verdict.to_dict()
        offer = Offer.objects.select_related("student").get(pk=entity_id)
        s = OfferUpdateSerializer(data=data)
        s.is_valid(raise_exception=True)
        before = {k: getattr(offer, k) for k in s.validated_data}
        return before, dict(s.validated_data), offer.student.course, None

    def apply(cr, actor):
        if cr.action == "create":
            s = OfferWriteSerializer(data=cr.proposed)
            s.is_valid(raise_exception=True)
            verdict = policy_check(s.validated_data)  # re-check at apply time: state may have changed
            if verdict.decision == BLOCK:
                raise ValidationError({"policy": verdict.to_dict()})
            v = s.validated_data
            offer = Offer.objects.create(**v, acceptance_deadline=acceptance_deadline(v["offer_date"], v.get("drive")))
            return offer.pk
        offer = Offer.objects.get(pk=cr.entity_id)
        for field, new in cr.proposed.items():
            old = getattr(offer, field)
            if old != new:
                OfferStatusEvent.objects.create(offer=offer, field=field, old_value=old, new_value=new, actor_label=actor.username)
                setattr(offer, field, new)
        offer.save()
        return offer.pk

    return prepare, apply


def _attendance_handler():
    from apps.bulletin.models import Attendance
    from apps.policy.models import PolicyFlag

    def prepare(action, entity_id, data):
        att = Attendance.objects.select_related("student").get(pk=entity_id)
        reason = (data.get("excuse_reason") or "").strip()
        if not reason:
            raise ValidationError({"excuse_reason": "Give the reason for the excused absence."})
        return {"status": att.status}, {"status": "excused", "excuse_reason": reason[:300]}, att.student.course, None

    def apply(cr, actor):
        att = Attendance.objects.get(pk=cr.entity_id)
        att.status = Attendance.Status.EXCUSED
        att.excuse_reason = cr.proposed["excuse_reason"]
        att.save()
        PolicyFlag.objects.filter(source_ref=f"attendance:{att.pk}", status="open").update(status="waived", reviewed_by=actor)
        return att.pk

    return prepare, apply


def _flag_handler():
    from apps.policy.models import PolicyFlag

    def prepare(action, entity_id, data):
        flag = PolicyFlag.objects.select_related("student").get(pk=entity_id)
        return {"status": flag.status}, {"status": "waived"}, flag.student.course, None

    def apply(cr, actor):
        PolicyFlag.objects.filter(pk=cr.entity_id).update(status="waived", reviewed_by=actor)
        return cr.entity_id

    return prepare, apply


def _recruiter_handler():
    from apps.recruiters.serializers import AdminRecruiterSerializer
    from apps.recruiters.services import create_recruiter

    def prepare(action, entity_id, data):
        s = AdminRecruiterSerializer(data=data)
        s.is_valid(raise_exception=True)
        return None, dict(s.validated_data), "", None

    def apply(cr, actor):
        rec = create_recruiter(company_name=cr.proposed["company_name"], website=cr.proposed.get("website", ""),
                               contact_name=cr.proposed["contact_name"], email=cr.proposed["contact_email"], actor=actor)
        return rec.pk

    return prepare, apply


HANDLERS = {
    ("student", "create"): _student_handler, ("student", "update"): _student_handler, ("student", "archive"): _student_handler,
    ("offer", "create"): _offer_handler, ("offer", "update"): _offer_handler,
    ("attendance", "excuse"): _attendance_handler,
    ("flag", "waive"): _flag_handler,
    ("recruiter", "create"): _recruiter_handler,
}


# ---------------------------------------------------------------- public API
def can_propose(user, course):
    if user.role in (ADMIN, OFFICER):
        return True
    return user.role == COORDINATOR and course and course == user.coordinator_course


def can_approve(user, cr):
    if user.pk == cr.proposer_id:
        return False
    if user.role == ADMIN:
        return True
    return user.role == COORDINATOR and cr.entity in COURSE_SCOPED and cr.course == user.coordinator_course


def propose(user, entity, action, entity_id, data, reason, request=None):
    key = (entity, action)
    if key not in HANDLERS:
        raise ValidationError({"detail": f"Unknown change type {entity}/{action}."})
    if not reason or len(reason.strip()) < 5:
        raise ValidationError({"reason": "Explain the change in at least a few words; the approver sees this."})
    prepare, _ = HANDLERS[key]()
    before, proposed, course, preview = prepare(action, entity_id, data or {})
    if not can_propose(user, course):
        raise PermissionDenied("You can only propose changes for your own programme.")
    with transaction.atomic():
        cr = ChangeRequest.objects.create(
            entity=entity, action=action, entity_id=str(entity_id or ""), course=course or "", before=before,
            proposed=seal(proposed), reason=reason.strip()[:300], proposer=user, policy_preview=preview,
            expires_at=timezone.now() + timedelta(hours=settings.CHANGE_REQUEST_TTL_HOURS),
        )
        audit.log(user, "change.proposed", entity, entity_id or "", before=before, after=redact(proposed), request=request)
    return cr


def approve(user, cr, note="", request=None):
    with transaction.atomic():
        cr = ChangeRequest.objects.select_for_update().get(pk=cr.pk)
        _check_decidable(user, cr)
        _, apply = HANDLERS[(cr.entity, cr.action)]()
        new_id = apply(cr, user)
        cr.status, cr.approver, cr.decided_at, cr.decision_note = ChangeRequest.Status.APPROVED, user, timezone.now(), note[:300]
        if not cr.entity_id:
            cr.entity_id = str(new_id)
        cr.save()
        audit.log(user, "change.approved", cr.entity, cr.entity_id, before=cr.before, after=redact(cr.proposed), request=request)
    return cr


def reject(user, cr, note, request=None):
    if not note or len(note.strip()) < 3:
        raise ValidationError({"note": "Say why the change is rejected."})
    with transaction.atomic():
        cr = ChangeRequest.objects.select_for_update().get(pk=cr.pk)
        _check_decidable(user, cr)
        cr.status, cr.approver, cr.decided_at, cr.decision_note = ChangeRequest.Status.REJECTED, user, timezone.now(), note[:300]
        cr.save()
        audit.log(user, "change.rejected", cr.entity, cr.entity_id, after={"note": note}, request=request)
    return cr


def _check_decidable(user, cr):
    if cr.status != ChangeRequest.Status.PENDING:
        raise ValidationError({"detail": f"This change is already {cr.status}."})
    if cr.expires_at < timezone.now():
        cr.status = ChangeRequest.Status.EXPIRED
        cr.save(update_fields=["status"])
        raise ValidationError({"detail": "This change expired before anyone approved it. Propose it again."})
    if user.pk == cr.proposer_id:
        raise PermissionDenied("You proposed this change, so someone else has to approve it.")
    if not can_approve(user, cr):
        raise PermissionDenied("Your role cannot approve this change.")
