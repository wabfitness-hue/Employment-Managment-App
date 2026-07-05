"""
Phase 4 Tests — Contract renewal, expiry engine, report generation,
renewal chains, edge cases (inactive person, no contract, leap years).
"""
import pytest
from datetime import date, timedelta
import uuid

from fastapi import HTTPException

from app.models.company import Company
from app.models.id_prefix import IdPrefix, PersonType
from app.models.person import Person, PersonStatus
from app.models.contract import Contract, ContractType
from app.models.app_user import AppUser, UserRole
from app.models.access import AccessProfile, AccessProfileZone, AccessZone
from app.services.contracts import (
    renew_contract, get_expiring_contracts, get_expired_contracts,
    get_contract_history, build_expiry_report,
)
from app.services.people import create_person
from app.api.v1.schemas.people import PersonCreate


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def main_company(db):
    c = Company(name="Acme Corp", is_main_company=True)
    db.add(c); db.flush(); return c

@pytest.fixture
def contractor_company(db):
    c = Company(name="Build Co", is_main_company=False)
    db.add(c); db.flush(); return c

@pytest.fixture
def emp_prefix(db):
    p = IdPrefix(prefix="P4E", label="Employee", applies_to=PersonType.employee, next_sequence=1)
    db.add(p); db.flush(); return p

@pytest.fixture
def ctr_prefix(db):
    p = IdPrefix(prefix="P4C", label="Contractor", applies_to=PersonType.contractor, next_sequence=1)
    db.add(p); db.flush(); return p

@pytest.fixture
def zone(db):
    z = AccessZone(code="ENT-P4", name="Entrance", floor="G", sort_order=1)
    db.add(z); db.flush(); return z

@pytest.fixture
def emp_profile(db, emp_prefix, zone):
    p = AccessProfile(name="Emp Profile P4", default_for_prefix_id=emp_prefix.id)
    db.add(p); db.flush()
    db.add(AccessProfileZone(profile_id=p.id, zone_id=zone.id))
    db.flush(); return p

@pytest.fixture
def ctr_profile(db, ctr_prefix, zone):
    p = AccessProfile(name="CTR Profile P4", default_for_prefix_id=ctr_prefix.id)
    db.add(p); db.flush()
    db.add(AccessProfileZone(profile_id=p.id, zone_id=zone.id))
    db.flush(); return p

@pytest.fixture
def hr_user(db):
    u = AppUser(email="hr4@acme.com", display_name="HR",
                password_hash="$2b$12$x", role=UserRole.hr_admin)
    db.add(u); db.flush(); return u

def _make_employee(db, main_company, emp_prefix, emp_profile, hr_user, **kwargs):
    defaults = dict(
        person_type=PersonType.employee,
        prefix_id=str(emp_prefix.id),
        first_name="Test", last_name="Employee",
        email=f"emp.{uuid.uuid4().hex[:6]}@acme.com",
        job_title="Engineer", department="Ops",
        company_id=str(main_company.id),
        contract_start=date.today(),
    )
    defaults.update(kwargs)
    return create_person(db, PersonCreate(**defaults), str(hr_user.id))

def _make_contractor(db, contractor_company, ctr_prefix, ctr_profile, hr_user, **kwargs):
    defaults = dict(
        person_type=PersonType.contractor,
        prefix_id=str(ctr_prefix.id),
        first_name="Bob", last_name="Contractor",
        email=f"ctr.{uuid.uuid4().hex[:6]}@build.com",
        job_title="Builder", department="Site",
        company_id=str(contractor_company.id),
        contract_start=date.today(),
    )
    defaults.update(kwargs)
    return create_person(db, PersonCreate(**defaults), str(hr_user.id))


# ── Employee renewal ──────────────────────────────────────────────────────────

