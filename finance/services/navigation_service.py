"""Service layer for navigation/stat cards API payloads."""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from accounts.models import User
from finance.models import Depense, Document, Notification, Payment, ResidentReport
from finance.serializers import NavigationStatsSerializer


def build_navigation_stats(user):
    """Return high-level counters used by dashboard navigation widgets."""
    today = timezone.now().date()
    current_month = today.replace(day=1)
    overdue_cutoff = today - timedelta(days=30)

    total_residents = User.objects.filter(role="RESIDENT").count()
    total_documents = Document.objects.filter(is_archived=False).count()
    total_expenses = Depense.objects.count()

    overdue_count = Document.objects.filter(
        is_paid=False,
        is_archived=False,
        date__lt=overdue_cutoff,
    ).count()

    unread_notifications = Notification.objects.filter(
        is_read=False,
        is_active=True,
        recipients=user,
    ).count()

    issue_reports = ResidentReport.objects.filter(status="NEW").count()

    documents_this_month = Document.objects.filter(
        created_at__date__gte=current_month,
        is_archived=False,
    ).count()

    payments_this_month = (
        Payment.objects.filter(payment_date__gte=current_month).aggregate(total=Sum("amount"))["total"] or 0
    )
    expenses_this_month = (
        Depense.objects.filter(date_depense__gte=current_month).aggregate(total=Sum("montant"))["total"] or 0
    )

    recent_residents = User.objects.filter(
        role="RESIDENT",
        date_joined__date__gte=current_month,
    ).count()

    payload = NavigationStatsSerializer(
        total_residents=total_residents,
        total_documents=total_documents,
        total_expenses=total_expenses,
        overdue_count=overdue_count,
        unread_notifications=unread_notifications,
        issue_reports=issue_reports,
        documents_this_month=documents_this_month,
        payments_this_month=float(payments_this_month),
        expenses_this_month=float(expenses_this_month),
        recent_residents=recent_residents,
        timestamp=timezone.now().isoformat(),
    )
    return payload.to_dict()
