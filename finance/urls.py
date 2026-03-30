from django.urls import path, re_path
from . import views
from . import api_views

app_name = 'finance'

urlpatterns = [
    # Home and authentication
    path('', views.HomeView.as_view(), name='home'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('settings/', views.SettingsView.as_view(), name='settings'),
    path('email-check/', views.EmailCheckView.as_view(), name='email_check'),
    
    # Dashboards
    path('syndic-dashboard/', views.SyndicDashboardView.as_view(), name='syndic_dashboard'),
    path('resident-dashboard/', views.ResidentDashboardView.as_view(), name='resident_dashboard'),
    
    # Resident management (syndic only)
    path('residents/', views.ResidentManagementView.as_view(), name='resident_management'),
    path('residents/create/', views.ResidentCreateView.as_view(), name='resident_create'),
    path('residents/<str:pk>/', views.ResidentDetailView.as_view(), name='resident_detail'),
    path('residents/<str:pk>/edit/', views.ResidentUpdateView.as_view(), name='resident_update'),
    
    # Syndic management (superadmin only)
    path('syndics/', views.SyndicManagementView.as_view(), name='syndic_management'),
    path('syndics/create/', views.SyndicCreateView.as_view(), name='syndic_create'),
    path('syndics/<str:pk>/', views.SyndicDetailView.as_view(), name='syndic_detail'),
    path('syndics/<str:pk>/edit/', views.SyndicUpdateView.as_view(), name='syndic_update'),
    
    # Document management
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/create/', views.DocumentCreateView.as_view(), name='document_create'),
	path('documents/<str:pk>/', views.DocumentDetailView.as_view(), name='document_detail'),
    
    # Payment management
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/<str:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('payments/<str:pk>/edit/', views.PaymentUpdateView.as_view(), name='payment_update'),
    path('payments/<str:pk>/proof/', views.PaymentProofView.as_view(), name='payment_proof'),
	path('payments/create/<str:document_id>/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('api/payments/upload/', views.PaymentUploadAPI.as_view(), name='payment_upload_api'),
    path('api/payments/<str:pk>/verify/', views.PaymentVerificationAPI.as_view(), name='payment_verify_api'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/create/', views.NotificationCreateView.as_view(), name='notification_create'),
	path('notifications/<str:pk>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    
    # Resident reports
    path('reports/', views.ResidentReportListView.as_view(), name='report_list'),
    path('reports/create/', views.ResidentReportCreateView.as_view(), name='report_create'),
	path('reports/management/', views.ReportManagementView.as_view(), name='report_management'),
	re_path(r'^reports/(?P<pk>[0-9a-fA-F]{24})/$', views.ResidentReportDetailView.as_view(), name='report_detail'),
	re_path(r'^reports/(?P<pk>[0-9a-fA-F]{24})/update/$', views.ReportUpdateView.as_view(), name='report_update'),
	re_path(r'^reports/(?P<report_id>[0-9a-fA-F]{24})/comment/$', views.ReportCommentCreateView.as_view(), name='report_comment'),
    
    

    # Calendar
    path('calendar/', views.CalendarListView.as_view(), name='calendar'),
    path('calendar/create/', views.EventCreateView.as_view(), name='event_create'),
    
    # Expense management
    path('depenses/', views.DepenseListView.as_view(), name='depense_list'),
    path('depenses/create/', views.DepenseCreateView.as_view(), name='depense_create'),
    path('depenses/<str:pk>/', views.DepenseDetailView.as_view(), name='depense_detail'),
    path('depenses/<str:pk>/edit/', views.DepenseUpdateView.as_view(), name='depense_update'),
    path('depenses/<str:pk>/delete/', views.DepenseDeleteView.as_view(), name='depense_delete'),
    
    # Overdue payments management
    path('impayes/', views.OverduePaymentsDashboardView.as_view(), name='overdue_dashboard'),
    path('impayes/<str:resident_id>/historique/', views.ResidentPaymentHistoryView.as_view(), name='resident_payment_history'),
    path('impayes/<str:document_id>/rappel/', views.SendReminderView.as_view(), name='send_reminder'),
    path('api/run-overdue-detection/', views.RunOverdueDetectionView.as_view(), name='run_overdue_detection'),
    
    # API endpoints
    path('api/navigation-stats/', api_views.NavigationStatsAPI.as_view(), name='navigation_stats_api'),
    path('api/send-notification/', views.SendNotificationAPI.as_view(), name='send_notification_api'),
]
