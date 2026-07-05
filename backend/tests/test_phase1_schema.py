"""
Phase 1 Tests — Database schema integrity, constraints, relationships, business logic.
All tests must pass before Phase 2 begins.
"""
import re
import pytest
from datetime import date, timedelta
from sqlalchemy.exc import IntegrityError

from app.models.company import Company
from app.models.id_prefix import IdPrefix, PersonType
from app.models.app_user import AppUser, UserRole
from app.models.person import Person, PersonStatus
from app.models.contract import Contract, ContractType
from app.models.audit_log import AuditLog
from app.models.card_event import CardEvent, CardEventType
from app.models.import_job import ImportJob, ImportSource, ImportStatus


# ── Company tests ────────────────────────────────────────────────────────────

class TestCompany:
    def test_create_main_company(self, db, main_company):
        assert main_company.id is not None
        assert main_company.is_main_company is True
        assert main_company.name == "Acme Corporation"

    def test_create_contractor_company(self, db, contractor_company):
        assert contractor_company.is_main_company is False
        assert contractor_company.card_background_colour == "#EA580C"

    def test_company_name_required(self, db):
        company = Company(is_main_company=False)
        db.add(company)
        with pytest.raises(Exception):
            db.flush()
        db.rollback()


# ── ID Prefix tests ──────────────────────────────────────────────────────────

