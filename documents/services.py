"""Business services for document-domain operations."""

from finance.models import Document


def active_documents_queryset():
    """Return non-archived documents with resident relation selected."""
    return Document.objects.filter(is_archived=False).select_related("resident", "uploaded_by")
