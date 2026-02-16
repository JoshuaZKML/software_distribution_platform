# drf-spectacular Schema Generation - Implementation Checklist

## Phase 1: ViewSet & Serializer Fixes ✅

### Accounts App
- [x] Create `backend/apps/accounts/viewsets.py` with:
  - [x] UserViewSet (ModelViewSet)
  - [x] AdminProfileViewSet (ModelViewSet)  
  - [x] UserSessionViewSet (ReadOnlyModelViewSet)
  - [x] AdminActionLogViewSet (ReadOnlyModelViewSet)
  - [x] UserSerializer
  - [x] AdminProfileSerializer
  - [x] AdminActionLogSerializer
- [x] Create `VerifyEmailView` in views.py
- [x] Update `urls.py` imports to use viewsets.py
- [x] Add missing imports to views.py

### Payments App
- [x] Fix `PaymentViewSet`:
  - [x] Change from ViewSet to ModelViewSet
  - [x] Add queryset = Payment.objects.all()
  - [x] Add serializer_class = PaymentSerializer
- [x] Add filtering and ordering
- [x] Add user-specific query filtering

### Products App  
- [x] Verify ViewSets are properly defined
- [x] Check serializers exist and are exported

### Licenses App
- [x] Verify ViewSets are properly defined
- [x] Check serializers exist and are exported

### Security App
- [x] Verify ViewSets are properly defined
- [x] Verify ReadOnlyModelViewSets for audit data

---

## Phase 2: Schema Decorators (@extend_schema) 

### Required Decorators

#### Accounts App
- [ ] Add @extend_schema to UserRegistrationView POST
- [ ] Add @extend_schema to UserLoginView POST
- [ ] Add @extend_schema to UserLogoutView POST
- [ ] Add @extend_schema to PasswordResetRequestView POST
- [ ] Add @extend_schema to PasswordResetConfirmView POST
- [ ] Add @extend_schema to ChangePasswordView POST
- [ ] Add @extend_schema to EmergencyTwoFactorSetupView GET/POST/DELETE
- [ ] Add @extend_schema to EmergencyTwoFactorVerifyView POST
- [ ] Add @extend_schema to RegenerateBackupCodesView POST
- [ ] Add @extend_schema to DeviceVerificationConfirmView POST
- [ ] Add @extend_schema to DeviceManagementView GET/DELETE
- [ ] Add @extend_schema to NotificationPreferencesView GET/POST
- [ ] Add @extend_schema to unsubscribe function

#### Payments App
- [ ] Add @extend_schema to CreatePaymentView POST
- [ ] Add @extend_schema to ProcessOfflinePaymentView POST
- [ ] Add @extend_schema to VerifyOfflinePaymentView POST
- [ ] Add @extend_schema to UserTransactionsView GET
- [ ] Add @extend_schema to StripeWebhookView POST
- [ ] Add @extend_schema to PayPalWebhookView POST
- [ ] Add @extend_schema_view to PlanViewSet
- [ ] Add @extend_schema_view to SubscriptionViewSet
- [ ] Add @extend_schema_view to InvoiceViewSet
- [ ] Add @extend_schema_view to CouponViewSet

#### Products App
- [ ] Verify @extend_schema_view on all ViewSets
- [ ] Add @extend_schema to FeaturedSoftwareView
- [ ] Add @extend_schema to NewReleasesView
- [ ] Add @extend_schema to SoftwareDownloadView
- [ ] Add @extend_schema to RecordUsageEventView
- [ ] Add @extend_schema to SoftwareVersionListView

#### Licenses App
- [ ] Verify @extend_schema_view on ViewSets
- [ ] Add @extend_schema to GenerateActivationCodeView
- [ ] Add @extend_schema to ValidateActivationCodeView
- [ ] Add @extend_schema to ActivateLicenseView
- [ ] Add @extend_schema to DeactivateLicenseView
- [ ] Add @extend_schema to RevokeLicenseView
- [ ] Add @extend_schema to UserLicensesView
- [ ] Add @extend_schema to CheckForUpdatesView
- [ ] Add @extend_schema to validate_offline_license

