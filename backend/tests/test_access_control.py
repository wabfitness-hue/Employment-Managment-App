"""
Access control tests — zones, profiles, auto-assignment logic,
time/day restrictions for contractors, individual zone overrides.
"""
import pytest
from datetime import time
from sqlalchemy.exc import IntegrityError

from app.models.access import (
    AccessZone, AccessProfile, AccessProfileZone,
    PersonAccess, PersonAccessZone, DayOfWeek, ZoneAccessType,
)
from app.models.id_prefix import IdPrefix, PersonType
from app.models.person import Person, PersonStatus
from app.models.company import Company


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def main_company(db):
    c = Company(name="Acme Corp", is_main_company=True)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def contractor_company(db):
    c = Company(name="BuildRight Ltd", is_main_company=False)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def dir_prefix(db):
    p = IdPrefix(prefix="DIR2", label="Director", applies_to=PersonType.employee, next_sequence=1)
    db.add(p)
    db.flush()
    return p


@pytest.fixture
def ctr_prefix(db):
    p = IdPrefix(prefix="CTR2", label="Contractor", applies_to=PersonType.contractor, next_sequence=1)
    db.add(p)
    db.flush()
    return p


@pytest.fixture
def entrance_zone(db):
    z = AccessZone(code="MAIN-ENT-T", name="Main Entrance", floor="G", sort_order=1)
    db.add(z)
    db.flush()
    return z


@pytest.fixture
def floor1_zone(db):
    z = AccessZone(code="FLOOR-1-T", name="Floor 1", floor="1", sort_order=2)
    db.add(z)
    db.flush()
    return z


@pytest.fixture
def boardroom_zone(db):
    z = AccessZone(code="BOARDROOM-T", name="Boardroom", floor="3", sort_order=7)
    db.add(z)
    db.flush()
    return z


@pytest.fixture
def director_profile(db, dir_prefix, entrance_zone, floor1_zone, boardroom_zone):
    profile = AccessProfile(
        name="Director Full Access Test",
        description="All areas",
        default_for_prefix_id=dir_prefix.id,
    )
    db.add(profile)
    db.flush()
    for zone in [entrance_zone, floor1_zone, boardroom_zone]:
        db.add(AccessProfileZone(profile_id=profile.id, zone_id=zone.id))
    db.flush()
    return profile


@pytest.fixture
def contractor_profile(db, ctr_prefix, entrance_zone, floor1_zone):
    profile = AccessProfile(
        name="Contractor Entry Only Test",
        description="Entry and floor 1 only",
        default_for_prefix_id=ctr_prefix.id,
    )
    db.add(profile)
    db.flush()
    for zone in [entrance_zone, floor1_zone]:
        db.add(AccessProfileZone(profile_id=profile.id, zone_id=zone.id))
    db.flush()
    return profile


@pytest.fixture
def director_person(db, main_company, dir_prefix):
    p = Person(
        person_type=PersonType.employee,
        employee_id="DIR2-0001",
        first_name="Jane", last_name="Director",
        email="jane.dir@acme.com",
        job_title="Director", department="Ops",
        company_id=main_company.id, prefix_id=dir_prefix.id,
    )
    db.add(p)
    db.flush()
    return p


@pytest.fixture
def contractor_person(db, contractor_company, ctr_prefix):
    p = Person(
        person_type=PersonType.contractor,
        employee_id="CTR2-0001",
        first_name="Bob", last_name="Builder",
        email="bob@buildright.com",
        job_title="Site Engineer", department="Build",
        company_id=contractor_company.id, prefix_id=ctr_prefix.id,
    )
    db.add(p)
    db.flush()
    return p


# ── AccessZone tests ──────────────────────────────────────────────────────────

class TestAccessZone:
    def test_create_zone(self, db, entrance_zone):
        assert entrance_zone.id is not None
        assert entrance_zone.code == "MAIN-ENT-T"
        assert entrance_zone.is_active is True

    def test_zone_code_unique(self, db, entrance_zone):
        duplicate = AccessZone(code="MAIN-ENT-T", name="Duplicate")
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_multiple_zones_created(self, db, entrance_zone, floor1_zone, boardroom_zone):
        zones = db.query(AccessZone).filter(
            AccessZone.code.in_(["MAIN-ENT-T", "FLOOR-1-T", "BOARDROOM-T"])
        ).all()
        assert len(zones) == 3


# ── AccessProfile tests ───────────────────────────────────────────────────────