class TestIdPrefix:
    def test_create_prefix(self, db, dir_prefix):
        assert dir_prefix.prefix == "DIR"
        assert dir_prefix.applies_to == PersonType.employee
        assert dir_prefix.next_sequence == 1

    def test_generate_employee_id_format(self, db, dir_prefix):
        # prefix + 5 random digits (non-sequential, so IDs aren't guessable)
        eid = dir_prefix.generate_employee_id()
        assert re.fullmatch(r"DIR\d{5}", eid), eid

    def test_generate_employee_id_random_not_sequential(self, db, dir_prefix):
        # Two generations should (essentially always) differ and never be "-0001".
        ids = {dir_prefix.generate_employee_id() for _ in range(20)}
        assert all(re.fullmatch(r"DIR\d{5}", i) for i in ids)
        assert len(ids) > 1

    def test_prefix_unique_constraint(self, db, dir_prefix, super_admin):
        duplicate = IdPrefix(
            prefix="DIR",
            label="Different Director",
            applies_to=PersonType.employee,
            created_by=super_admin.id,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_contractor_prefix(self, db, ctr_prefix):
        assert ctr_prefix.applies_to == PersonType.contractor
        assert re.fullmatch(r"CTR\d{5}", ctr_prefix.generate_employee_id())

    def test_all_default_prefixes_coverable(self):
        defaults = [
            ("DIR", "Director", PersonType.employee),
            ("MGR", "Manager", PersonType.employee),
            ("ENG", "Engineer", PersonType.employee),
            ("HR", "Human Resources", PersonType.employee),
            ("ADM", "Admin", PersonType.employee),
            ("CTR", "Contractor", PersonType.contractor),
        ]
        for prefix, label, ptype in defaults:
            p = IdPrefix(prefix=prefix, label=label, applies_to=ptype, next_sequence=1)
            assert re.fullmatch(rf"{prefix}\d{{5}}", p.generate_employee_id())


# ── AppUser tests ────────────────────────────────────────────────────────────

class TestAppUser:
    def test_create_super_admin(self, db, super_admin):
        assert super_admin.role == UserRole.super_admin
        assert super_admin.mfa_enabled is True
        assert super_admin.is_active is True
        assert super_admin.failed_login_count == 0

    def test_email_unique_constraint(self, db, super_admin):
        duplicate = AppUser(
            email="admin@acme.com",
            display_name="Duplicate",
            password_hash="hash",
            role=UserRole.manager,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_all_roles_valid(self):
        roles = [UserRole.super_admin, UserRole.hr_admin, UserRole.it_admin, UserRole.manager]
        assert len(roles) == 4

    def test_manager_has_department_scope(self, db, super_admin):
        manager = AppUser(
            email="mgr@acme.com",
            display_name="Dept Manager",
            password_hash="hash",
            role=UserRole.manager,
            department_scope="Engineering",
            created_by=super_admin.id,
        )
        db.add(manager)
        db.flush()
        assert manager.department_scope == "Engineering"


# ── Person tests ─────────────────────────────────────────────────────────────

class TestPerson:
    def _make_person(self, db, company, prefix, created_by, **kwargs):
        person = Person(
            person_type=PersonType.employee,
            employee_id=prefix.generate_employee_id(),
            first_name="Jane",
            last_name="Smith",
            email=f"jane.smith.{prefix.next_sequence}@acme.com",
            job_title="Director of Operations",
            department="Operations",
            floor="3",
            company_id=company.id,
            prefix_id=prefix.id,
            created_by=created_by.id,
            **kwargs,
        )
        prefix.next_sequence += 1
        db.add(person)
        db.flush()
        return person

    def test_create_employee(self, db, main_company, dir_prefix, super_admin):
        person = self._make_person(db, main_company, dir_prefix, super_admin)
        assert person.id is not None
        assert re.fullmatch(r"DIR\d{5}", person.employee_id), person.employee_id
        assert person.full_name == "Jane Smith"
        assert person.status == PersonStatus.pending

    def test_full_name_property(self, db, main_company, dir_prefix, super_admin):
        person = self._make_person(db, main_company, dir_prefix, super_admin)
        assert person.full_name == "Jane Smith"

    def test_employee_id_unique(self, db, main_company, dir_prefix, super_admin):
        first = self._make_person(db, main_company, dir_prefix, super_admin)
        duplicate = Person(
            person_type=PersonType.employee,
            employee_id=first.employee_id,  # reuse the exact ID to force a collision
            first_name="Bob",
            last_name="Jones",
            email="bob.jones@acme.com",
            job_title="Director",
            department="Finance",
            company_id=main_company.id,
            prefix_id=dir_prefix.id,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_email_unique(self, db, main_company, dir_prefix, super_admin):
        self._make_person(db, main_company, dir_prefix, super_admin)
        dir_prefix.next_sequence = 99
        duplicate = Person(
            person_type=PersonType.employee,
            employee_id="DIR-0099",
            first_name="Clone",
            last_name="Smith",
            email=f"jane.smith.1@acme.com",
            job_title="Director",
            department="Operations",
            company_id=main_company.id,
            prefix_id=dir_prefix.id,
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_nfc_uid_unique_when_set(self, db, main_company, dir_prefix, ctr_prefix, super_admin):
        p1 = self._make_person(db, main_company, dir_prefix, super_admin)
        p1.nfc_uid = "AABBCCDD"
        db.flush()
        p2 = Person(
            person_type=PersonType.employee,
            employee_id="DIR-0099",
            first_name="Other",
            last_name="Person",
            email="other@acme.com",
            job_title="Director",
            department="HR",
            nfc_uid="AABBCCDD",
            company_id=main_company.id,
            prefix_id=dir_prefix.id,
        )
        db.add(p2)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()

    def test_contractor_links_to_contractor_company(self, db, contractor_company, ctr_prefix, super_admin):
        contractor = Person(
            person_type=PersonType.contractor,
            employee_id=ctr_prefix.generate_employee_id(),
            first_name="Bob",
            last_name="Builder",
            email="bob@buildright.com",
            job_title="Site Engineer",
            department="Construction",
            company_id=contractor_company.id,
            prefix_id=ctr_prefix.id,
            created_by=super_admin.id,
        )
        db.add(contractor)
        db.flush()
        assert contractor.company_id == contractor_company.id
        assert contractor.person_type == PersonType.contractor


# ── Contract tests ───────────────────────────────────────────────────────────

class TestContract:
    def _make_employee_with_contract(self, db, main_company, dir_prefix, super_admin):
        person = Person(
            person_type=PersonType.employee,
            employee_id=dir_prefix.generate_employee_id(),
            first_name="Test",
            last_name="Employee",
            email=f"test{dir_prefix.next_sequence}@acme.com",
            job_title="Director",
            department="Ops",
            company_id=main_company.id,
            prefix_id=dir_prefix.id,
        )
        dir_prefix.next_sequence += 1
        db.add(person)
        db.flush()
        contract = Contract.new_employee_contract(person.id, date.today())
        db.add(contract)
        db.flush()
        return person, contract

    def test_employee_contract_duration(self, db, main_company, dir_prefix, super_admin):
        _, contract = self._make_employee_with_contract(db, main_company, dir_prefix, super_admin)
        expected_end = date(
            date.today().year + 5,
            date.today().month,
            date.today().day,
        )
        assert contract.end_date == expected_end
        assert contract.contract_type == ContractType.employee_5yr
        assert contract.is_current is True

    def test_contractor_contract_duration(self, db, contractor_company, ctr_prefix, super_admin):
        contractor = Person(
            person_type=PersonType.contractor,
            employee_id=ctr_prefix.generate_employee_id(),
            first_name="Con",
            last_name="Tractor",
            email="con@builder.com",
            job_title="Builder",
            department="Build",
            company_id=contractor_company.id,
            prefix_id=ctr_prefix.id,
        )
        ctr_prefix.next_sequence += 1
        db.add(contractor)
        db.flush()
        contract = Contract.new_contractor_contract(contractor.id, date.today())
        db.add(contract)
        db.flush()
        expected_end = date.today() + timedelta(days=183)
        assert contract.end_date == expected_end
        assert contract.contract_type == ContractType.contractor_6mo

    def test_days_remaining_positive(self, db, main_company, dir_prefix, super_admin):
        _, contract = self._make_employee_with_contract(db, main_company, dir_prefix, super_admin)
        assert contract.days_remaining > 0
        assert not contract.is_expired

    def test_expired_contract(self, db, main_company, dir_prefix, super_admin):
        person, _ = self._make_employee_with_contract(db, main_company, dir_prefix, super_admin)
        past_contract = Contract(
            person_id=person.id,
            contract_type=ContractType.employee_5yr,
            start_date=date(2015, 1, 1),
            end_date=date(2020, 1, 1),
            is_current=False,
        )
        db.add(past_contract)
        db.flush()
        assert past_contract.is_expired is True
        assert past_contract.expiry_warning_level == "expired"

    def test_expiry_warning_levels(self, db, main_company, dir_prefix, super_admin):
        person, _ = self._make_employee_with_contract(db, main_company, dir_prefix, super_admin)

        cases = [
            (date.today() + timedelta(days=100), None),
            (date.today() + timedelta(days=60), "notice"),
            (date.today() + timedelta(days=20), "warning"),
            (date.today() + timedelta(days=7), "critical"),
            (date.today() - timedelta(days=1), "expired"),
        ]
        for end_date, expected_level in cases:
            c = Contract(
                person_id=person.id,
                contract_type=ContractType.employee_5yr,
                start_date=date(2020, 1, 1),
                end_date=end_date,
                is_current=False,
            )
            db.add(c)
            db.flush()
            assert c.expiry_warning_level == expected_level, f"Failed for end_date={end_date}"

    def test_contract_renewal_chain(self, db, main_company, dir_prefix, super_admin):
        person, original = self._make_employee_with_contract(db, main_company, dir_prefix, super_admin)
        original.is_current = False
        renewal = Contract.new_employee_contract(
            person.id,
            date.today(),
            renewed_by=super_admin.id,
            renewed_from=original.id,
        )
        db.add(renewal)
        db.flush()
        assert renewal.renewed_from == original.id
        assert renewal.is_current is True
        assert original.is_current is False


# ── AuditLog tests ───────────────────────────────────────────────────────────

class TestAuditLog:
    def test_create_audit_entry(self, db, super_admin):
        log = AuditLog(
            user_id=super_admin.id,
            action="create_employee",
            target_type="person",
            detail={"first_name": "Jane", "last_name": "Smith"},
            ip_address="127.0.0.1",
        )
        db.add(log)
        db.flush()
        assert log.id is not None
        assert log.timestamp is not None

    def test_audit_log_without_user(self, db):
        log = AuditLog(action="system_startup", ip_address="system")
        db.add(log)
        db.flush()
        assert log.user_id is None


# ── CardEvent tests ──────────────────────────────────────────────────────────

class TestCardEvent:
    def test_card_scan_event(self, db, main_company, dir_prefix, super_admin):
        person = Person(
            person_type=PersonType.employee,
            employee_id="DIR-0050",
            first_name="Card",
            last_name="Test",
            email="card@acme.com",
            job_title="Director",
            department="Ops",
            nfc_uid="DEADBEEF",
            company_id=main_company.id,
            prefix_id=dir_prefix.id,
        )
        db.add(person)
        db.flush()

        event = CardEvent(
            person_id=person.id,
            event_type=CardEventType.scan,
            nfc_uid="DEADBEEF",
            performed_by=super_admin.id,
            result="valid",
        )
        db.add(event)
        db.flush()
        assert event.id is not None
        assert event.timestamp is not None


# ── ImportJob tests ──────────────────────────────────────────────────────────

class TestImportJob:
    def test_create_import_job(self, db, super_admin):
        job = ImportJob(
            source_type=ImportSource.csv,
            filename="employees_2026.csv",
            status=ImportStatus.pending,
            started_by=super_admin.id,
        )
        db.add(job)
        db.flush()
        assert job.id is not None
        assert job.records_found == 0
        assert job.records_imported == 0

    def test_import_job_with_errors(self, db, super_admin):
        job = ImportJob(
            source_type=ImportSource.xlsx,
            filename="data.xlsx",
            status=ImportStatus.review,
            records_found=10,
            records_imported=8,
            records_skipped=2,
            errors=[{"row": 3, "error": "Missing email"}, {"row": 7, "error": "Invalid date"}],
            started_by=super_admin.id,
        )
        db.add(job)
        db.flush()
        assert len(job.errors) == 2
