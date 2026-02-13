# FILE: /backend/apps/products/filters.py
"""
Django FilterSet for Software model.
Provides clean, declarative filtering for the Software API.
All changes are backward‑compatible and non‑disruptive.
"""
import django_filters
from .models import Software


class SoftwareFilter(django_filters.FilterSet):
    """
    Dedicated FilterSet for Software model.

    Moves all manual filtering logic out of the view for better testability,
    OpenAPI documentation, and separation of concerns.

    ⚠️ Performance & Correctness Notes:
    - The `os` filter uses `icontains` on `versions__supported_os` (a JSON list).
      This requires a JOIN and will cause duplicate rows in the queryset unless
      `.distinct()` is applied. The view must (and does) call `.distinct()`.
    - For large datasets, consider normalizing `supported_os` into a ManyToMany
      relation or a Postgres ArrayField with GIN index for efficient `overlap`
      lookups. This filter is a placeholder that works but may become a bottleneck.
    - Price filters rely on `base_price`; ensure a database index exists on this
      field for range‑scan performance.
    """
    min_price = django_filters.NumberFilter(
        field_name="base_price",
        lookup_expr='gte'
    )
    max_price = django_filters.NumberFilter(
        field_name="base_price",
        lookup_expr='lte'
    )
    os = django_filters.CharFilter(
        field_name="versions__supported_os",
        lookup_expr='icontains',          # case‑insensitive, more user‑friendly
        help_text="Filter by operating system (e.g., 'windows', 'linux', 'macos')"
    )
    category = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr='exact',
        help_text="Category slug"
    )

    class Meta:
        model = Software
        fields = [
            'category',
            'is_active',
            'is_featured',
            'is_new',
            'license_type',
            'has_trial',
            'min_price',
            'max_price',
            'os',
        ]

    def filter_queryset(self, queryset):
        """
        Ensure the filtered queryset is distinct, eliminating duplicates
        introduced by the `versions` JOIN. This makes the filter self‑contained
        and safe even if the view forgets to call `.distinct()`.
        """
        queryset = super().filter_queryset(queryset)
        return queryset.distinct()