class TestAccessProfile:
    def test_create_profile(self, db, director_profile, dir_prefix):
        assert director_profile.id is not None
        assert director_profile.default_for_prefix_id == dir_prefix.id

    def test_profile_has_zones(self, db, director_profile):
        assert len(director_profile.profile_zones) == 3

    def test_only_one_profile_per_prefix(self, db, dir_prefix, director_profile):
        duplicate = AccessProfile(
            name="Another Director Profile",
            default_for_prefix_id=dir_prefix.id,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_profile_without_prefix_link_allowed(self, db):
        profile = AccessProfile(name="Custom One-Off Profile")
        db.add(profile)
        db.flush()
        assert profile.default_for_prefix_id is None

    def test_contractor_profile_has_two_zones(self, db, contractor_profile):
        assert len(contractor_profile.profile_zones) == 2


# ── ProfileZone deduplication ─────────────────────────────────────────────────

class TestProfileZoneUniqueness:
    def test_duplicate_zone_in_profile_rejected(self, db, director_profile, entrance_zone):
        dup = AccessProfileZone(profile_id=director_profile.id, zone_id=entrance_zone.id)
        db.add(dup)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


# ── PersonAccess — employee (no restrictions) ─────────────────────────────────

class TestPersonAccessEmployee:
    def test_assign_director_profile(self, db, director_person, director_profile):
        access = PersonAccess(
            person_id=director_person.id,
            profile_id=director_profile.id,
            has_time_restriction=False,
        )
        db.add(access)
        db.flush()
        assert access.id is not None
        assert access.has_time_restriction is False
        assert access.allowed_days is None
        assert access.access_start is None
        assert access.access_end is None

    def test_one_access_record_per_person(self, db, director_person, director_profile):
        a1 = PersonAccess(person_id=director_person.id, profile_id=director_profile.id)
        db.add(a1)
        db.flush()
        a2 = PersonAccess(person_id=director_person.id, profile_id=director_profile.id)
        db.add(a2)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_employee_allowed_on_any_day(self, db, director_person, director_profile):
        access = PersonAccess(
            person_id=director_person.id,
            profile_id=director_profile.id,
            has_time_restriction=False,
        )
        db.add(access)
        db.flush()
        for day in DayOfWeek:
            assert access.is_allowed_on_day(day) is True


# ── PersonAccess — contractor (time + day restricted) ─────────────────────────

class TestPersonAccessContractor:
    def _make_contractor_access(self, db, contractor_person, contractor_profile):
        access = PersonAccess(
            person_id=contractor_person.id,
            profile_id=contractor_profile.id,
            has_time_restriction=True,
            access_start=time(8, 0),
            access_end=time(17, 30),
        )
        access.allowed_days_list = [
            DayOfWeek.monday.value,
            DayOfWeek.tuesday.value,
            DayOfWeek.wednesday.value,
            DayOfWeek.thursday.value,
            DayOfWeek.friday.value,
        ]
        db.add(access)
        db.flush()
        return access

    def test_contractor_has_time_restriction(self, db, contractor_person, contractor_profile):
        access = self._make_contractor_access(db, contractor_person, contractor_profile)
        assert access.has_time_restriction is True
        assert access.access_start == time(8, 0)
        assert access.access_end == time(17, 30)

    def test_contractor_allowed_weekdays(self, db, contractor_person, contractor_profile):
        access = self._make_contractor_access(db, contractor_person, contractor_profile)
        weekdays = [
            DayOfWeek.monday, DayOfWeek.tuesday, DayOfWeek.wednesday,
            DayOfWeek.thursday, DayOfWeek.friday,
        ]
        for day in weekdays:
            assert access.is_allowed_on_day(day) is True

    def test_contractor_blocked_weekends(self, db, contractor_person, contractor_profile):
        access = self._make_contractor_access(db, contractor_person, contractor_profile)
        assert access.is_allowed_on_day(DayOfWeek.saturday) is False
        assert access.is_allowed_on_day(DayOfWeek.sunday) is False

    def test_allowed_days_list_roundtrip(self, db, contractor_person, contractor_profile):
        access = self._make_contractor_access(db, contractor_person, contractor_profile)
        days = access.allowed_days_list
        assert "monday" in days
        assert "saturday" not in days
        assert len(days) == 5

    def test_custom_day_restriction(self, db, contractor_person, contractor_profile):
        access = PersonAccess(
            person_id=contractor_person.id,
            profile_id=contractor_profile.id,
            has_time_restriction=True,
            access_start=time(9, 0),
            access_end=time(16, 0),
        )
        access.allowed_days_list = [DayOfWeek.monday.value, DayOfWeek.wednesday.value]
        db.add(access)
        db.flush()
        assert access.is_allowed_on_day(DayOfWeek.monday) is True
        assert access.is_allowed_on_day(DayOfWeek.tuesday) is False
        assert access.is_allowed_on_day(DayOfWeek.wednesday) is True


# ── PersonAccessZone — individual overrides ───────────────────────────────────

class TestPersonAccessZoneOverrides:
    def test_grant_extra_zone(self, db, contractor_person, contractor_profile, boardroom_zone):
        access = PersonAccess(
            person_id=contractor_person.id,
            profile_id=contractor_profile.id,
            has_time_restriction=True,
            access_start=time(8, 0),
            access_end=time(17, 0),
        )
        access.allowed_days_list = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        db.add(access)
        db.flush()

        override = PersonAccessZone(
            person_access_id=access.id,
            zone_id=boardroom_zone.id,
            access_type=ZoneAccessType.grant,
            reason="Special project meeting access approved by Director",
        )
        db.add(override)
        db.flush()
        assert override.access_type == ZoneAccessType.grant
        assert override.reason is not None

    def test_deny_zone_override(self, db, director_person, director_profile, floor1_zone):
        access = PersonAccess(
            person_id=director_person.id,
            profile_id=director_profile.id,
            has_time_restriction=False,
        )
        db.add(access)
        db.flush()

        override = PersonAccessZone(
            person_access_id=access.id,
            zone_id=floor1_zone.id,
            access_type=ZoneAccessType.deny,
            reason="Under investigation — access suspended",
        )
        db.add(override)
        db.flush()
        assert override.access_type == ZoneAccessType.deny

    def test_duplicate_zone_override_rejected(self, db, contractor_person, contractor_profile, boardroom_zone):
        access = PersonAccess(
            person_id=contractor_person.id,
            profile_id=contractor_profile.id,
            has_time_restriction=False,
        )
        db.add(access)
        db.flush()
        o1 = PersonAccessZone(person_access_id=access.id, zone_id=boardroom_zone.id, access_type=ZoneAccessType.grant)
        db.add(o1)
        db.flush()
        o2 = PersonAccessZone(person_access_id=access.id, zone_id=boardroom_zone.id, access_type=ZoneAccessType.deny)
        db.add(o2)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


# ── Auto-assignment logic (pure Python — no DB needed) ────────────────────────

class TestAutoAssignmentLogic:
    """
    Verifies the rule: when a person is created with prefix X,
    the profile whose default_for_prefix_id == X is automatically assigned.
    This tests the lookup logic independently of the full API.
    """
    def test_lookup_profile_by_prefix(self, db, dir_prefix, director_profile):
        found = db.query(AccessProfile).filter(
            AccessProfile.default_for_prefix_id == dir_prefix.id
        ).first()
        assert found is not None
        assert found.id == director_profile.id

    def test_lookup_contractor_profile_by_prefix(self, db, ctr_prefix, contractor_profile):
        found = db.query(AccessProfile).filter(
            AccessProfile.default_for_prefix_id == ctr_prefix.id
        ).first()
        assert found is not None
        assert found.id == contractor_profile.id

    def test_no_profile_for_unknown_prefix(self, db):
        import uuid
        found = db.query(AccessProfile).filter(
            AccessProfile.default_for_prefix_id == uuid.uuid4()
        ).first()
        assert found is None


# ── DayOfWeek enum ────────────────────────────────────────────────────────────

class TestDayOfWeekEnum:
    def test_all_seven_days_defined(self):
        days = list(DayOfWeek)
        assert len(days) == 7

    def test_weekend_days_present(self):
        assert DayOfWeek.saturday in DayOfWeek
        assert DayOfWeek.sunday in DayOfWeek

    def test_values_are_lowercase(self):
        for day in DayOfWeek:
            assert day.value == day.value.lower()


# ── evaluate_card_access deny-by-default (M2) ─────────────────────────────────

class TestEvaluateCardAccess:
    class _Contract:
        is_expired = False

    def _person(self, **kw):
        import types
        from app.models.person import PersonStatus
        d = dict(status=PersonStatus.active, card_status="active",
                 nfc_uid="PERM123", temp_nfc_uid=None,
                 current_contract=self._Contract())
        d.update(kw)
        return types.SimpleNamespace(**d)

    def test_matching_permanent_card_granted(self):
        from app.services.people import evaluate_card_access
        assert evaluate_card_access(self._person(), "PERM123") == (True, None)

    def test_unknown_card_denied(self):
        from app.services.people import evaluate_card_access
        granted, reason = evaluate_card_access(self._person(), "STRANGER")
        assert granted is False and "Unrecognised" in reason

    def test_stolen_status_blocks_even_with_correct_card(self):
        from app.services.people import evaluate_card_access
        granted, reason = evaluate_card_access(self._person(card_status="stolen"), "PERM123")
        assert granted is False and "stolen" in reason.lower()

    def test_temp_card_out_temp_granted(self):
        from app.services.people import evaluate_card_access
        p = self._person(temp_nfc_uid="TEMP999", card_status="temporary")
        assert evaluate_card_access(p, "TEMP999") == (True, None)

    def test_temp_card_out_permanent_blocked(self):
        from app.services.people import evaluate_card_access
        p = self._person(temp_nfc_uid="TEMP999", card_status="temporary")
        granted, reason = evaluate_card_access(p, "PERM123")
        assert granted is False and "forgotten" in reason.lower()

    def test_temp_card_out_unknown_denied(self):
        from app.services.people import evaluate_card_access
        p = self._person(temp_nfc_uid="TEMP999", card_status="temporary")
        granted, reason = evaluate_card_access(p, "RANDOM")
        assert granted is False and "Unrecognised" in reason

    def test_inactive_holder_denied(self):
        from app.services.people import evaluate_card_access
        from app.models.person import PersonStatus
        granted, reason = evaluate_card_access(self._person(status=PersonStatus.suspended), "PERM123")
        assert granted is False
