"""
URL Configuration for Tickets app.
"""

from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    # Ticket listing and creation
    path(
        '',
        views.TicketListView.as_view(),
        name='list'
    ),
    path(
        'create/',
        views.TicketCreateView.as_view(),
        name='create'
    ),
    
    # Ticket detail and management
    path(
        '<int:pk>/',
        views.TicketDetailView.as_view(),
        name='detail'
    ),
    path(
        '<int:pk>/update-status/',
        views.TicketUpdateStatusView.as_view(),
        name='update_status'
    ),
    path(
        '<int:pk>/assign/',
        views.TicketAssignView.as_view(),
        name='assign'
    ),
    
    # Messages and attachments
    path(
        '<int:ticket_pk>/message/',
        views.TicketMessageCreateView.as_view(),
        name='add_message'
    ),
    path(
        '<int:ticket_pk>/upload/',
        views.TicketAttachmentUploadView.as_view(),
        name='upload_attachment'
    ),
    
    # Dashboard
    path(
        'dashboard/',
        views.TicketDashboardView.as_view(),
        name='dashboard'
    ),
]