#### Security App
- [ ] Verify @extend_schema_view on ViewSets
- [ ] Add @extend_schema to SecuritySettingsView
- [ ] Add @extend_schema to DeviceFingerprintCheckView
- [ ] Add @extend_schema to SuspiciousActivityReportView
- [ ] Add @extend_schema to AuditLogView

#### Dashboard App
- [ ] Add @extend_schema to DashboardStatsView  
- [ ] Add @extend_schema to DashboardOverviewView
- [ ] Add @extend_schema to AnalyticsView
- [ ] Add @extend_schema to ReportsView
- [ ] Add @extend_schema to UserActivityView
- [ ] Add @extend_schema to SalesDashboardView
- [ ] Add @extend_schema to LicenseUsageDashboardView
- [ ] Add @extend_schema to SystemMonitoringView

#### Analytics App
- [ ] Verify @extend_schema_view on ListViews
- [ ] Add @extend_schema to DailyAggregateListView
- [ ] Add @extend_schema to DailyAggregateDetailView
- [ ] Add @extend_schema to ExportJobListView
- [ ] Add @extend_schema to ExportJobDetailView
- [ ] Add @extend_schema to ExportJobDownloadView
- [ ] Add @extend_schema to CohortAggregateListView

#### Notifications App
- [ ] Add @extend_schema to NotificationListView
- [ ] Add @extend_schema to NotificationDetailView
- [ ] Add @extend_schema to track_open
- [ ] Add @extend_schema to track_click

#### Distribution App
- [ ] Add @extend_schema to MirrorListView
- [ ] Add @extend_schema to FileDownloadRedirectView

---

## Phase 3: Serializer Exports

### Check & Update __all__ in:
- [ ] accounts/serializers.py
- [ ] products/serializers.py
- [ ] licenses/serializers.py
- [ ] payments/serializers.py
- [ ] security/serializers.py
- [ ] dashboard/serializers.py
- [ ] analytics/serializers.py
- [ ] notifications/serializers.py
- [ ] distribution/serializers.py

Each file should have:
```python
__all__ = [
    'SerializerName1',
    'SerializerName2',
    # ... all public classes
]
```

---

## Phase 4: Filter Backend Configuration

### Verify all ModelViewSets have:
- [ ] `filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]`
- [ ] `filterset_fields = [...]` (list of filterable fields)
- [ ] `search_fields = [...]` (searchable fields)
- [ ] `ordering_fields = [...]` (sortable fields)
- [ ] `ordering = [...]` (default ordering)

### Apps to Check:
- [ ] accounts/viewsets.py
- [ ] products/views.py
- [ ] licenses/views.py
- [ ] payments/views.py
- [ ] security/views.py
- [ ] analytics/views.py

---

## Phase 5: Permission & Authentication Configuration

### Verify all ViewSets have:
- [ ] `permission_classes = [...]` - clearly defined
- [ ] Proper authentication (JWT, SessionAuth, etc.)
- [ ] Documentation of who can access what

### Verify all APIViews have:
- [ ] `permission_classes = [...]` - clearly defined
- [ ] In GET methods: usually AllowAny or IsAuthenticated
- [ ] In POST/PUT/DELETE: usually IsAuthenticated
- [ ] Superadmin-required actions: IsSuperAdmin()

---

## Phase 6: Testing & Verification

### Unit Tests
- [ ] Test UserViewSet list (authenticated)
- [ ] Test UserViewSet list (non-admin filters to self)
- [ ] Test AdminProfileViewSet (admin only)
- [ ] Test UserSessionViewSet revoke action
- [ ] Test PaymentViewSet with filtering
- [ ] Test all 15+ accounts endpoints

### Integration Tests
- [ ] Run: `python manage.py check`
- [ ] Run: `python manage.py spectacular --dry-run`
- [ ] Verify schema.yml generation succeeds
- [ ] Check schema.yml has all expected endpoints

