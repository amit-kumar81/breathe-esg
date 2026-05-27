"""
Shared test fixtures and base classes for BreatheESG test suite.

Provides a BaseBreatheTestCase with pre-built:
- Tenant
- Admin, Analyst, Data Provider, and Viewer users (each with UserProfile)
- DataSource (SAP type with standard field mapping)
- JWT authentication helper
"""

import io
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from breathe.apps.tenants.models import Tenant
from breathe.apps.auth.models import UserProfile
from breathe.apps.ingest.models import DataSource, RawIngestion, ParsedRecord, NormalizedRecord
from breathe.apps.review.models import ReviewTask, ReviewApproval
from breathe.apps.emissions.models import EmissionsDataPoint


class BaseBreatheTestCase(APITestCase):
    """
    Base test case with tenant, users, and data source pre-created.

    Subclass this and call super().setUp() to get:
      self.tenant      — Tenant instance
      self.admin       — User with ADMIN role
      self.analyst     — User with ANALYST role
      self.provider    — User with DATA_PROVIDER role
      self.viewer      — User with VIEWER role
      self.data_source — DataSource (SAP) with standard field mapping
    """

    SAMPLE_CSV = (
        "Plant_Name,Scope1_MT,Scope2_MT,Year\n"
        "Plant Alpha,1000.5,500.25,2023\n"
        "Plant Beta,2000.0,800.0,2023\n"
        "Plant Gamma,0,300.0,2022\n"
    )

    SAP_FIELD_MAPPING = {
        "Plant_Name": "facility_name",
        "Scope1_MT": "scope_1_emissions",
        "Scope2_MT": "scope_2_emissions",
        "Year": "reporting_year",
    }

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Corp",
            slug="test-corp",
            plan="PROFESSIONAL",
            is_active=True,
        )

        self.admin = self._make_user("admin_user", "admin@test.com", "ADMIN")
        self.analyst = self._make_user("analyst_user", "analyst@test.com", "ANALYST")
        self.provider = self._make_user("provider_user", "provider@test.com", "DATA_PROVIDER")
        self.viewer = self._make_user("viewer_user", "viewer@test.com", "VIEWER")

        self.data_source = DataSource.objects.create(
            tenant_id=self.tenant,
            source_type="SAP",
            name="Demo SAP Export",
            field_mapping=self.SAP_FIELD_MAPPING,
        )

    def _make_user(self, username, email, role, password="testpass123"):
        user = User.objects.create_user(username=username, email=email, password=password)
        UserProfile.objects.create(user=user, tenant=self.tenant, role=role)
        return user

    def auth(self, user):
        """Attach JWT auth header for the given user."""
        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def deauth(self):
        self.client.credentials()

    def make_csv_file(self, content=None, filename="test.csv"):
        """Return a BytesIO file-like object suitable for multipart upload."""
        csv_bytes = (content or self.SAMPLE_CSV).encode("utf-8")
        f = io.BytesIO(csv_bytes)
        f.name = filename
        return f

    def create_ingestion(self, csv_content=None):
        """Create a RawIngestion directly (bypassing upload endpoint)."""
        content = csv_content or self.SAMPLE_CSV
        return RawIngestion.objects.create(
            tenant_id=self.tenant,
            data_source_id=self.data_source,
            filename="test.csv",
            file_hash=RawIngestion.compute_hash(content.encode()),
            line_count=content.count("\n") - 1,
            raw_csv_content=content,
        )

    def create_parsed_records(self, ingestion):
        """Parse an ingestion's CSV content into ParsedRecords."""
        from breathe.apps.ingest.utils import parse_raw_ingestion
        parse_raw_ingestion(ingestion)
        return ParsedRecord.objects.filter(ingestion_id=ingestion)

    def create_normalized_records(self, ingestion):
        """Run full normalization (also creates EmissionsDataPoints and ReviewTasks)."""
        from breathe.apps.ingest.normalization import normalize_ingestion
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        return NormalizedRecord.objects.filter(ingestion_id=ingestion)

    def create_review_task(self, status="PENDING", priority="MEDIUM"):
        """Create a standalone ReviewTask with a minimal NormalizedRecord."""
        ingestion = self.create_ingestion()
        self.create_normalized_records(ingestion)
        task = ReviewTask.objects.filter(ingestion_id=ingestion, status="PENDING").first()
        if task and status != "PENDING":
            task.status = status
            task.save()
        return task

    def create_emissions_point(self, facility="Test Plant", scope="SCOPE_1",
                               value=1000.0, year=2023):
        return EmissionsDataPoint.objects.create(
            tenant_id=self.tenant,
            data_source_id=self.data_source,
            facility_name=facility,
            scope=scope,
            emissions_value=value,
            emissions_unit="mtCO2e",
            year=year,
            is_valid=True,
            normalized_values={"facility_name": facility},
            validation_errors=[],
            data_quality_flags=[],
        )
