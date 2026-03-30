"""Business logic for syndic dashboard analytics."""

from datetime import datetime, timedelta, time
import json
from decimal import Decimal

from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from finance.models import Depense, Document, Notification, Payment, ResidentReport, ResidentStatus


def parse_date(value):
    """Parse a YYYY-MM-DD string into a date object."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def shift_month(base_date, months_back):
    """Return first day of month shifted by N months."""
    year = base_date.year
    month = base_date.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return base_date.replace(year=year, month=month, day=1)


def compute_delta(current_value, previous_value):
    """Compute percentage delta between current and previous values."""
    if previous_value:
        return round(((current_value - previous_value) / previous_value) * 100, 1)
    if current_value:
        return 100.0
    return 0.0


def status_category_from_balance(balance):
    """Map a resident balance to semantic status category."""
    if balance <= 0:
        return "up_to_date"
    if balance <= 100:
        return "pending"
    if balance <= 500:
        return "overdue"
    return "critical"


def build_syndic_dashboard_context(request):
    """Build all dashboard KPIs, charts, and operational insights."""
    tz = timezone.get_current_timezone()
    today = timezone.now().date()
    period = request.GET.get("period", "6m")
    resident_filter = request.GET.get("resident", "").strip()
    status_filter = request.GET.get("status", "all").strip()
    date_from = parse_date(request.GET.get("from"))
    date_to = parse_date(request.GET.get("to"))

    if not date_to:
        date_to = today

    if period == "30d":
        default_from = today - timedelta(days=30)
        chart_months = 3
    elif period == "90d":
        default_from = today - timedelta(days=90)
        chart_months = 6
    elif period == "12m":
        default_from = today - timedelta(days=365)
        chart_months = 12
    elif period == "all":
        default_from = None
        chart_months = 12
    else:
        default_from = today - timedelta(days=180)
        chart_months = 6

    if not date_from:
        date_from = default_from

    residents = list(User.objects.filter(role="RESIDENT").order_by("first_name", "username"))
    resident_ids = [resident.id for resident in residents]

    if resident_ids:
        existing_status_ids = set(
            ResidentStatus.objects.filter(resident_id__in=resident_ids).values_list("resident_id", flat=True)
        )
        missing_statuses = [ResidentStatus(resident_id=rid) for rid in resident_ids if rid not in existing_status_ids]
        if missing_statuses:
            ResidentStatus.objects.bulk_create(missing_statuses)

    due_totals = {}
    paid_totals = {}
    if resident_ids:
        due_totals = {
            item["resident_id"]: item["total"] or Decimal("0")
            for item in (
                Document.objects.filter(resident_id__in=resident_ids, is_paid=False)
                .values("resident_id")
                .annotate(total=Sum("amount"))
            )
        }
        paid_totals = {
            item["document__resident_id"]: item["total"] or Decimal("0")
            for item in (
                Payment.objects.filter(document__resident_id__in=resident_ids)
                .values("document__resident_id")
                .annotate(total=Sum("amount"))
            )
        }

    status_map = {
        status.resident_id: status
        for status in ResidentStatus.objects.filter(resident_id__in=resident_ids)
    }
    status_updates = []
    now = timezone.now()
    resident_records = []
    for resident in residents:
        due = due_totals.get(resident.id, Decimal("0"))
        paid = paid_totals.get(resident.id, Decimal("0"))
        balance = due - paid
        category = status_category_from_balance(balance)

        resident_status = status_map.get(resident.id)
        if resident_status and (resident_status.total_due != due or resident_status.total_paid != paid):
            resident_status.total_due = due
            resident_status.total_paid = paid
            resident_status.last_updated = now
            status_updates.append(resident_status)

        resident_records.append(
            {
                "resident": resident,
                "category": category,
                "due": due,
                "paid": paid,
                "balance": balance,
            }
        )

    if status_updates:
        ResidentStatus.objects.bulk_update(status_updates, ["total_due", "total_paid", "last_updated"])

    if resident_filter.isdigit():
        resident_records = [r for r in resident_records if str(r["resident"].id) == resident_filter]
    if status_filter in {"up_to_date", "pending", "overdue", "critical"}:
        resident_records = [r for r in resident_records if r["category"] == status_filter]

    up_to_date = [r["resident"] for r in resident_records if r["category"] == "up_to_date"]
    pending = [r["resident"] for r in resident_records if r["category"] == "pending"]
    overdue = [r["resident"] for r in resident_records if r["category"] == "overdue"]
    critical = [r["resident"] for r in resident_records if r["category"] == "critical"]

    total_residents = len(resident_records)
    total_due = sum((r["due"] for r in resident_records), Decimal("0"))
    total_paid = sum((r["paid"] for r in resident_records), Decimal("0"))
    exposure_total = total_due + total_paid
    collection_rate = round((total_paid / exposure_total) * 100, 1) if exposure_total > 0 else 0
    unpaid_rate = round(100 - collection_rate, 1) if exposure_total > 0 else 0

    documents_qs = Document.objects.select_related("resident").filter(is_archived=False)
    payments_qs = Payment.objects.select_related("document__resident")
    expenses_qs = Depense.objects.all()
    reports_qs = ResidentReport.objects.select_related("resident")

    if resident_filter.isdigit():
        documents_qs = documents_qs.filter(resident_id=resident_filter)
        payments_qs = payments_qs.filter(document__resident_id=resident_filter)
        reports_qs = reports_qs.filter(resident_id=resident_filter)

    if date_from:
        start_dt = timezone.make_aware(datetime.combine(date_from, time.min), tz)
        documents_qs = documents_qs.filter(created_at__gte=start_dt)
        reports_qs = reports_qs.filter(created_at__gte=start_dt)
        payments_qs = payments_qs.filter(payment_date__gte=date_from)
        expenses_qs = expenses_qs.filter(date_depense__gte=date_from)

    if date_to:
        end_dt = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min), tz)
        documents_qs = documents_qs.filter(created_at__lt=end_dt)
        reports_qs = reports_qs.filter(created_at__lt=end_dt)
        payments_qs = payments_qs.filter(payment_date__lte=date_to)
        expenses_qs = expenses_qs.filter(date_depense__lte=date_to)

    current_month = today.replace(day=1)
    current_month_start = timezone.make_aware(datetime.combine(current_month, time.min), tz)
    documents_this_month = documents_qs.filter(created_at__gte=current_month_start).count()
    payments_this_month = payments_qs.filter(payment_date__gte=current_month).aggregate(total=Sum("amount"))["total"] or 0
    expenses_this_month = expenses_qs.filter(date_depense__gte=current_month).aggregate(total=Sum("montant"))["total"] or 0

    recent_residents_qs = User.objects.filter(
        role="RESIDENT", date_joined__gte=current_month_start
    )
    if resident_filter.isdigit():
        recent_residents_qs = recent_residents_qs.filter(id=resident_filter)
    recent_residents = recent_residents_qs.count()

    overdue_cutoff = today - timedelta(days=30)
    overdue_count = documents_qs.filter(is_paid=False, date__lt=overdue_cutoff).count()

    unread_notifications = Notification.objects.filter(
        is_read=False,
        is_active=True,
        recipients=request.user,
    ).count()

    recent_documents = documents_qs.order_by("-created_at")[:6]
    recent_payments = payments_qs.order_by("-payment_date")[:6]
    recent_reports = reports_qs.order_by("-created_at")[:8]
    recent_notifications = Notification.objects.filter(is_active=True).order_by("-created_at")[:8]

    notif_type_counts = list(
        Notification.objects.filter(is_active=True)
        .values("notification_type")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )
    notification_categories = [
        {
            "key": item["notification_type"],
            "label": dict(Notification.NOTIFICATION_TYPES).get(item["notification_type"], item["notification_type"]),
            "count": item["total"],
        }
        for item in notif_type_counts
    ]

    monthly_trend = []
    for i in range(chart_months - 1, -1, -1):
        month_start = shift_month(today, i)
        month_end = shift_month(today, i - 1) if i > 0 else (today + timedelta(days=1))

        month_payments = payments_qs.filter(
            payment_date__gte=month_start,
            payment_date__lt=month_end,
        ).aggregate(total=Sum("amount"))["total"] or 0
        month_expenses = expenses_qs.filter(
            date_depense__gte=month_start,
            date_depense__lt=month_end,
        ).aggregate(total=Sum("montant"))["total"] or 0

        monthly_trend.append(
            {
                "month": month_start.strftime("%b %Y"),
                "payments": float(month_payments),
                "expenses": float(month_expenses),
                "net": float(month_payments - month_expenses),
            }
        )

    status_distribution = [
        {"label": "A jour", "value": len(up_to_date), "color": "#22c55e"},
        {"label": "En attente", "value": len(pending), "color": "#3b82f6"},
        {"label": "En retard", "value": len(overdue), "color": "#f59e0b"},
        {"label": "Critique", "value": len(critical), "color": "#ef4444"},
    ]

    top_debtors = []
    for resident_record in sorted(
        [r for r in resident_records if r["balance"] > 0],
        key=lambda x: x["balance"],
        reverse=True,
    )[:5]:
        resident_user = resident_record["resident"]
        top_debtors.append(
            {
				"id": str(resident_user.id),
                "name": resident_user.get_full_name() or resident_user.username,
                "apartment": resident_user.apartment or "",
                "balance": float(resident_record["balance"]),
                "category": resident_record["category"],
            }
        )

    payments_compare_qs = Payment.objects.select_related("document__resident")
    expenses_compare_qs = Depense.objects.all()
    if resident_filter.isdigit():
        payments_compare_qs = payments_compare_qs.filter(document__resident_id=resident_filter)

    this_month_start = today.replace(day=1)
    prev_month_start = shift_month(today, 1)
    if this_month_start.month == 12:
        this_month_end = this_month_start.replace(year=this_month_start.year + 1, month=1, day=1)
    else:
        this_month_end = this_month_start.replace(month=this_month_start.month + 1, day=1)
    prev_month_end = this_month_start

    this_month_payments_total = payments_compare_qs.filter(
        payment_date__gte=this_month_start,
        payment_date__lt=this_month_end,
    ).aggregate(total=Sum("amount"))["total"] or 0
    prev_month_payments_total = payments_compare_qs.filter(
        payment_date__gte=prev_month_start,
        payment_date__lt=prev_month_end,
    ).aggregate(total=Sum("amount"))["total"] or 0

    this_month_expenses_total = expenses_compare_qs.filter(
        date_depense__gte=this_month_start,
        date_depense__lt=this_month_end,
    ).aggregate(total=Sum("montant"))["total"] or 0
    prev_month_expenses_total = expenses_compare_qs.filter(
        date_depense__gte=prev_month_start,
        date_depense__lt=prev_month_end,
    ).aggregate(total=Sum("montant"))["total"] or 0

    payments_growth = compute_delta(float(this_month_payments_total), float(prev_month_payments_total))
    expenses_growth = compute_delta(float(this_month_expenses_total), float(prev_month_expenses_total))
    net_cash_this_month = float(this_month_payments_total - this_month_expenses_total)
    net_margin = round((net_cash_this_month / float(this_month_payments_total)) * 100, 1) if this_month_payments_total else 0

    critical_count = len(critical)
    pending_count = len(pending)
    overdue_residents_count = len(overdue)
    up_to_date_count = len(up_to_date)

    risk_numerator = (critical_count * 100) + (overdue_residents_count * 65) + (pending_count * 30)
    risk_index = round(risk_numerator / max(total_residents, 1), 1) if total_residents else 0
    risk_index = min(100, max(0, risk_index))

    open_reports_count = reports_qs.filter(status__in=["NEW", "IN_PROGRESS"]).count()
    ops_pressure_score = min(100, (overdue_count * 8) + (unread_notifications * 4) + (open_reports_count * 6))
    if ops_pressure_score >= 70:
        ops_pressure_level = "élevée"
    elif ops_pressure_score >= 40:
        ops_pressure_level = "modérée"
    else:
        ops_pressure_level = "maîtrisée"

    if net_cash_this_month > 0:
        cashflow_signal = "positive"
        cashflow_message = "Flux net positif ce mois"
    elif net_cash_this_month < 0:
        cashflow_signal = "negative"
        cashflow_message = "Flux net à surveiller"
    else:
        cashflow_signal = "neutral"
        cashflow_message = "Flux net stable"

    focus_items = []
    if critical_count > 0 or overdue_residents_count > 0:
        focus_items.append(
            {
                "label": "Recouvrement prioritaire",
                "value": f"{critical_count + overdue_residents_count} profil(s) à traiter",
                "tone": "danger",
            }
        )
    if payments_growth < 0:
        focus_items.append(
            {
                "label": "Encaissement en baisse",
                "value": f"{payments_growth}% vs mois précédent",
                "tone": "warning",
            }
        )
    if unread_notifications > 0:
        focus_items.append(
            {
                "label": "Relances en attente",
                "value": f"{unread_notifications} notification(s) non lue(s)",
                "tone": "info",
            }
        )
    if open_reports_count > 0:
        focus_items.append(
            {
                "label": "Tickets ouverts",
                "value": f"{open_reports_count} signalement(s) actif(s)",
                "tone": "warning",
            }
        )
    if not focus_items:
        focus_items.append(
            {
                "label": "Situation stable",
                "value": "Aucun signal critique détecté",
                "tone": "success",
            }
        )

    return {
        "up_to_date": up_to_date,
        "pending": pending,
        "overdue": overdue,
        "critical": critical,
        "total_residents": total_residents,
        "total_due": total_due,
        "total_paid": total_paid,
        "recent_residents": recent_residents,
        "documents_this_month": documents_this_month,
        "payments_this_month": payments_this_month,
        "expenses_this_month": expenses_this_month,
        "overdue_count": overdue_count,
        "unread_notifications": unread_notifications,
        "recent_documents": recent_documents,
        "recent_notifications": recent_notifications,
        "recent_reports": recent_reports,
        "recent_payments": recent_payments,
        "monthly_trend": monthly_trend,
        "collection_rate": collection_rate,
        "unpaid_rate": unpaid_rate,
        "notification_categories": notification_categories,
        "status_distribution": status_distribution,
        "top_debtors": top_debtors,
        "payments_growth": payments_growth,
        "expenses_growth": expenses_growth,
        "net_cash_this_month": net_cash_this_month,
        "net_margin": net_margin,
        "risk_index": risk_index,
        "critical_count": critical_count,
        "pending_count": pending_count,
        "overdue_residents_count": overdue_residents_count,
        "up_to_date_count": up_to_date_count,
        "open_reports_count": open_reports_count,
        "ops_pressure_score": ops_pressure_score,
        "ops_pressure_level": ops_pressure_level,
        "cashflow_signal": cashflow_signal,
        "cashflow_message": cashflow_message,
        "focus_items": focus_items,
        "dashboard_residents": residents,
        "selected_period": period,
        "selected_resident": resident_filter,
        "selected_status": status_filter,
        "selected_from": date_from,
        "selected_to": date_to,
        "document_create_url": reverse("finance:document_create"),
        "depense_create_url": reverse("finance:depense_create"),
        "notification_create_url": reverse("finance:notification_create"),
        "resident_create_url": reverse("finance:resident_create"),
        "overdue_dashboard_url": reverse("finance:overdue_dashboard"),
        "event_create_url": reverse("finance:event_create"),
        "monthly_trend_json": json.dumps(monthly_trend),
        "status_distribution_json": json.dumps(status_distribution),
        "notification_categories_json": json.dumps(notification_categories),
        "top_debtors_json": json.dumps(top_debtors),
    }