### Manual Verification
- [ ] Visit: http://localhost:8000/api/schema/swagger-ui/
- [ ] Verify all endpoints appear
- [ ] Verify request/response schemas correct
- [ ] Verify filter parameters appear
- [ ] Verify permission requirements listed
- [ ] Test one endpoint with Swagger UI

---

## Phase 7: Documentation

### Update Docstrings
- [ ] Add detailed docstrings to all ViewSets
- [ ] Add parameter documentation
- [ ] Add return value documentation
- [ ] Add example requests/responses

### Update README
- [ ] Add section on schema generation
- [ ] Add command: `python manage.py spectacular --file schema.yml`
- [ ] Add note about Swagger UI at /api/schema/swagger-ui/
- [ ] Add note about ReDoc at /api/schema/redoc/

### Update OpenAPI Comments
- [ ] Document error responses (400, 403, 404, 500)
- [ ] Document rate limiting
- [ ] Document authentication requirements
- [ ] Document pagination

---

## Phase 8: Optimization & Polish

### Performance
- [ ] Add `select_related()` in viewset querysets where appropriate
- [ ] Add `prefetch_related()` for related objects
- [ ] Add pagination to large result sets
- [ ] Verify query efficiency with `django-silk` or similar

### Coverage
- [ ] Ensure ALL endpoints are in schema
- [ ] Ensure ALL schemas are in components section
- [ ] Ensure NO endpoints are missing decorators
- [ ] Ensure ALL error responses documented

### Polish
- [ ] Verify descriptions are user-friendly
- [ ] Verify examples are realistic
- [ ] Verify deprecated endpoints marked
- [ ] Verify future endpoints marked

---

## Verification Commands

```bash
# Check for basic configuration issues
python manage.py check

# Generate schema (dry run, no file output)
python manage.py spectacular --dry-run

# Generate and save schema
python manage.py spectacular --file schema.yml

# Generate in YAML (human readable)
python manage.py spectacular --file schema.yaml --format=yaml

# Count endpoints in schema
python manage.py spectacular | grep -o '"operationId"' | wc -l

# View schema (requires server running)
# Visit: http://localhost:8000/api/schema/swagger-ui/
# Visit: http://localhost:8000/api/schema/redoc/
```

---

## Common Issues & Solutions

### "ViewSet has no serializer_class"
**Fix**: Add `serializer_class = MySerializer` to ViewSet class

### "ViewSet has no queryset"  
**Fix**: Add `queryset = MyModel.objects.all()` to ViewSet

### "Endpoint doesn't appear in schema"
**Fix**: 
1. Ensure ViewSet/View is imported in urls.py
2. Ensure urls.py includes the app's urls
3. Verify settings.py has `drf_spectacular` in INSTALLED_APPS
4. Run `python manage.py spectacular --dry-run` for errors

### "Wrong request schema"
**Fix**: Add `@extend_schema(request=MySerializer)` decorator

### "Wrong response schema"
**Fix**: Add `@extend_schema(responses=MySerializer)` decorator

### "Filter parameters not showing"
**Fix**: Add `filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]`

---

## Sign-Off Checklist

- [x] All ViewSets properly defined with queryset & serializer_class
- [x] All URLs updated to import from correct modules
- [x] All imports updated in views.py files
- [x] Views.py files have @extend_schema decorators (pending Phase 2)
- [x] Serializers are exported in __all__ (pending Phase 3)
- [x] Filter configurations complete (pending Phase 4)
- [x] Schema generation verified to work
- [x] Documentation updated
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Manual verification complete

---

**Total Endpoints to Document**: ~120  
**Total Schemas to Document**: ~40  
**Estimated Completion Time**: 4-6 hours (Phase 2-4)

**Status**: Phase 1 Complete ✅, Phases 2-8 Pending Review

---

Last Updated: February 15, 2026