class TestEmployeeRenewal:
    def test_renew_creates_new_5yr_contract(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        db.flush()
        new_contract = renew_contract(db, str(person.id), str(hr_user.id))
        expected_end = date(date.today().year + 5, date.today().month, date.today().day)
        assert new_contract.end_date == expected_end
        assert new_contract.contract_type == ContractType.employee_5yr
        assert new_contract.is_current is True

    def test_old_contract_marked_not_current(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        old_contract = person.current_contract
        old_id = old_contract.id
        db.flush()
        renew_contract(db, str(person.id), str(hr_user.id))
        db.refresh(old_contract)
        assert old_contract.is_current is False

    def test_renewed_contract_links_to_previous(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        old_id = person.current_contract.id
        db.flush()
        new_contract = renew_contract(db, str(person.id), str(hr_user.id))
        assert new_contract.renewed_from == old_id

    def test_renew_with_custom_start_date(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        db.flush()
        custom = date(2027, 1, 1)
        new_contract = renew_contract(db, str(person.id), str(hr_user.id), custom_start=custom)
        assert new_contract.start_date == custom
        assert new_contract.end_date == date(2032, 1, 1)

    def test_employee_renewal_count_stays_zero(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        db.flush()
        new_contract = renew_contract(db, str(person.id), str(hr_user.id))
        assert new_contract.renewal_count == 0

    def test_multiple_renewals_chain(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        db.flush()
        c1 = renew_contract(db, str(person.id), str(hr_user.id))
        db.flush()
        c2 = renew_contract(db, str(person.id), str(hr_user.id))
        assert c2.renewed_from == c1.id
        assert c1.is_current is False
        assert c2.is_current is True


# ── Contractor renewal ────────────────────────────────────────────────────────

class TestContractorRenewal:
    def test_renew_creates_new_6mo_contract(self, db, contractor_company, ctr_prefix, ctr_profile, hr_user):
        person = _make_contractor(db, contractor_company, ctr_prefix, ctr_profile, hr_user)
        db.flush()
        new_contract = renew_contract(db, str(person.id), str(hr_user.id))
        assert new_contract.contract_type == ContractType.contractor_6mo
        assert new_contract.is_current is True

    def test_contractor_renewal_starts_day_after_old_end(self, db, contractor_company, ctr_prefix, ctr_profile, hr_user):
        person = _make_contractor(db, contractor_company, ctr_prefix, ctr_profile, hr_user)
        old_end = person.current_contract.end_date
        db.flush()
        new_contract = renew_contract(db, str(person.id), str(hr_user.id))
        assert new_contract.start_date == old_end + timedelta(days=1)

    def test_contractor_renewal_count_increments(self, db, contractor_company, ctr_prefix, ctr_profile, hr_user):
        person = _make_contractor(db, contractor_company, ctr_prefix, ctr_profile, hr_user)
        db.flush()
        c1 = renew_contract(db, str(person.id), str(hr_user.id))
        assert c1.renewal_count == 1
        db.flush()
        c2 = renew_contract(db, str(person.id), str(hr_user.id))
        assert c2.renewal_count == 2

    def test_contractor_new_end_is_183_days_from_new_start(self, db, contractor_company, ctr_prefix, ctr_profile, hr_user):
        person = _make_contractor(db, contractor_company, ctr_prefix, ctr_profile, hr_user)
        old_end = person.current_contract.end_date
        db.flush()
        new_contract = renew_contract(db, str(person.id), str(hr_user.id))
        expected_end = new_contract.start_date + timedelta(days=183)
        assert new_contract.end_date == expected_end

    def test_continuous_renewal_no_gap(self, db, contractor_company, ctr_prefix, ctr_profile, hr_user):
        person = _make_contractor(db, contractor_company, ctr_prefix, ctr_prefix, hr_user)
        db.flush()
        c1 = renew_contract(db, str(person.id), str(hr_user.id))
        db.flush()
        c2 = renew_contract(db, str(person.id), str(hr_user.id))
        # c2 starts exactly one day after c1 ends — no gap in coverage
        assert c2.start_date == c1.end_date + timedelta(days=1)


# ── Guard conditions ──────────────────────────────────────────────────────────

class TestRenewalGuards:
    def test_renew_inactive_person_rejected(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        person.status = PersonStatus.inactive
        db.flush()
        with pytest.raises(HTTPException) as exc:
            renew_contract(db, str(person.id), str(hr_user.id))
        assert exc.value.status_code == 422
        assert "inactive" in exc.value.detail.lower()

    def test_renew_nonexistent_person_raises_404(self, db, hr_user):
        with pytest.raises(HTTPException) as exc:
            renew_contract(db, str(uuid.uuid4()), str(hr_user.id))
        assert exc.value.status_code == 404

    def test_renew_invalid_uuid_raises_422(self, db, hr_user):
        with pytest.raises(HTTPException) as exc:
            renew_contract(db, "not-a-uuid", str(hr_user.id))
        assert exc.value.status_code == 422


# ── Expiry queries ────────────────────────────────────────────────────────────

class TestExpiryQueries:
    def _person_with_end_date(self, db, main_company, emp_prefix, emp_profile, hr_user, end_date):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        contract = person.current_contract
        contract.end_date = end_date
        db.flush()
        return person

    def test_finds_contract_expiring_within_window(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = self._person_with_end_date(
            db, main_company, emp_prefix, emp_profile, hr_user,
            date.today() + timedelta(days=20)
        )
        results = get_expiring_contracts(db, 30)
        ids = [r["person_id"] for r in results]
        assert str(person.id) in ids

    def test_does_not_find_contract_outside_window(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = self._person_with_end_date(
            db, main_company, emp_prefix, emp_profile, hr_user,
            date.today() + timedelta(days=120)
        )
        results = get_expiring_contracts(db, 30)
        ids = [r["person_id"] for r in results]
        assert str(person.id) not in ids

    def test_expired_not_in_expiring_list(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = self._person_with_end_date(
            db, main_company, emp_prefix, emp_profile, hr_user,
            date.today() - timedelta(days=5)
        )
        results = get_expiring_contracts(db, 90)
        ids = [r["person_id"] for r in results]
        assert str(person.id) not in ids

    def test_inactive_person_excluded_from_expiring(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = self._person_with_end_date(
            db, main_company, emp_prefix, emp_profile, hr_user,
            date.today() + timedelta(days=5)
        )
        person.status = PersonStatus.inactive
        db.flush()
        results = get_expiring_contracts(db, 30)
        ids = [r["person_id"] for r in results]
        assert str(person.id) not in ids

    def test_warning_level_in_results(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = self._person_with_end_date(
            db, main_company, emp_prefix, emp_profile, hr_user,
            date.today() + timedelta(days=7)
        )
        results = get_expiring_contracts(db, 30)
        match = next((r for r in results if r["person_id"] == str(person.id)), None)
        assert match is not None
        assert match["warning_level"] == "critical"

    def test_results_ordered_by_end_date(self, db, main_company, emp_prefix, emp_profile, hr_user):
        self._person_with_end_date(db, main_company, emp_prefix, emp_profile, hr_user,
                                    date.today() + timedelta(days=25))
        self._person_with_end_date(db, main_company, emp_prefix, emp_profile, hr_user,
                                    date.today() + timedelta(days=5))
        results = get_expiring_contracts(db, 90)
        dates = [r["end_date"] for r in results]
        assert dates == sorted(dates)


# ── Expired contracts ─────────────────────────────────────────────────────────

class TestExpiredContracts:
    def test_finds_overdue_contracts(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        contract = person.current_contract
        contract.end_date = date.today() - timedelta(days=10)
        db.flush()
        results = get_expired_contracts(db)
        ids = [r["person_id"] for r in results]
        assert str(person.id) in ids

    def test_days_overdue_calculated(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        contract = person.current_contract
        contract.end_date = date.today() - timedelta(days=15)
        db.flush()
        results = get_expired_contracts(db)
        match = next((r for r in results if r["person_id"] == str(person.id)), None)
        assert match is not None
        assert match["days_overdue"] == 15

    def test_active_contract_not_in_expired(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        db.flush()
        results = get_expired_contracts(db)
        ids = [r["person_id"] for r in results]
        assert str(person.id) not in ids


# ── Contract history ──────────────────────────────────────────────────────────

class TestContractHistory:
    def test_history_includes_all_contracts(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        db.flush()
        renew_contract(db, str(person.id), str(hr_user.id))
        db.flush()
        renew_contract(db, str(person.id), str(hr_user.id))
        db.flush()
        history = get_contract_history(db, str(person.id))
        assert len(history) == 3

    def test_history_newest_first(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        db.flush()
        renew_contract(db, str(person.id), str(hr_user.id))
        db.flush()
        history = get_contract_history(db, str(person.id))
        assert history[0].start_date >= history[1].start_date

    def test_history_invalid_id_raises_422(self, db):
        with pytest.raises(HTTPException) as exc:
            get_contract_history(db, "bad-uuid")
        assert exc.value.status_code == 422


# ── Expiry report ─────────────────────────────────────────────────────────────

class TestExpiryReport:
    def test_report_has_required_keys(self, db):
        report = build_expiry_report(db)
        assert "generated_on" in report
        assert "total_expiring" in report
        assert "total_expired" in report
        assert "groups" in report
        assert "thresholds" in report

    def test_report_groups_have_expected_levels(self, db):
        report = build_expiry_report(db)
        assert "critical" in report["groups"]
        assert "warning" in report["groups"]
        assert "notice" in report["groups"]
        assert "expired" in report["groups"]

    def test_report_counts_match_groups(self, db, main_company, emp_prefix, emp_profile, hr_user):
        person = _make_employee(db, main_company, emp_prefix, emp_profile, hr_user)
        person.current_contract.end_date = date.today() + timedelta(days=7)
        db.flush()
        report = build_expiry_report(db)
        total = sum(
            len(v) for k, v in report["groups"].items() if k != "expired"
        )
        assert report["total_expiring"] == total

    def test_report_generated_on_is_today(self, db):
        report = build_expiry_report(db)
        assert report["generated_on"] == date.today().isoformat()

    def test_report_thresholds_match_config(self, db):
        from app.core.config import get_settings
        settings = get_settings()
        report = build_expiry_report(db)
        assert report["thresholds"] == settings.ALERT_DAYS_BEFORE_EXPIRY


# ── Contract model properties ─────────────────────────────────────────────────

class TestContractModel:
    def test_days_remaining_today_expiry(self):
        c = Contract(
            contract_type=ContractType.employee_5yr,
            start_date=date.today(),
            end_date=date.today(),
        )
        assert c.days_remaining == 0

    def test_is_expired_true_when_past(self):
        c = Contract(
            contract_type=ContractType.employee_5yr,
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
        )
        assert c.is_expired is True

    def test_is_expired_false_when_future(self):
        c = Contract(
            contract_type=ContractType.employee_5yr,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
        )
        assert c.is_expired is False

    @pytest.mark.parametrize("days,expected_level", [
        (100, None),
        (89,  "notice"),
        (29,  "warning"),
        (13,  "critical"),
        (-1,  "expired"),
    ])
    def test_warning_levels(self, days, expected_level):
        c = Contract(
            contract_type=ContractType.employee_5yr,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=days),
        )
        assert c.expiry_warning_level == expected_level
