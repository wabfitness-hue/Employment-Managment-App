"""
Phase 3 Tests — Employee/Contractor CRUD, ID generation, auto access assignment,
NFC lookup, manager scope enforcement, validation rules.
"""
import re
import pytest
import uuid
from datetime import date, timedelta

from app.models.company import Company
from app.models.id_prefix import IdPrefix, PersonType
from app.models.person import Person, PersonStatus
from app.models.contract import Contract, ContractType
from app.models.access import AccessProfile, AccessProfileZone, AccessZone, PersonAccess
from app.models.app_user import AppUser, UserRole
from app.services.people import (
    create_person, update_person, change_status,
    assign_nfc, lookup_by_nfc, list_people, get_person_or_404,
)
from app.api.v1.schemas.people import (
    PersonCreate, PersonUpdate, StatusChangeRequest, PersonFilter,
)
from fastapi import HTTPException


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def main_company(db):
    c = Company(name="Acme Corp", is_main_company=True,
                card_background_colour="#1E40AF", card_text_colour="#FFFFFF")
    db.add(c); db.flush(); return c

@pytest.fixture
def contractor_company(db):
    c = Company(name="BuildRight Ltd", is_main_company=False,
                card_background_colour="#EA580C", card_text_colour="#FFFFFF")
    db.add(c); db.flush(); return c

@pytest.fixture
def dir_prefix(db):
    p = IdPrefix(prefix="D3", label="Director", applies_to=PersonType.employee, next_sequence=1)
    db.add(p); db.flush(); return p

@pytest.fixture
def eng_prefix(db):
    p = IdPrefix(prefix="E3", label="Engineer", applies_to=PersonType.employee, next_sequence=1)
    db.add(p); db.flush(); return p

@pytest.fixture
def ctr_prefix(db):
    p = IdPrefix(prefix="C3", label="Contractor", applies_to=PersonType.contractor, next_sequence=1)
    db.add(p); db.flush(); return p

@pytest.fixture
def entrance_zone(db):
    z = AccessZone(code="ENT-P3", name="Main Entrance", floor="G", sort_order=1)
    db.add(z); db.flush(); return z

@pytest.fixture
def floor1_zone(db):
    z = AccessZone(code="F1-P3", name="Floor 1", floor="1", sort_order=2)
    db.add(z); db.flush(); return z

@pytest.fixture
def dir_profile(db, dir_prefix, entrance_zone, floor1_zone):
    p = AccessProfile(name="Dir Profile P3", default_for_prefix_id=dir_prefix.id)
    db.add(p); db.flush()
    for z in [entrance_zone, floor1_zone]:
        db.add(AccessProfileZone(profile_id=p.id, zone_id=z.id))
    db.flush(); return p

@pytest.fixture
def ctr_profile(db, ctr_prefix, entrance_zone):
    p = AccessProfile(name="CTR Profile P3", default_for_prefix_id=ctr_prefix.id)
    db.add(p); db.flush()
    db.add(AccessProfileZone(profile_id=p.id, zone_id=entrance_zone.id))
    db.flush(); return p

@pytest.fixture
def hr_admin(db):
    u = AppUser(email="hr@acme.com", display_name="HR Admin",
                password_hash="$2b$12$x", role=UserRole.hr_admin)
    db.add(u); db.flush(); return u

@pytest.fixture
def manager_user(db):
    u = AppUser(email="mgr@acme.com", display_name="Manager",
                password_hash="$2b$12$x", role=UserRole.manager,
                department_scope="Engineering")
    db.add(u); db.flush(); return u

def _emp_payload(main_company, dir_prefix, **kwargs):
    defaults = dict(
        person_type=PersonType.employee,
        prefix_id=str(dir_prefix.id),
        first_name="Jane", last_name="Smith",
        email=f"jane.{uuid.uuid4().hex[:6]}@acme.com",
        job_title="Director", department="Operations",
        company_id=str(main_company.id),
        contract_start=date.today(),
    )
    defaults.update(kwargs)
    return PersonCreate(**defaults)

def _ctr_payload(contractor_company, ctr_prefix, **kwargs):
    defaults = dict(
        person_type=PersonType.contractor,
        prefix_id=str(ctr_prefix.id),
        first_name="Bob", last_name="Builder",
        email=f"bob.{uuid.uuid4().hex[:6]}@build.com",
        job_title="Site Engineer", department="Construction",
        company_id=str(contractor_company.id),
        contract_start=date.today(),
    )
    defaults.update(kwargs)
    return PersonCreate(**defaults)


