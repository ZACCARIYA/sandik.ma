# SyndicPro SaaS Design System

## 1) Foundations

### Color Palette
- Primary: `#2563EB` (action, links, emphasis)
- Secondary: `#0EA5E9` (supporting actions, accents)
- Success: `#16A34A` (paid, completed, positive)
- Warning: `#D97706` (pending, attention)
- Danger: `#DC2626` (late, critical, destructive)
- Neutral:
  - 0: `#FFFFFF`
  - 50: `#F8FAFC`
  - 100: `#F1F5F9`
  - 200: `#E2E8F0`
  - 500: `#64748B`
  - 800: `#1E293B`
  - 900: `#0F172A`

### Typography
- Font: `Inter`
- Scale:
  - XS `12px`
  - SM `14px`
  - MD `16px`
  - LG `18px`
  - XL `20px`
  - 2XL `24px`
  - 3XL `30px`

### Spacing
- 8px grid system: `4, 8, 12, 16, 20, 24, 32, 40, 48`

### Radius and Shadows
- Radius: `8, 12, 16, 20px`
- Shadows:
  - Small: subtle card lift
  - Medium: interactive hover
  - Large: overlay, modal

## 2) Layout System

- Sidebar:
  - Collapsible
  - Icon + label
  - Active state gradient
- Topbar:
  - Search
  - Notification dropdown
  - Profile dropdown
- Page header:
  - Title + subtitle + optional actions
  - Shared component: `templates/components/page_header.html`
- Content shell:
  - Consistent horizontal padding
  - Reusable card surfaces (`card-modern`)

## 3) Reusable Components

- KPI Cards: `templates/components/stats_card.html`
- Generic Card: `templates/components/card.html`
- Data Table: `templates/components/data_table.html`
- Form Field: `templates/components/form_field.html`
- Quick Action: `templates/components/quick_action.html`
- Resident Status Card: `templates/components/resident_status_card.html`
- Empty States: `.empty-state`
- Loading Skeletons: `.skeleton-line`, `.skeleton-block`
- Status Badges:
  - `.status-paid`
  - `.status-pending`
  - `.status-late`
  - `.status-critical`

## 4) Theme + Accessibility

- Dark mode token mapping via `[data-theme="dark"]`
- High-contrast text tokens for readability
- Reduced motion support via `prefers-reduced-motion`
- Focus ring for controls and form fields

## 5) Page Coverage

- Dashboard: fintech analytics layout + charts + watchlists
- Residents:
  - Management with filtering/search
  - Resident detail as structured profile
- Finance pages:
  - Shared cards/forms/tables style system
- Documents:
  - Unified card surface and status treatment
- Notifications:
  - Inbox/timeline list with severity emphasis
- Reports:
  - Standardized cards, filters, and actions

## 6) Suggested Frontend Architecture (Django)

- `templates/base.html` for shell/layout behavior
- `templates/components/*` for reusable UI primitives
- `static/css/saas-system.css` as design-token + component layer
- Keep page-specific CSS minimal; prefer component classes

## 7) Recommended Libraries

- Charts: `Chart.js`
- Icons: `Font Awesome` (current) or `Lucide`
- Animations: CSS transitions + keyframes (lightweight)
- Optional:
  - `htmx` for incremental interactivity
  - `alpine.js` for small component behavior without React overhead

## 8) Premium SaaS Visual Strategy

- Strong hierarchy with white-space and muted surfaces
- Data-first cards with concise metrics
- Subtle gradients (not decorative-heavy)
- Clear status semantics (paid/pending/late/critical)
- Cohesive motion language (short, purposeful)

## 9) Monetization Opportunities

- Advanced analytics add-on (cashflow forecasting, anomaly alerts)
- Automated reminder workflows (email/SMS tiers)
- Export/reporting pack (scheduled PDF + branded reports)
- Role-based premium modules (owner portal, vendor SLA dashboard)

## 10) Developer Layout

### Folder Layout
- `templates/base.html`: global shell (sidebar, topbar, alerts, theme, toast)
- `templates/components/`: reusable blocks (`page_header`, `stats_card`, `data_table`, etc.)
- `templates/finance/*.html`: page-level templates only
- `static/css/saas-system.css`: global tokens and shared component styles

### Standard Page Skeleton
```django
{% extends 'base.html' %}
{% block title %}Page Title - SyndicPro{% endblock %}
{% block content %}
<div class="container-fluid">
    {% include 'components/page_header.html' with title='...' subtitle='...' icon='fas fa-...' actions=page_actions|default:None %}

    <section class="row g-3 mb-4">
        <!-- stats cards -->
    </section>

    <section class="card-modern">
        <div class="card-body-modern">
            <!-- main content -->
        </div>
    </section>
</div>
{% endblock %}
```

### Implementation Rules
- Put business logic and aggregation in Django views, not templates.
- Keep inline CSS minimal; prefer shared classes from `saas-system.css`.
- Use `page_actions` for header CTAs to stay consistent across pages.
- Preserve filter state in pagination (`querystring` without `page`).
- Use semantic statuses (`paid/pending/late/critical`) everywhere.
