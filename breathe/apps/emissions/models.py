"""
Emissions data models (normalized).

Design Philosophy:
- Hybrid Relational + JSONB: frequently queried fields are relational, flexible fields are JSONB.
- Relational fields (facility_name, emissions_value, year, methodology) allow fast filtering and aggregation.
- JSONB fields (normalized_values, validation_errors, data_quality_flags) handle flexible, evolving schemas.
- is_valid flag enables quick "approved vs. needs review" queries.
"""

import uuid
from django.db import models
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource, ParsedRecord


class EmissionsDataPoint(models.Model):
    """
    A single emissions record after normalization and validation.

    This is the central entity: analysts review, approve, or reject these.
    """
    SCOPE_CHOICES = (
        ('SCOPE_1', 'Scope 1: Direct emissions'),
        ('SCOPE_2', 'Scope 2: Indirect (electricity, steam)'),
        ('SCOPE_3', 'Scope 3: Value chain'),
    )

    UNIT_CHOICES = (
        ('mtCO2e', 'Metric tons CO2 equivalent'),
        ('tCO2e', 'Tons CO2 equivalent'),
        ('kgCO2e', 'Kilograms CO2 equivalent'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emissions_data_points')
    parsed_record_id = models.ForeignKey(ParsedRecord, on_delete=models.SET_NULL, null=True, related_name='emissions_data_points')
    data_source_id = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='emissions_data_points')

    # --- Relational fields (fast queries) ---
    # Key searchable fields stored as relational columns
    facility_name = models.CharField(max_length=255, db_index=True)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, db_index=True)
    emissions_value = models.DecimalField(max_digits=15, decimal_places=4, help_text="Numeric emissions value")
    emissions_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='mtCO2e')
    year = models.IntegerField(db_index=True, help_text="Reporting year")
    methodology = models.CharField(max_length=255, blank=True, null=True, help_text="Calculation methodology")

    # Validation and review state
    is_valid = models.BooleanField(default=False, db_index=True, help_text="Passed all validation checks")

    # --- JSONB fields (flexible schema) ---
    # All normalized values (subset or superset of relational fields)
    # Example: {"facility_name": "Plant A", "scope_1_emissions": 1234.56, ...}
    normalized_values = models.JSONField(default=dict, help_text="Complete normalized data as JSON")

    # Validation errors: [{"field": "facility_name", "error": "missing"}]
    validation_errors = models.JSONField(default=list, help_text="List of validation failures")

    # Data quality flags: [{"field": "methodology", "severity": "warning", "message": "Not provided"}]
    data_quality_flags = models.JSONField(default=list, help_text="Quality warnings and issues")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'emissions_emissions_data_point'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['data_source_id']),
            models.Index(fields=['facility_name', 'year']),
            models.Index(fields=['is_valid', 'year']),
        ]

    def __str__(self):
        return f"{self.facility_name} ({self.scope}) {self.year}: {self.emissions_value} {self.emissions_unit}"