# ── ID generation ─────────────────────────────────────────────────────────────

class TestIDGeneration:
    def test_first_employee_id(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        # IDs are prefix + 7 random digits (non-sequential, so they aren't guessable).
        payload = _emp_payload(main_company, dir_prefix)
        person = create_person(db, payload, str(hr_admin.id))
        assert re.fullmatch(r"D3\d{7}", person.employee_id), person.employee_id

    def test_ids_are_unique(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        ids = set()
        for _ in range(10):
            payload = _emp_payload(main_company, dir_prefix)
            person = create_person(db, payload, str(hr_admin.id))
            assert re.fullmatch(r"D3\d{7}", person.employee_id), person.employee_id
            ids.add(person.employee_id)
        assert len(ids) == 10  # no collisions

    def test_contractor_id_uses_ctr_prefix(self, db, contractor_company, ctr_prefix, ctr_profile, hr_admin):
        payload = _ctr_payload(contractor_company, ctr_prefix)
        person = create_person(db, payload, str(hr_admin.id))
        assert re.fullmatch(r"C3\d{7}", person.employee_id), person.employee_id

    def test_different_prefixes_use_their_own_prefix(self, db, main_company, dir_prefix, eng_prefix, dir_profile, hr_admin):
        AccessProfile(name="Eng Profile P3", default_for_prefix_id=eng_prefix.id)
        p1 = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        p2 = create_person(db, PersonCreate(
            person_type=PersonType.employee,
            prefix_id=str(eng_prefix.id),
            first_name="Alice", last_name="Eng",
            email=f"alice.{uuid.uuid4().hex[:6]}@acme.com",
            job_title="Engineer", department="Engineering",
            company_id=str(main_company.id),
            contract_start=date.today(),
        ), str(hr_admin.id))
        assert re.fullmatch(r"D3\d{7}", p1.employee_id), p1.employee_id
        assert re.fullmatch(r"E3\d{7}", p2.employee_id), p2.employee_id


# ── Create employee ───────────────────────────────────────────────────────────

class TestCreateEmployee:
    def test_creates_with_pending_status(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        assert person.status == PersonStatus.pending

    def test_creates_5yr_contract(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        contract = person.current_contract
        assert contract is not None
        assert contract.contract_type == ContractType.employee_5yr
        expected_end = date(date.today().year + 5, date.today().month, date.today().day)
        assert contract.end_date == expected_end

    def test_auto_assigns_access_profile(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        access = db.query(PersonAccess).filter(PersonAccess.person_id == person.id).first()
        assert access is not None
        assert access.profile_id == dir_profile.id
        assert access.has_time_restriction is False

    def test_employee_no_time_restriction(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        access = db.query(PersonAccess).filter(PersonAccess.person_id == person.id).first()
        assert access.allowed_days is None
        assert access.access_start is None

    def test_duplicate_email_rejected(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        email = f"dup.{uuid.uuid4().hex[:6]}@acme.com"
        create_person(db, _emp_payload(main_company, dir_prefix, email=email), str(hr_admin.id))
        with pytest.raises(HTTPException) as exc:
            create_person(db, _emp_payload(main_company, dir_prefix, email=email), str(hr_admin.id))
        assert exc.value.status_code == 409

    def test_wrong_prefix_type_rejected(self, db, main_company, ctr_prefix, hr_admin):
        payload = PersonCreate(
            person_type=PersonType.employee,
            prefix_id=str(ctr_prefix.id),
            first_name="Wrong", last_name="Type",
            email=f"wrong.{uuid.uuid4().hex[:6]}@acme.com",
            job_title="Director", department="Ops",
            company_id=str(main_company.id),
            contract_start=date.today(),
        )
        with pytest.raises(HTTPException) as exc:
            create_person(db, payload, str(hr_admin.id))
        assert exc.value.status_code == 422

    def test_employee_must_use_main_company(self, db, contractor_company, dir_prefix, hr_admin):
        payload = _emp_payload(contractor_company, dir_prefix,
                               company_id=str(contractor_company.id))
        with pytest.raises(HTTPException) as exc:
            create_person(db, payload, str(hr_admin.id))
        assert exc.value.status_code == 422


# ── Create contractor ─────────────────────────────────────────────────────────

class TestCreateContractor:
    def test_creates_6mo_contract(self, db, contractor_company, ctr_prefix, ctr_profile, hr_admin):
        person = create_person(db, _ctr_payload(contractor_company, ctr_prefix), str(hr_admin.id))
        contract = person.current_contract
        assert contract.contract_type == ContractType.contractor_6mo
        expected = date.today() + __import__('datetime').timedelta(days=183)
        assert contract.end_date == expected

    def test_contractor_gets_time_restriction(self, db, contractor_company, ctr_prefix, ctr_profile, hr_admin):
        person = create_person(db, _ctr_payload(contractor_company, ctr_prefix), str(hr_admin.id))
        access = db.query(PersonAccess).filter(PersonAccess.person_id == person.id).first()
        assert access.has_time_restriction is True
        assert access.access_start is not None
        assert access.access_end is not None
        assert "monday" in access.allowed_days

    def test_contractor_blocked_from_main_company(self, db, main_company, ctr_prefix, hr_admin):
        payload = _ctr_payload(main_company, ctr_prefix,
                               company_id=str(main_company.id))
        with pytest.raises(HTTPException) as exc:
            create_person(db, payload, str(hr_admin.id))
        assert exc.value.status_code == 422

    def test_contractor_auto_assigns_contractor_profile(self, db, contractor_company, ctr_prefix, ctr_profile, hr_admin):
        person = create_person(db, _ctr_payload(contractor_company, ctr_prefix), str(hr_admin.id))
        access = db.query(PersonAccess).filter(PersonAccess.person_id == person.id).first()
        assert access.profile_id == ctr_profile.id


# ── Update ────────────────────────────────────────────────────────────────────

class TestUpdatePerson:
    def test_update_name(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        updated = update_person(db, str(person.id), PersonUpdate(first_name="Janet"))
        assert updated.first_name == "Janet"

    def test_update_department(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        updated = update_person(db, str(person.id), PersonUpdate(department="Finance"))
        assert updated.department == "Finance"

    def test_update_email_conflict_rejected(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        p1 = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        p2 = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        with pytest.raises(HTTPException) as exc:
            update_person(db, str(p2.id), PersonUpdate(email=p1.email))
        assert exc.value.status_code == 409

    def test_partial_update_preserves_other_fields(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix,
                                                 first_name="Alice", last_name="Jones"), str(hr_admin.id))
        update_person(db, str(person.id), PersonUpdate(floor="4"))
        assert person.first_name == "Alice"
        assert person.floor == "4"

    def test_blank_name_rejected(self):
        with pytest.raises(Exception):
            PersonUpdate(first_name="  ")

    def test_person_not_found_raises_404(self, db):
        with pytest.raises(HTTPException) as exc:
            update_person(db, str(uuid.uuid4()), PersonUpdate(floor="5"))
        assert exc.value.status_code == 404


# ── Status changes ────────────────────────────────────────────────────────────

class TestStatusChange:
    def test_activate_person(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        assert person.status == PersonStatus.pending
        updated = change_status(db, str(person.id), PersonStatus.active, str(hr_admin.id))
        assert updated.status == PersonStatus.active

    def test_deactivate_person(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        change_status(db, str(person.id), PersonStatus.active, str(hr_admin.id))
        updated = change_status(db, str(person.id), PersonStatus.inactive, str(hr_admin.id))
        assert updated.status == PersonStatus.inactive

    def test_suspend_person(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        updated = change_status(db, str(person.id), PersonStatus.suspended, str(hr_admin.id))
        assert updated.status == PersonStatus.suspended


# ── NFC ───────────────────────────────────────────────────────────────────────

class TestNFC:
    def test_assign_nfc_uid(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        updated = assign_nfc(db, str(person.id), "AABBCCDD")
        assert updated.nfc_uid == "AABBCCDD"

    def test_nfc_uid_uppercased(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        updated = assign_nfc(db, str(person.id), "aabbccdd")
        assert updated.nfc_uid == "AABBCCDD"

    def test_duplicate_nfc_uid_rejected(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        p1 = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        p2 = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        assign_nfc(db, str(p1.id), "DEADBEEF")
        db.flush()
        with pytest.raises(HTTPException) as exc:
            assign_nfc(db, str(p2.id), "DEADBEEF")
        assert exc.value.status_code == 409

    def test_lookup_by_nfc(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        assign_nfc(db, str(person.id), "12345678")
        db.flush()
        found = lookup_by_nfc(db, "12345678")
        assert found.id == person.id

    def test_lookup_nfc_case_insensitive(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        assign_nfc(db, str(person.id), "CAFEBABE")
        db.flush()
        found = lookup_by_nfc(db, "cafebabe")
        assert found.id == person.id

    def test_lookup_unknown_nfc_raises_404(self, db):
        with pytest.raises(HTTPException) as exc:
            lookup_by_nfc(db, "UNKNOWN0")
        assert exc.value.status_code == 404


# ── List / search / filter ────────────────────────────────────────────────────

class TestListPeople:
    def _create_set(self, db, main_company, dir_prefix, dir_profile, contractor_company, ctr_prefix, ctr_profile, hr_admin):
        people = []
        for i in range(3):
            people.append(create_person(db, _emp_payload(
                main_company, dir_prefix,
                first_name=f"Employee{i}", department="Engineering"
            ), str(hr_admin.id)))
        people.append(create_person(db, _ctr_payload(
            contractor_company, ctr_prefix, department="Construction"
        ), str(hr_admin.id)))
        db.flush()
        return people

    def test_list_all(self, db, main_company, dir_prefix, dir_profile,
                      contractor_company, ctr_prefix, ctr_profile, hr_admin):
        self._create_set(db, main_company, dir_prefix, dir_profile,
                         contractor_company, ctr_prefix, ctr_profile, hr_admin)
        result = list_people(db, PersonFilter(), "hr_admin", None)
        assert len(result) >= 4

    def test_filter_by_type(self, db, main_company, dir_prefix, dir_profile,
                             contractor_company, ctr_prefix, ctr_profile, hr_admin):
        self._create_set(db, main_company, dir_prefix, dir_profile,
                         contractor_company, ctr_prefix, ctr_profile, hr_admin)
        employees = list_people(db, PersonFilter(person_type=PersonType.employee), "hr_admin", None)
        contractors = list_people(db, PersonFilter(person_type=PersonType.contractor), "hr_admin", None)
        assert all(p.person_type == PersonType.employee for p in employees)
        assert all(p.person_type == PersonType.contractor for p in contractors)

    def test_search_by_name(self, db, main_company, dir_prefix, dir_profile,
                             contractor_company, ctr_prefix, ctr_profile, hr_admin):
        self._create_set(db, main_company, dir_prefix, dir_profile,
                         contractor_company, ctr_prefix, ctr_profile, hr_admin)
        result = list_people(db, PersonFilter(search="Employee0"), "hr_admin", None)
        assert len(result) >= 1
        assert any("Employee0" in p.first_name for p in result)

    def test_manager_sees_only_own_dept(self, db, main_company, dir_prefix, dir_profile,
                                         contractor_company, ctr_prefix, ctr_profile, hr_admin):
        self._create_set(db, main_company, dir_prefix, dir_profile,
                         contractor_company, ctr_prefix, ctr_profile, hr_admin)
        result = list_people(db, PersonFilter(), "manager", "Engineering")
        assert all(p.department == "Engineering" for p in result)

    def test_filter_expiring_contracts(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        # Create a person with a nearly-expired contract
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        contract = person.current_contract
        contract.end_date = date.today() + timedelta(days=10)
        db.flush()
        result = list_people(db, PersonFilter(expiring_within_days=30), "hr_admin", None)
        ids = [p.id for p in result]
        assert person in ids or person.id in [p.id for p in result]


# ── get_person_or_404 ─────────────────────────────────────────────────────────

class TestGetPerson:
    def test_valid_id_returns_person(self, db, main_company, dir_prefix, dir_profile, hr_admin):
        person = create_person(db, _emp_payload(main_company, dir_prefix), str(hr_admin.id))
        found = get_person_or_404(db, str(person.id))
        assert found.id == person.id

    def test_invalid_uuid_raises_422(self, db):
        with pytest.raises(HTTPException) as exc:
            get_person_or_404(db, "not-a-uuid")
        assert exc.value.status_code == 422

    def test_missing_id_raises_404(self, db):
        with pytest.raises(HTTPException) as exc:
            get_person_or_404(db, str(uuid.uuid4()))
        assert exc.value.status_code == 404
