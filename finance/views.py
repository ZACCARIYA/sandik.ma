from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View, TemplateView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth import get_user_model, logout, authenticate, login
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django import forms
from decimal import Decimal
import json

from .models import (
    Document,
    Notification,
    Payment,
    ResidentStatus,
    ResidentReport,
    ReportComment,
    Event,
    Depense,
    Reminder,
    send_sms,
    send_email,
    send_whatsapp,
)
from .services.dashboard_service import build_syndic_dashboard_context

User = get_user_model()


class HomeView(TemplateView):
    """Home page - redirects authenticated users to their dashboard"""
    template_name = 'finance/home.html'

    def get(self, request, *args, **kwargs):
        # Redirect authenticated users to their appropriate dashboard
        if request.user.is_authenticated:
            if request.user.role == 'RESIDENT':
                return redirect('finance:resident_dashboard')
            elif request.user.role in ['SYNDIC', 'SUPERADMIN']:
                return redirect('finance:syndic_dashboard')
        
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add some statistics for the home page
        if self.request.user.is_authenticated:
            try:
                if hasattr(self.request.user, 'role'):
                    context['user_role'] = self.request.user.role
                    context['user_name'] = self.request.user.get_full_name() or self.request.user.username
            except:
                pass
        
        return context


class SyndicDashboardView(TemplateView):
    """Dashboard for syndic - shows residents grouped by status"""
    template_name = 'finance/syndic_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_syndic_dashboard_context(self.request))
        return context


class ResidentDashboardView(TemplateView):
    """Dashboard for residents - shows their own data"""
    template_name = 'finance/resident_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role != 'RESIDENT':
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get or create resident status
        status, created = ResidentStatus.objects.get_or_create(resident=user)
        status.update_totals()
        
        # Get resident's documents
        documents = user.documents.all().order_by('-date')
        show_archived = self.request.GET.get('archived') == '1'
        if not show_archived:
            documents = documents.filter(is_archived=False)
        
        # Get resident's notifications
        notifications = user.received_notifications.filter(is_active=True).order_by('-created_at')[:10]
        
        # Recent payments
        recent_payments = Payment.objects.filter(document__resident=user).order_by('-payment_date')[:5]
        
        # Get resident's reports
        recent_reports = user.resident_reports.all().order_by('-created_at')[:5]
        
        # Get upcoming events for residents
        from django.db.models import Q
        upcoming_events = Event.objects.filter(
            Q(audience='ALL_RESIDENTS') | Q(participants=user)
        ).filter(start_at__gte=timezone.now()).order_by('start_at')[:5]
        
        # Actions de page pour l'en-tête
        from django.urls import reverse_lazy
        page_actions = [
            {
                'label': 'Nouveau Rapport',
                'url': reverse_lazy('finance:report_create'),
                'icon': 'fas fa-plus-circle',
                'type': 'primary'
            },
            {
                'label': 'Mes Documents',
                'url': reverse_lazy('finance:document_list'),
                'icon': 'fas fa-file-alt',
                'type': 'outline'
            },
            {
                'label': 'Mes Notifications',
                'url': reverse_lazy('finance:notification_list'),
                'icon': 'fas fa-bell',
                'type': 'outline'
            }
        ]
        
        context.update({
            'status': status,
            'documents': documents,
            'notifications': notifications,
            'recent_payments': recent_payments,
            'recent_reports': recent_reports,
            'upcoming_events': upcoming_events,
            'page_actions': page_actions,
        })
        return context


class ResidentManagementView(ListView):
    """Manage residents - syndic and superadmin only"""
    model = User
    template_name = 'finance/resident_management.html'
    context_object_name = 'residents'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = User.objects.filter(role='RESIDENT').select_related('created_by', 'status').order_by('username')

        search_query = self.request.GET.get('q', '').strip()
        active_filter = self.request.GET.get('active', 'all').strip()
        apartment_filter = self.request.GET.get('apartment', 'all').strip()

        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone__icontains=search_query) |
                Q(apartment__icontains=search_query)
            )

        if active_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif active_filter == 'inactive':
            queryset = queryset.filter(is_active=False)

        if apartment_filter == 'with':
            queryset = queryset.exclude(apartment__isnull=True).exclude(apartment='')
        elif apartment_filter == 'without':
            queryset = queryset.filter(Q(apartment__isnull=True) | Q(apartment=''))

        return queryset

    def _status_category_from_balance(self, balance):
        if balance <= 0:
            return 'up_to_date'
        if balance <= 100:
            return 'pending'
        if balance <= 500:
            return 'overdue'
        return 'critical'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Ajouter un Résident',
                'url': reverse_lazy('finance:resident_create'),
                'icon': 'fas fa-plus',
                'type': 'primary'
            }
        ]
        
        # Statistiques des résidents
        from django.utils import timezone
        from datetime import timedelta
        
        # Total des résidents
        context['total_residents'] = User.objects.filter(role='RESIDENT').count()
        
        # Résidents avec appartement
        context['residents_with_apartment'] = User.objects.filter(
            role='RESIDENT', 
            apartment__isnull=False
        ).exclude(apartment='').count()
        
        # Nouveaux résidents (30 derniers jours)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        context['recent_residents'] = User.objects.filter(
            role='RESIDENT',
            date_joined__gte=thirty_days_ago
        ).count()
        
        # Résidents actifs
        context['active_residents'] = User.objects.filter(
            role='RESIDENT',
            is_active=True
        ).count()

        filtered_queryset = self.get_queryset()
        page_residents = list(context.get('residents', []))

        status_labels = {
            'up_to_date': 'A jour',
            'pending': 'En attente',
            'overdue': 'En retard',
            'critical': 'Critique',
        }
        status_counts = {
            'up_to_date': 0,
            'pending': 0,
            'overdue': 0,
            'critical': 0,
        }

        filtered_total_due = Decimal('0')
        filtered_total_paid = Decimal('0')
        top_debtors = []

        def resolve_status(resident):
            try:
                return resident.status
            except ResidentStatus.DoesNotExist:
                return None

        for resident in filtered_queryset:
            status_obj = resolve_status(resident)
            due = status_obj.total_due if status_obj else Decimal('0')
            paid = status_obj.total_paid if status_obj else Decimal('0')
            balance = due - paid
            category = self._status_category_from_balance(balance)

            filtered_total_due += due
            filtered_total_paid += paid
            status_counts[category] += 1

            if balance > 0:
                top_debtors.append({
                    'resident': resident,
                    'balance': balance,
                    'category': category,
                })

        for resident in page_residents:
            status_obj = resolve_status(resident)
            due = status_obj.total_due if status_obj else Decimal('0')
            paid = status_obj.total_paid if status_obj else Decimal('0')
            balance = due - paid
            category = self._status_category_from_balance(balance)
            resident.fin_due = due
            resident.fin_paid = paid
            resident.fin_balance = balance
            resident.fin_status = category
            resident.fin_status_label = status_labels[category]

        top_debtors = sorted(top_debtors, key=lambda item: item['balance'], reverse=True)[:6]
        max_debtor_balance = top_debtors[0]['balance'] if top_debtors else Decimal('0')
        if max_debtor_balance > 0:
            for item in top_debtors:
                item['progress'] = float((item['balance'] / max_debtor_balance) * 100)
        else:
            for item in top_debtors:
                item['progress'] = 0.0

        filtered_exposure = filtered_total_due + filtered_total_paid
        filtered_collection_rate = round((filtered_total_paid / filtered_exposure) * 100, 1) if filtered_exposure > 0 else 0
        filtered_balance = filtered_total_due - filtered_total_paid

        query_params = self.request.GET.copy()
        query_params.pop('page', None)

        context['residents'] = page_residents
        context['filtered_count'] = filtered_queryset.count()
        context['filtered_total_due'] = filtered_total_due
        context['filtered_total_paid'] = filtered_total_paid
        context['filtered_balance'] = filtered_balance
        context['filtered_collection_rate'] = filtered_collection_rate
        context['status_breakdown'] = status_counts
        context['status_chart_json'] = json.dumps([
            {'label': 'A jour', 'value': status_counts['up_to_date']},
            {'label': 'En attente', 'value': status_counts['pending']},
            {'label': 'En retard', 'value': status_counts['overdue']},
            {'label': 'Critique', 'value': status_counts['critical']},
        ])
        context['top_debtors'] = top_debtors
        context['querystring'] = query_params.urlencode()
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_active'] = self.request.GET.get('active', 'all').strip()
        context['selected_apartment'] = self.request.GET.get('apartment', 'all').strip()
        
        return context


class ResidentCreateView(CreateView):
    """Create resident - syndic and superadmin only"""
    model = User
    template_name = 'finance/resident_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'apartment', 'address']
    success_url = reverse_lazy('finance:resident_management')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        try:
            user = form.save(commit=False)
            user.role = 'RESIDENT'
            user.is_active = True
            user.created_by = self.request.user  # Track who created this resident
            user.set_password('resident123')  # Default password
            
            # Validate uniqueness before saving
            user.clean()
            user.save()
            
            # Create resident status
            ResidentStatus.objects.create(resident=user)
            
            messages.success(self.request, f"Résident {user.username} créé avec succès. Mot de passe: resident123")
            return super().form_valid(form)
            
        except ValidationError as e:
            # Handle validation errors (like duplicate apartment)
            for field, errors in e.message_dict.items():
                for error in errors:
                    form.add_error(field, error)
            return self.form_invalid(form)
        except IntegrityError:
            form.add_error('apartment', "Un résident existe déjà pour cet appartement.")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour à la liste',
                'url': reverse_lazy('finance:resident_management'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        # Get existing apartments to show in help text
        existing_apartments = User.objects.filter(
            role='RESIDENT', 
            apartment__isnull=False
        ).exclude(apartment='').values_list('apartment', flat=True)
        
        context['existing_apartments'] = list(existing_apartments)
        context['creator'] = self.request.user
        
        return context


class ResidentUpdateView(UpdateView):
    """Update resident - syndic and superadmin only"""
    model = User
    template_name = 'finance/resident_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'apartment', 'address', 'is_active']
    success_url = reverse_lazy('finance:resident_management')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(role='RESIDENT')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour à la liste',
                'url': reverse_lazy('finance:resident_management'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        context['creator'] = self.request.user
        
        return context


class SyndicManagementView(ListView):
    """Manage syndics - superadmin only"""
    model = User
    template_name = 'finance/syndic_management.html'
    context_object_name = 'syndics'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role != 'SUPERADMIN':
            messages.error(request, "Accès non autorisé. Seuls les super administrateurs peuvent gérer les syndics.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(role='SYNDIC').order_by('username')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_syndics'] = User.objects.filter(role='SYNDIC').count()
        context['active_syndics'] = User.objects.filter(role='SYNDIC', is_active=True).count()
        return context


class SyndicCreateView(CreateView):
    """Create syndic - superadmin only"""
    model = User
    template_name = 'finance/syndic_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'address']
    success_url = reverse_lazy('finance:syndic_management')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role != 'SUPERADMIN':
            messages.error(request, "Accès non autorisé. Seuls les super administrateurs peuvent créer des syndics.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        user = form.save(commit=False)
        user.role = 'SYNDIC'
        user.is_active = True
        user.set_password('syndic123')  # Default password
        user.save()
        
        messages.success(self.request, f"Syndic {user.username} créé avec succès. Mot de passe: syndic123")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour à la liste',
                'url': reverse_lazy('finance:syndic_management'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        return context


class SyndicUpdateView(UpdateView):
    """Update syndic - superadmin only"""
    model = User
    template_name = 'finance/syndic_form.html'
    fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'address', 'is_active']
    success_url = reverse_lazy('finance:syndic_management')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role != 'SUPERADMIN':
            messages.error(request, "Accès non autorisé. Seuls les super administrateurs peuvent modifier les syndics.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(role='SYNDIC')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour à la liste',
                'url': reverse_lazy('finance:syndic_management'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        return context


class SyndicDetailView(DetailView):
    """View syndic details - superadmin only"""
    model = User
    template_name = 'finance/syndic_detail.html'
    context_object_name = 'syndic'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role != 'SUPERADMIN':
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(role='SYNDIC')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        syndic = self.get_object()
        
        # Get syndic's activity statistics
        context['documents_created'] = Document.objects.filter(uploaded_by=syndic).count()
        context['notifications_sent'] = Notification.objects.filter(sender=syndic).count()
        context['residents_managed'] = User.objects.filter(role='RESIDENT').count()
        
        # Recent activity
        context['recent_documents'] = Document.objects.filter(uploaded_by=syndic).order_by('-created_at')[:5]
        context['recent_notifications'] = Notification.objects.filter(sender=syndic).order_by('-created_at')[:5]
        
        return context


class ResidentDetailView(DetailView):
    """Resident detail - syndic and superadmin only"""
    model = User
    template_name = 'finance/resident_detail.html'
    context_object_name = 'resident'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return User.objects.filter(role='RESIDENT')



class CalendarListView(TemplateView):
    template_name = 'finance/calendar_list.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role in ['SYNDIC', 'SUPERADMIN']:
            events = Event.objects.all().prefetch_related('participants')
        else:
            # resident sees events targeting all residents or specifically included
            events = Event.objects.filter(Q(audience='ALL_RESIDENTS') | Q(participants=self.request.user)).distinct()
        context['events'] = events.order_by('start_at')
        
        # Actions de page pour l'en-tête
        if self.request.user.role in ['SUPERADMIN', 'SYNDIC']:
            context['page_actions'] = [
                {
                    'label': 'Nouvel Événement',
                    'url': reverse_lazy('finance:event_create'),
                    'icon': 'fas fa-plus',
                    'type': 'success'
                }
            ]
        
        return context


class EventCreateView(CreateView):
    model = Event
    template_name = 'finance/event_form.html'
    fields = ['title','description','event_type','start_at','end_at','audience','participants','reminder_minutes_before']
    success_url = reverse_lazy('finance:calendar')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SYNDIC', 'SUPERADMIN']:
            messages.error(request, 'Accès non autorisé.')
            return redirect('finance:calendar')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour au Calendrier',
                'url': reverse_lazy('finance:calendar'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Événement créé avec succès.')
        return super().form_valid(form)


class ResidentReportListView(ListView):
    """List reports. Residents see their own; syndic/superadmin see all."""
    model = ResidentReport
    template_name = 'finance/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = ResidentReport.objects.all()
        
        if self.request.user.role == 'RESIDENT':
            return queryset.filter(resident=self.request.user)
        return queryset.select_related('resident', 'reviewed_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques pour les syndics
        if self.request.user.role in ['SYNDIC', 'SUPERADMIN']:
            context['total_reports'] = ResidentReport.objects.count()
            context['new_reports'] = ResidentReport.objects.filter(status='NEW').count()
            context['in_progress_reports'] = ResidentReport.objects.filter(status='IN_PROGRESS').count()
            context['resolved_reports'] = ResidentReport.objects.filter(status='RESOLVED').count()
        
        return context


class ResidentReportCreateView(CreateView):
    """Create a new resident report (resident only)."""
    model = ResidentReport
    template_name = 'finance/report_form.html'
    fields = ['title', 'description', 'category', 'photo', 'location']
    success_url = reverse_lazy('finance:report_list')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role != 'RESIDENT':
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.resident = self.request.user
        messages.success(self.request, "Votre rapport a été enregistré avec succès.")
        return super().form_valid(form)


class ReportManagementView(ListView):
    """List all reports for syndics and superadmins management."""
    model = ResidentReport
    template_name = 'finance/report_management.html'
    context_object_name = 'reports'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SYNDIC', 'SUPERADMIN']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ResidentReport.objects.all().select_related('resident', 'reviewed_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistiques des rapports
        context['total_reports'] = ResidentReport.objects.count()
        context['new_reports'] = ResidentReport.objects.filter(status='NEW').count()
        context['in_progress_reports'] = ResidentReport.objects.filter(status='IN_PROGRESS').count()
        context['resolved_reports'] = ResidentReport.objects.filter(status='RESOLVED').count()
        context['recent_reports'] = ResidentReport.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
        
        return context


class ReportUpdateView(UpdateView):
    """Update report status and add comments (syndic/superadmin only)."""
    model = ResidentReport
    template_name = 'finance/report_update.html'
    fields = ['status']
    success_url = reverse_lazy('finance:report_management')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SYNDIC', 'SUPERADMIN']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.reviewed_by = self.request.user
        form.instance.reviewed_at = timezone.now()
        messages.success(self.request, f"Statut du rapport mis à jour : {form.instance.get_status_display()}")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comments.filter(is_internal=False).order_by('created_at')
        return context


class ReportCommentCreateView(CreateView):
    """Add comment to a report."""
    model = ReportComment
    template_name = 'finance/report_comment_form.html'
    fields = ['comment', 'is_internal']
    success_url = reverse_lazy('finance:report_management')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.report = get_object_or_404(ResidentReport, pk=self.kwargs['report_id'])
        form.instance.author = self.request.user
        
        # Seuls les syndics peuvent ajouter des commentaires internes
        if form.instance.is_internal and self.request.user.role not in ['SYNDIC', 'SUPERADMIN']:
            form.instance.is_internal = False
        
        messages.success(self.request, "Commentaire ajouté avec succès.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Expose report_id and report to the template for links
        report_id = self.kwargs.get('report_id')
        context['report_id'] = report_id
        if report_id:
            context['report'] = get_object_or_404(ResidentReport, pk=report_id)
        return context

    def get_success_url(self):
        return reverse_lazy('finance:report_detail', kwargs={'pk': self.kwargs['report_id']})


class ResidentReportDetailView(DetailView):
    """Show details of a resident report. Residents can view only their own."""
    model = ResidentReport
    template_name = 'finance/report_detail.html'
    context_object_name = 'report'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = ResidentReport.objects.select_related('resident', 'reviewed_by')
        if self.request.user.role == 'RESIDENT':
            return qs.filter(resident=self.request.user)
        return qs


class DocumentListView(ListView):
    """List documents - filtered by role"""
    model = Document
    template_name = 'finance/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Document.objects.select_related('resident', 'uploaded_by').order_by('-date')
        
        # Filtres pour les syndics
        if self.request.user.role in ['SUPERADMIN', 'SYNDIC']:
            # Filtre par type de document
            document_type = self.request.GET.get('document_type')
            if document_type:
                qs = qs.filter(document_type=document_type)
            
            # Filtre par statut de paiement
            payment_status = self.request.GET.get('payment_status')
            if payment_status == 'paid':
                qs = qs.filter(is_paid=True)
            elif payment_status == 'unpaid':
                qs = qs.filter(is_paid=False)
            elif payment_status == 'overdue':
                from django.utils import timezone
                thirty_days_ago = timezone.now().date() - timezone.timedelta(days=30)
                qs = qs.filter(is_paid=False, date__lt=thirty_days_ago)
            
            # Filtre par dates
            date_start = self.request.GET.get('date_start')
            if date_start:
                qs = qs.filter(date__gte=date_start)
            
            date_end = self.request.GET.get('date_end')
            if date_end:
                qs = qs.filter(date__lte=date_end)
        
        # Filtre archives
        show_archived = self.request.GET.get('archived') == '1'
        if not show_archived:
            qs = qs.filter(is_archived=False)
            
        # Filtre pour les résidents
        if self.request.user.role == 'RESIDENT':
            qs = qs.filter(resident=self.request.user)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_resident_view'] = (self.request.user.role == 'RESIDENT')
        
        # Statistiques pour les syndics
        if self.request.user.role in ['SUPERADMIN', 'SYNDIC']:
            all_docs = Document.objects.filter(is_archived=False)
            context['stats'] = {
                'total': all_docs.count(),
                'paid': all_docs.filter(is_paid=True).count(),
                'unpaid': all_docs.filter(is_paid=False).count(),
                'overdue': sum(1 for doc in all_docs if doc.is_overdue),
                'total_amount': all_docs.aggregate(total=Sum('amount'))['total'] or 0,
                'paid_amount': all_docs.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0,
            }
        
        return context


class DocumentCreateView(CreateView):
    """Create document - syndic and superadmin only"""
    model = Document
    template_name = 'finance/document_form.html'
    fields = ['title', 'file', 'amount', 'date', 'document_type', 'resident', 'description']
    success_url = reverse_lazy('finance:document_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['residents'] = User.objects.filter(role='RESIDENT')
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour à la liste',
                'url': reverse_lazy('finance:document_list'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        return context
    
    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, "Document créé avec succès.")
        return super().form_valid(form)


class DocumentDetailView(DetailView):
    """View document details"""
    model = Document
    template_name = 'finance/document_detail.html'
    context_object_name = 'document'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        
        document = self.get_object()
        # Only the document owner or syndic/admin can view
        if document.resident != request.user and request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        
        return super().dispatch(request, *args, **kwargs)


class NotificationListView(ListView):
    """List notifications - filtered by role"""
    model = Notification
    template_name = 'finance/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Notification.objects.none()

        queryset = (
            Notification.objects
            .select_related('sender')
            .prefetch_related('recipients')
            .filter(is_active=True)
        )

        if self.request.user.role == 'RESIDENT':
            queryset = queryset.filter(recipients=self.request.user)

        search_query = self.request.GET.get('q', '').strip()
        notification_type = self.request.GET.get('notification_type', 'all').strip()
        priority = self.request.GET.get('priority', 'all').strip()
        status = self.request.GET.get('status', 'all').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()

        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(message__icontains=search_query) |
                Q(sender__username__icontains=search_query) |
                Q(sender__first_name__icontains=search_query) |
                Q(sender__last_name__icontains=search_query)
            )

        if notification_type and notification_type != 'all':
            queryset = queryset.filter(notification_type=notification_type)

        if priority and priority != 'all':
            queryset = queryset.filter(priority=priority)

        if status == 'read':
            queryset = queryset.filter(is_read=True)
        elif status == 'unread':
            queryset = queryset.filter(is_read=False)

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_resident_view = (self.request.user.is_authenticated and self.request.user.role == 'RESIDENT')
        notifications_queryset = self.get_queryset()
        today = timezone.now().date()

        total_notifications = notifications_queryset.count()
        unread_notifications = notifications_queryset.filter(is_read=False).count()
        high_priority_notifications = notifications_queryset.filter(priority__in=['HIGH', 'URGENT']).count()
        today_notifications = notifications_queryset.filter(created_at__date=today).count()

        priority_summary = list(
            notifications_queryset
            .values('priority')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        type_summary = list(
            notifications_queryset
            .values('notification_type')
            .annotate(total=Count('id'))
            .order_by('-total')
        )

        priority_map = dict(Notification.PRIORITY_LEVELS)
        type_map = dict(Notification.NOTIFICATION_TYPES)

        priority_chart_data = [
            {
                'label': priority_map.get(item['priority'], item['priority']),
                'value': item['total'],
            }
            for item in priority_summary
        ]
        type_chart_data = [
            {
                'label': type_map.get(item['notification_type'], item['notification_type']),
                'value': item['total'],
            }
            for item in type_summary
        ]

        query_params = self.request.GET.copy()
        query_params.pop('page', None)

        context.update({
            'is_resident_view': is_resident_view,
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'high_priority_notifications': high_priority_notifications,
            'today_notifications': today_notifications,
            'read_rate': round(((total_notifications - unread_notifications) / total_notifications) * 100, 1) if total_notifications else 0,
            'notification_type_choices': Notification.NOTIFICATION_TYPES,
            'priority_choices': Notification.PRIORITY_LEVELS,
            'priority_summary': priority_chart_data,
            'type_summary': type_chart_data,
            'priority_summary_json': json.dumps(priority_chart_data),
            'type_summary_json': json.dumps(type_chart_data),
            'selected_q': self.request.GET.get('q', '').strip(),
            'selected_type': self.request.GET.get('notification_type', 'all').strip(),
            'selected_priority': self.request.GET.get('priority', 'all').strip(),
            'selected_status': self.request.GET.get('status', 'all').strip(),
            'selected_date_from': self.request.GET.get('date_from', '').strip(),
            'selected_date_to': self.request.GET.get('date_to', '').strip(),
            'querystring': query_params.urlencode(),
        })

        if not is_resident_view:
            context['page_actions'] = [
                {
                    'label': 'Nouvelle Notification',
                    'url': reverse_lazy('finance:notification_create'),
                    'icon': 'fas fa-plus',
                    'type': 'primary'
                }
            ]

        return context


class NotificationCreateView(CreateView):
    """Create notification - syndic and superadmin only"""
    model = Notification
    template_name = 'finance/notification_form.html'
    fields = ['title', 'message', 'notification_type', 'priority', 'recipients']
    success_url = reverse_lazy('finance:notification_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour aux Notifications',
                'url': reverse_lazy('finance:notification_list'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        # Liste des résidents pour la sélection
        context['residents'] = User.objects.filter(role='RESIDENT').order_by('first_name', 'last_name')
        
        return context
    
    def get_initial(self):
        initial = super().get_initial()
        # Préremplir le destinataire si resident_id est passé en querystring
        resident_id = self.request.GET.get('resident_id')
        # Ou si un email de résident est passé
        resident_email = self.request.GET.get('email') or self.request.GET.get('resident_email')
        if resident_id:
            try:
                resident = User.objects.get(pk=resident_id, role='RESIDENT')
                # Pour un champ ManyToMany, l'initial accepte une liste de pks
                initial['recipients'] = [resident.pk]
            except User.DoesNotExist:
                pass
        elif resident_email:
            try:
                resident = User.objects.get(email=resident_email, role='RESIDENT')
                initial['recipients'] = [resident.pk]
            except User.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        form.instance.sender = self.request.user
        response = super().form_valid(form)

        # S'assurer que le résident pré-sélectionné est bien ajouté (au cas où le formulaire ne l'a pas gardé)
        resident_id = self.request.GET.get('resident_id') or self.request.POST.get('resident_id')
        resident_email = (
            self.request.GET.get('email') or self.request.GET.get('resident_email') or
            self.request.POST.get('email') or self.request.POST.get('resident_email')
        )
        if resident_id:
            try:
                resident = User.objects.get(pk=resident_id, role='RESIDENT')
                # Si un résident précis est ciblé, on force la liste des destinataires à ce seul résident
                self.object.recipients.set([resident])
            except User.DoesNotExist:
                pass
        elif resident_email:
            try:
                resident = User.objects.get(email=resident_email, role='RESIDENT')
                self.object.recipients.set([resident])
            except User.DoesNotExist:
                pass

        def parse_flag(field_name, default=False):
            raw_value = self.request.POST.get(field_name)
            if raw_value is None:
                return default
            return str(raw_value).lower() in ['on', '1', 'true']

        send_email_enabled = parse_flag('send_email', default=True)
        send_sms_enabled = parse_flag('send_sms', default=False)
        send_whatsapp_enabled = parse_flag('send_whatsapp', default=False)

        dashboard_url = 'http://127.0.0.1:8000/resident-dashboard/'
        try:
            from django.conf import settings
            base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
            dashboard_url = base_url + reverse('finance:resident_dashboard')
        except Exception:
            pass

        direct_message = f"{self.object.title or 'Notification'}\n\n{self.object.message or ''}"
        whatsapp_message = f"{direct_message}\n{dashboard_url}"
        subject = self.object.title or "Notification"

        if send_email_enabled:
            self.object._email_already_sent = True
            try:
                from .emails import send_templated_email
            except ImportError:
                send_templated_email = None

        for user in self.object.recipients.all():
            if send_email_enabled and getattr(user, 'email', None):
                notification_type = getattr(self.object, 'get_notification_type_display', None)
                notification_type = notification_type() if callable(notification_type) else getattr(self.object, 'notification_type', None)
                priority = getattr(self.object, 'get_priority_display', None)
                priority = priority() if callable(priority) else getattr(self.object, 'priority', None)
                amount = getattr(self.object, 'amount', None)
                date_obj = getattr(self.object, 'date', None)
                date_str = date_obj.strftime('%d/%m/%Y') if hasattr(date_obj, 'strftime') else (date_obj or None)
                link = getattr(self.object, 'link', None)

                context = {
                    'subject': subject,
                    'resident_name': (user.get_full_name() or user.username),
                    'notification_type': notification_type,
                    'priority': priority,
                    'amount': amount,
                    'date': date_str,
                    'message': (self.object.message or ''),
                    'intro_text': "Vous avez reçu une nouvelle notification.",
                    'link': link,
                    'dashboard_url': dashboard_url,
                }
                try:
                    if send_templated_email:
                        send_templated_email(
                            subject=subject,
                            to_email=user.email,
                            template_name='emails/notification_generic.html',
                            context=context,
                        )
                    else:
                        send_email(user.email, subject, self.object.message or '')
                    print(f"[NOTIFICATION CREATE] Email envoyé à {user.email} pour notification: {subject}")
                except Exception as e:
                    print(f"[NOTIFICATION CREATE] Erreur envoi email à {user.email}: {e}")
                    import traceback
                    traceback.print_exc()

            if send_sms_enabled and getattr(user, 'phone', None):
                try:
                    send_sms(user.phone, direct_message)
                    print(f"[NOTIFICATION CREATE] SMS mock envoyé à {user.phone}")
                except Exception as e:
                    print(f"[NOTIFICATION CREATE] Erreur SMS pour {user.phone}: {e}")

            if send_whatsapp_enabled and getattr(user, 'phone', None):
                try:
                    send_whatsapp(user.phone, whatsapp_message)
                    print(f"[NOTIFICATION CREATE] WhatsApp mock envoyé à {user.phone}")
                except Exception as e:
                    print(f"[NOTIFICATION CREATE] Erreur WhatsApp pour {user.phone}: {e}")

        messages.success(self.request, "Notification créée avec succès.")
        return response


class NotificationDetailView(DetailView):
    """View a single notification"""
    model = Notification
    template_name = 'finance/notification_detail.html'
    context_object_name = 'notification'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        notification = self.get_object()
        # Residents can only view notifications that include them
        if request.user.role == 'RESIDENT' and request.user not in notification.recipients.all():
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:notification_list')
        return super().dispatch(request, *args, **kwargs)

class PaymentListView(ListView):
    """List payments - filtered by role"""
    model = Payment
    template_name = 'finance/payment_list.html'
    context_object_name = 'object_list'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        qs = Payment.objects.select_related('document__resident', 'verified_by').order_by('-payment_date')
        
        # Filtre pour les résidents - seulement leurs paiements
        if self.request.user.role == 'RESIDENT':
            qs = qs.filter(document__resident=self.request.user)
        
        # Filtres pour les syndics
        if self.request.user.role in ['SUPERADMIN', 'SYNDIC']:
            # Recherche
            search = self.request.GET.get('search')
            if search:
                qs = qs.filter(
                    Q(document__resident__username__icontains=search) |
                    Q(document__resident__first_name__icontains=search) |
                    Q(document__resident__last_name__icontains=search) |
                    Q(reference__icontains=search) |
                    Q(document__title__icontains=search)
                )
            
            # Filtre par méthode de paiement
            payment_method = self.request.GET.get('payment_method')
            if payment_method:
                qs = qs.filter(payment_method=payment_method)
            
            # Filtre par statut
            status = self.request.GET.get('status')
            if status == 'verified':
                qs = qs.filter(is_verified=True)
            elif status == 'pending':
                qs = qs.filter(is_verified=False)
            
            # Filtre par dates
            date_from = self.request.GET.get('date_from')
            if date_from:
                qs = qs.filter(payment_date__gte=date_from)
            
            date_to = self.request.GET.get('date_to')
            if date_to:
                qs = qs.filter(payment_date__lte=date_to)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


class PaymentDetailView(DetailView):
    """View payment details"""
    model = Payment
    template_name = 'finance/payment_detail.html'
    context_object_name = 'payment'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        qs = Payment.objects.select_related('document__resident', 'verified_by')
        if self.request.user.role == 'RESIDENT':
            qs = qs.filter(document__resident=self.request.user)
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object
        resident = payment.document.resident
        
        # Calculer les statistiques du résident
        all_payments = Payment.objects.filter(document__resident=resident)
        context['total_payments'] = all_payments.count()
        context['verified_payments'] = all_payments.filter(is_verified=True).count()
        context['pending_payments'] = all_payments.filter(is_verified=False).count()
        context['total_contributions'] = Document.objects.filter(resident=resident).count()
        
        return context


class PaymentProofView(View):
    """View payment proof image"""
    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        
        # Vérifier les permissions
        if request.user.role == 'RESIDENT' and payment.document.resident != request.user:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:payment_list')
        
        if not payment.payment_proof:
            messages.error(request, "Aucun justificatif disponible.")
            return redirect('finance:payment_detail', pk=pk)
        
        from django.http import FileResponse
        return FileResponse(payment.payment_proof.open(), content_type='image/jpeg')


class PaymentUpdateView(UpdateView):
    """Update payment - syndic and superadmin only"""
    model = Payment
    template_name = 'finance/payment_form.html'
    fields = ['amount', 'payment_method', 'payment_date', 'reference', 'notes', 'is_verified']
    success_url = reverse_lazy('finance:payment_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object
        # Ajouter le document au contexte pour le template
        if payment and payment.document:
            context['document'] = payment.document
            # Préparer le help_text pour le montant
            context['help_text_amount'] = f"Montant du document : {payment.document.amount} DH"
        return context
    
    def form_valid(self, form):
        if form.cleaned_data.get('is_verified') and not self.object.is_verified:
            form.instance.verified_by = self.request.user
            form.instance.verified_at = timezone.now()
        messages.success(self.request, "Paiement modifié avec succès.")
        return super().form_valid(form)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentUploadAPI(View):
    """API endpoint to upload payment proof"""
    def post(self, request):
        try:
            payment_id = request.POST.get('payment_id')
            payment_proof = request.FILES.get('payment_proof')
            
            if not payment_id or not payment_proof:
                return JsonResponse({'success': False, 'error': 'Données manquantes'}, status=400)
            
            payment = get_object_or_404(Payment, pk=payment_id)
            
            # Vérifier les permissions
            if request.user.role == 'RESIDENT' and payment.document.resident != request.user:
                return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
            
            # Valider le type de fichier
            if not payment_proof.content_type.startswith('image/'):
                return JsonResponse({'success': False, 'error': 'Le fichier doit être une image'}, status=400)
            
            # Valider la taille (5MB max)
            if payment_proof.size > 5 * 1024 * 1024:
                return JsonResponse({'success': False, 'error': 'Fichier trop volumineux (max 5MB)'}, status=400)
            
            payment.payment_proof = payment_proof
            payment.save()
            
            return JsonResponse({'success': True, 'message': 'Justificatif uploadé avec succès'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentVerificationAPI(View):
    """API endpoint to verify or reject a payment"""
    def post(self, request, pk):
        try:
            # Vérifier l'authentification
            if not request.user.is_authenticated:
                return JsonResponse({'success': False, 'error': 'Authentification requise'}, status=401)
            
            # Vérifier les permissions (seulement SYNDIC et SUPERADMIN)
            if request.user.role not in ['SYNDIC', 'SUPERADMIN']:
                return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
            
            payment = get_object_or_404(Payment, pk=pk)
            
            # Vérifier si le paiement est déjà vérifié
            if payment.is_verified:
                return JsonResponse({'success': False, 'error': 'Ce paiement est déjà vérifié'}, status=400)
            
            action = request.POST.get('action')  # 'verify' ou 'reject'
            
            if action == 'verify':
                # Valider le paiement
                payment.is_verified = True
                payment.verified_by = request.user
                payment.verified_at = timezone.now()
                payment.save()
                
                # Mettre à jour le statut du document
                total_paid = payment.document.payments.filter(is_verified=True).aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0')
                payment.document.is_paid = total_paid >= payment.document.amount
                payment.document.save()
                
                # Envoyer une notification au résident
                try:
                    Notification.objects.create(
                        title=f"Paiement validé - {payment.document.title}",
                        message=f"Votre paiement de {payment.amount} DH pour le document '{payment.document.title}' a été validé avec succès.",
                        notification_type="PAYMENT_CONFIRMATION",
                        priority="MEDIUM",
                        sender=request.user,
                    ).recipients.add(payment.document.resident)
                except Exception as e:
                    # Ne pas bloquer si la notification échoue
                    pass
                
                return JsonResponse({
                    'success': True,
                    'message': 'Paiement validé avec succès',
                    'is_verified': True,
                    'verified_by': request.user.get_full_name() or request.user.username,
                    'verified_at': payment.verified_at.strftime('%d/%m/%Y %H:%M')
                })
                
            elif action == 'reject':
                # Rejeter le paiement (on peut ajouter un champ rejection_reason si nécessaire)
                rejection_reason = request.POST.get('reason', 'Paiement rejeté par le syndic')
                
                # Envoyer une notification au résident
                try:
                    Notification.objects.create(
                        title=f"Paiement rejeté - {payment.document.title}",
                        message=f"Votre paiement de {payment.amount} DH pour le document '{payment.document.title}' a été rejeté. Raison: {rejection_reason}",
                        notification_type="PAYMENT_REMINDER",
                        priority="HIGH",
                        sender=request.user,
                    ).recipients.add(payment.document.resident)
                except Exception as e:
                    # Ne pas bloquer si la notification échoue
                    pass
                
                return JsonResponse({
                    'success': True,
                    'message': 'Paiement rejeté',
                    'is_verified': False
                })
            else:
                return JsonResponse({'success': False, 'error': 'Action invalide'}, status=400)
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class PaymentCreateView(CreateView):
    """Create payment for a document - residents only"""
    model = Payment
    template_name = 'finance/payment_form.html'
    fields = ['amount', 'payment_method', 'payment_date', 'reference', 'notes', 'payment_proof']
    success_url = reverse_lazy('finance:document_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role != 'RESIDENT':
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name, field in form.fields.items():
            widget = field.widget
            widget_class = widget.__class__.__name__
            if widget_class in ('Select', 'SelectMultiple'):
                widget.attrs['class'] = 'form-select'
            elif widget_class == 'Textarea':
                widget.attrs['class'] = 'form-control'
            elif widget_class == 'ClearableFileInput':
                widget.attrs['class'] = 'form-control'
            else:
                widget.attrs['class'] = 'form-control'
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document_id = self.kwargs.get('document_id')
        document = get_object_or_404(Document, id=document_id, resident=self.request.user)
        context['document'] = document
        context['help_text_amount'] = f"Montant du document : {document.amount} DH"
        return context
    
    def form_valid(self, form):
        document_id = self.kwargs.get('document_id')
        document = get_object_or_404(Document, id=document_id, resident=self.request.user)
        form.instance.document = document
        messages.success(self.request, "Paiement enregistré avec succès. Il sera vérifié par le syndic.")
        return super().form_valid(form)


class CustomLoginView(TemplateView):
    """Custom login view"""
    template_name = 'finance/login.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('finance:home')
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Bienvenue, {user.username} !")
                return redirect('finance:home')
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
        else:
            messages.error(request, "Veuillez remplir tous les champs.")
        
        return self.get(request, *args, **kwargs)


class RegisterView(TemplateView):
    """User registration view for residents"""
    template_name = 'finance/register.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('finance:home')
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        # Create a custom form for User model
        class UserRegistrationForm(forms.ModelForm):
            password1 = forms.CharField(
                label="Mot de passe",
                widget=forms.PasswordInput(attrs={'class': 'form-control'}),
                min_length=8,
                help_text="Minimum 8 caractères"
            )
            password2 = forms.CharField(
                label="Confirmer le mot de passe",
                widget=forms.PasswordInput(attrs={'class': 'form-control'})
            )
            
            class Meta:
                model = User
                fields = ['username', 'email', 'first_name', 'last_name', 'apartment', 'phone']
                widgets = {
                    'username': forms.TextInput(attrs={'class': 'form-control'}),
                    'email': forms.EmailInput(attrs={'class': 'form-control'}),
                    'first_name': forms.TextInput(attrs={'class': 'form-control'}),
                    'last_name': forms.TextInput(attrs={'class': 'form-control'}),
                    'apartment': forms.TextInput(attrs={'class': 'form-control'}),
                    'phone': forms.TextInput(attrs={'class': 'form-control'}),
                }
            
            def clean_password2(self):
                password1 = self.cleaned_data.get("password1")
                password2 = self.cleaned_data.get("password2")
                if password1 and password2 and password1 != password2:
                    raise forms.ValidationError("Les mots de passe ne correspondent pas.")
                return password2
            
            def clean_apartment(self):
                apartment = self.cleaned_data.get('apartment')
                if apartment:
                    # Check if apartment already exists for a resident
                    existing = User.objects.filter(
                        role='RESIDENT',
                        apartment=apartment
                    )
                    if existing.exists():
                        raise forms.ValidationError("Un résident existe déjà pour cet appartement.")
                return apartment
        
        form = UserRegistrationForm(request.POST)
        
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.role = 'RESIDENT'
                user.is_active = True
                user.set_password(form.cleaned_data['password1'])
                
                # Validate before saving
                user.clean()
                user.save()
                
                # Create resident status
                ResidentStatus.objects.create(resident=user)
                
                messages.success(request, f"Compte créé avec succès ! Vous pouvez maintenant vous connecter.")
                return redirect('finance:login')
                
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
            except IntegrityError:
                form.add_error('apartment', "Un résident existe déjà pour cet appartement.")
        
        # If form is invalid, render with errors
        context = self.get_context_data(**kwargs)
        context['form'] = form
        return self.render_to_response(context)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Create form instance for GET request
        if 'form' not in context:
            class UserRegistrationForm(forms.ModelForm):
                password1 = forms.CharField(
                    label="Mot de passe",
                    widget=forms.PasswordInput(attrs={'class': 'form-control'}),
                    min_length=8
                )
                password2 = forms.CharField(
                    label="Confirmer le mot de passe",
                    widget=forms.PasswordInput(attrs={'class': 'form-control'})
                )
                
                class Meta:
                    model = User
                    fields = ['username', 'email', 'first_name', 'last_name', 'apartment', 'phone']
                    widgets = {
                        'username': forms.TextInput(attrs={'class': 'form-control'}),
                        'email': forms.EmailInput(attrs={'class': 'form-control'}),
                        'first_name': forms.TextInput(attrs={'class': 'form-control'}),
                        'last_name': forms.TextInput(attrs={'class': 'form-control'}),
                        'apartment': forms.TextInput(attrs={'class': 'form-control'}),
                        'phone': forms.TextInput(attrs={'class': 'form-control'}),
                    }
            
            context['form'] = UserRegistrationForm()
        
        return context


class CustomLogoutView(TemplateView):
    """Custom logout view"""
    template_name = 'finance/logout.html'
    
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, "Vous avez été déconnecté avec succès.")
        return super().get(request, *args, **kwargs)


@method_decorator(csrf_exempt, name='dispatch')
class SendNotificationAPI(View):
    """API endpoint for sending notifications via SMS/Email"""
    
    def post(self, request):
        if not request.user.is_authenticated or request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        try:
            data = json.loads(request.body)
            notification_id = data.get('notification_id')
            send_sms_enabled = data.get('send_sms', False)
            send_email_enabled = data.get('send_email', False)
            send_whatsapp_enabled = data.get('send_whatsapp', False)
            
            notification = get_object_or_404(Notification, id=notification_id)
            
            results = {
                'sms_sent': 0,
                'email_sent': 0,
                'whatsapp_sent': 0,
                'errors': []
            }
            
            for recipient in notification.recipients.all():
                try:
                    if send_sms_enabled and recipient.phone:
                        send_sms(recipient.phone, f"{notification.title}\n\n{notification.message}")
                        results['sms_sent'] += 1
                    
                    if send_email_enabled and recipient.email:
                        # Utiliser le template HTML pour un email professionnel
                        try:
                            from .emails import send_templated_email
                            from django.urls import reverse
                            from django.conf import settings
                            base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
                            dashboard_url = base_url + reverse('finance:resident_dashboard')
                            
                            context = {
                                'resident_name': recipient.get_full_name() or recipient.username,
                                'message': notification.message,
                                'dashboard_url': dashboard_url,
                                'notification_type': notification.get_notification_type_display() if hasattr(notification, 'get_notification_type_display') else None,
                                'priority': notification.get_priority_display() if hasattr(notification, 'get_priority_display') else None,
                                'amount': getattr(notification, 'amount', None),
                                'date': getattr(notification, 'date', None),
                                'intro_text': "Vous avez reçu une nouvelle notification.",
                            }
                            send_templated_email(
                                subject=notification.title,
                                to_email=recipient.email,
                                template_name='emails/notification_generic.html',
                                context=context,
                            )
                        except Exception:
                            # Fallback vers send_email simple si le template échoue
                            send_email(recipient.email, notification.title, notification.message)
                        results['email_sent'] += 1

                    if send_whatsapp_enabled and recipient.phone:
                        send_whatsapp(recipient.phone, f"{notification.title}\n\n{notification.message}")
                        results['whatsapp_sent'] += 1
                        
                except Exception as e:
                    results['errors'].append(f"Erreur pour {recipient.username}: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'message': f"Notifications envoyées: {results['sms_sent']} SMS, {results['email_sent']} emails, {results['whatsapp_sent']} WhatsApp",
                'results': results
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# ==================== VUES POUR LA GESTION DES DÉPENSES ====================

class DepenseListView(ListView):
    """Liste des dépenses - accès différencié selon le rôle"""
    model = Depense
    template_name = 'finance/depense_list.html'
    context_object_name = 'depenses'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = Depense.objects.all()
        
        # Filtres
        categorie = self.request.GET.get('categorie')
        if categorie:
            queryset = queryset.filter(categorie=categorie)
        
        date_debut = self.request.GET.get('date_debut')
        if date_debut:
            queryset = queryset.filter(date_depense__gte=date_debut)
        
        date_fin = self.request.GET.get('date_fin')
        if date_fin:
            queryset = queryset.filter(date_depense__lte=date_fin)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        context['categories'] = Depense.CATEGORIES
        context['total_depenses'] = queryset.aggregate(total=Sum('montant'))['total'] or 0
        context['can_manage'] = self.request.user.role in ['SUPERADMIN', 'SYNDIC']
        
        # Calcul de la dépense moyenne
        depense_count = queryset.count()
        if depense_count > 0 and context['total_depenses'] > 0:
            context['depense_moyenne'] = context['total_depenses'] / depense_count
        else:
            context['depense_moyenne'] = 0
        
        # Actions de page pour l'en-tête
        if context['can_manage']:
            context['page_actions'] = [
                {
                    'label': 'Nouvelle Dépense',
                    'url': reverse_lazy('finance:depense_create'),
                    'icon': 'fas fa-plus',
                    'type': 'success'
                }
            ]
        
        # Données pour les graphiques
        if self.request.user.role == 'RESIDENT':
            chart_data = self.get_chart_data()
            context['chart_data'] = chart_data
            # Sérialiser en JSON pour JavaScript
            import json
            context['chart_data_json'] = json.dumps(chart_data)
        
        return context
    
    def get_chart_data(self):
        """Données pour les graphiques des résidents"""
        # Répartition par catégorie
        categories_data = (
            Depense.objects
            .values('categorie')
            .annotate(total=Sum('montant'))
            .order_by('-total')
        )
        
        # Évolution mensuelle (6 derniers mois)
        from django.utils.dateparse import parse_date
        from datetime import datetime, timedelta
        import calendar
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=180)  # 6 mois
        
        monthly_data = {}
        current_date = start_date
        while current_date <= end_date:
            month_key = f"{current_date.year}-{current_date.month:02d}"
            month_name = f"{calendar.month_name[current_date.month][:3]} {current_date.year}"
            monthly_data[month_name] = 0
            current_date = current_date.replace(day=1)
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        monthly_expenses = (
            Depense.objects
            .filter(date_depense__gte=start_date, date_depense__lte=end_date)
            .extra({'month': "strftime('%%Y-%%m', date_depense)"})
            .values('month')
            .annotate(total=Sum('montant'))
        )
        
        for expense in monthly_expenses:
            year, month = expense['month'].split('-')
            month_name = f"{calendar.month_name[int(month)][:3]} {year}"
            if month_name in monthly_data:
                monthly_data[month_name] = float(expense['total'])
        
        return {
            'categories': [
                {
                    'categorie': dict(Depense.CATEGORIES).get(item['categorie'], item['categorie']),
                    'montant': float(item['total'])
                }
                for item in categories_data
            ],
            'monthly': [
                {'month': month, 'total': total}
                for month, total in monthly_data.items()
            ]
        }


class DepenseCreateView(CreateView):
    """Créer une nouvelle dépense - syndics seulement"""
    model = Depense
    template_name = 'finance/depense_form.html'
    fields = ['titre', 'description', 'montant', 'categorie', 'date_depense']
    success_url = reverse_lazy('finance:depense_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:depense_list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        form.instance.ajoute_par = self.request.user
        messages.success(self.request, "Dépense ajoutée avec succès.")
        return super().form_valid(form)


class DepenseUpdateView(UpdateView):
    """Modifier une dépense - syndics seulement"""
    model = Depense
    template_name = 'finance/depense_form.html'
    fields = ['titre', 'description', 'montant', 'categorie', 'date_depense']
    success_url = reverse_lazy('finance:depense_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:depense_list')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, "Dépense modifiée avec succès.")
        return super().form_valid(form)


class DepenseDetailView(DetailView):
    """Détails d'une dépense"""
    model = Depense
    template_name = 'finance/depense_detail.html'
    context_object_name = 'depense'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)


class DepenseDeleteView(View):
    """Supprimer une dépense - syndics seulement"""
    
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:depense_list')
        
        depense = get_object_or_404(Depense, pk=pk)
        depense.delete()
        messages.success(request, "Dépense supprimée avec succès.")
        return redirect('finance:depense_list')


# ==================== SYSTÈME DE DÉTECTION DES IMPAYÉS ====================

class OverduePaymentsDashboardView(TemplateView):
    """Tableau de bord des impayés - syndics seulement"""
    template_name = 'finance/overdue_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        unpaid_docs = Document.objects.filter(
            is_paid=False, is_archived=False
        ).select_related('resident')
        
        # Group by resident
        residents_data = {}
        total_overdue_amount = Decimal('0')
        total_partially_paid = 0
        total_overdue = 0
        total_critical = 0
        
        for doc in unpaid_docs:
            rid = doc.resident_id
            if rid not in residents_data:
                residents_data[rid] = {
                    'resident': doc.resident,
                    'documents': [],
                    'total_due': Decimal('0'),
                    'total_paid': Decimal('0'),
                    'max_days_overdue': 0,
                    'unpaid_count': 0,
                }
            
            paid_amount = doc.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            residents_data[rid]['documents'].append(doc)
            residents_data[rid]['total_due'] += doc.amount
            residents_data[rid]['total_paid'] += paid_amount
            residents_data[rid]['unpaid_count'] += 1
            residents_data[rid]['max_days_overdue'] = max(
                residents_data[rid]['max_days_overdue'], doc.days_overdue
            )
            
            total_overdue_amount += doc.amount - paid_amount
            
            if paid_amount > 0 and paid_amount < doc.amount:
                total_partially_paid += 1
            if doc.days_overdue >= 90:
                total_critical += 1
            elif doc.days_overdue > 0:
                total_overdue += 1
        
        # Compute status and balance for each resident
        residents_list = []
        for rid, data in residents_data.items():
            balance = data['total_due'] - data['total_paid']
            if balance <= 0:
                status = 'paid'
                status_label = 'À jour'
                status_color = 'success'
            elif data['total_paid'] > 0:
                status = 'partial'
                status_label = 'Partiellement payé'
                status_color = 'warning'
            elif data['max_days_overdue'] >= 90:
                status = 'critical'
                status_label = 'Critique'
                status_color = 'danger'
            elif data['max_days_overdue'] >= 30:
                status = 'overdue'
                status_label = 'En retard'
                status_color = 'danger'
            else:
                status = 'pending'
                status_label = 'En attente'
                status_color = 'warning'
            
            data['balance'] = balance
            data['status'] = status
            data['status_label'] = status_label
            data['status_color'] = status_color
            data['reminders_count'] = Reminder.objects.filter(resident_id=rid).count()
            residents_list.append(data)
        
        # Sort: critical first, then overdue, then partial, then pending
        status_order = {'critical': 0, 'overdue': 1, 'partial': 2, 'pending': 3, 'paid': 4}
        residents_list.sort(key=lambda r: (status_order.get(r['status'], 5), -r['balance']))
        
        # Recent reminders
        recent_reminders = Reminder.objects.select_related(
            'document', 'resident', 'created_by'
        ).order_by('-created_at')[:10]
        
        context.update({
            'residents': residents_list,
            'total_overdue_amount': total_overdue_amount,
            'recent_reminders': recent_reminders,
            'stats': {
                'total_unpaid_residents': len(residents_list),
                'total_overdue': total_overdue,
                'total_critical': total_critical,
                'total_partially_paid': total_partially_paid,
                'total_reminders_sent': Reminder.objects.filter(status='SENT').count(),
            }
        })
        return context


class ResidentPaymentHistoryView(TemplateView):
    """Per-resident payment and reminder history."""
    template_name = 'finance/resident_payment_history.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('finance:login')
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            messages.error(request, "Accès non autorisé.")
            return redirect('finance:home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resident = get_object_or_404(User, pk=self.kwargs['resident_id'], role='RESIDENT')
        
        documents = Document.objects.filter(
            resident=resident, is_archived=False
        ).order_by('-date')
        
        # Enrich documents with payment info
        docs_data = []
        total_due = Decimal('0')
        total_paid_all = Decimal('0')
        for doc in documents:
            paid = doc.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            balance = doc.amount - paid
            if doc.is_paid:
                status = 'paid'
                status_label = 'Payé'
                status_color = 'success'
            elif paid > 0:
                status = 'partial'
                status_label = 'Partiellement payé'
                status_color = 'warning'
            elif doc.is_overdue:
                status = 'overdue'
                status_label = f'En retard ({doc.days_overdue}j)'
                status_color = 'danger'
            else:
                status = 'pending'
                status_label = 'En attente'
                status_color = 'info'
            
            docs_data.append({
                'document': doc,
                'paid_amount': paid,
                'balance': balance,
                'status': status,
                'status_label': status_label,
                'status_color': status_color,
                'payments': doc.payments.all().order_by('-payment_date'),
            })
            total_due += doc.amount
            total_paid_all += paid
        
        reminders = Reminder.objects.filter(
            resident=resident
        ).select_related('document', 'created_by').order_by('-created_at')
        
        context.update({
            'resident': resident,
            'docs_data': docs_data,
            'reminders': reminders,
            'total_due': total_due,
            'total_paid': total_paid_all,
            'balance': total_due - total_paid_all,
        })
        return context


class SendReminderView(View):
    """Send a payment reminder to a resident for an overdue document."""
    
    def post(self, request, document_id):
        if not request.user.is_authenticated or request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            return JsonResponse({'error': 'Non autorisé'}, status=403)
        
        doc = get_object_or_404(Document, pk=document_id)
        reminder_type = request.POST.get('reminder_type', 'EMAIL')
        
        # Build reminder message
        message = doc.get_reminder_message(for_syndic=False)
        
        reminder = Reminder.objects.create(
            document=doc,
            resident=doc.resident,
            reminder_type=reminder_type,
            message=message,
            created_by=request.user,
        )
        
        # Attempt to send email
        if reminder_type == 'EMAIL' and doc.resident.email:
            success = send_email(
                recipient_email=doc.resident.email,
                subject=f"Rappel de paiement - {doc.title}",
                message=message,
            )
            if success:
                reminder.mark_sent()
                messages.success(request, f"Rappel envoyé par email à {doc.resident.email}")
            else:
                reminder.mark_failed()
                messages.warning(request, "Échec de l'envoi de l'email. Le rappel a été enregistré.")
        elif reminder_type == 'PDF':
            # Generate a simple text-based PDF
            try:
                from io import BytesIO
                from django.template.loader import render_to_string
                
                pdf_content = render_to_string('finance/reminder_pdf.html', {
                    'document': doc,
                    'resident': doc.resident,
                    'message': message,
                    'date': timezone.now(),
                })
                
                filename = f"rappel_{doc.pk}_{doc.resident.username}_{timezone.now().strftime('%Y%m%d')}.html"
                reminder.pdf_file.save(filename, ContentFile(pdf_content.encode('utf-8')))
                reminder.mark_sent()
                messages.success(request, "Rappel PDF généré avec succès.")
            except Exception as e:
                reminder.mark_failed()
                messages.warning(request, f"Erreur lors de la génération du PDF: {e}")
        else:
            reminder.mark_sent()
            messages.success(request, "Rappel enregistré.")
        
        # Redirect back to appropriate page
        next_url = request.POST.get('next', '')
        if next_url:
            return redirect(next_url)
        return redirect('finance:overdue_dashboard')


class RunOverdueDetectionView(View):
    """Exécuter manuellement la détection des impayés"""
    
    def post(self, request):
        if not request.user.is_authenticated or request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        try:
            # Importer et exécuter la commande
            from django.core.management import call_command
            from io import StringIO
            
            output = StringIO()
            call_command('detect_overdue_payments', stdout=output)
            
            messages.success(request, "Détection des impayés exécutée avec succès.")
            return JsonResponse({
                'success': True,
                'message': 'Détection terminée',
                'output': output.getvalue()
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class UserProfileView(TemplateView):
    """User profile page - authenticated users only"""
    template_name = 'finance/user_profile.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Veuillez vous connecter pour accéder à votre profil.")
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Actions de page pour l'en-tête
        context['page_actions'] = [
            {
                'label': 'Retour au tableau de bord',
                'url': reverse_lazy('finance:home'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        
        # Informations de l'utilisateur
        context['user_info'] = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': getattr(user, 'phone', ''),
            'apartment': getattr(user, 'apartment', ''),
            'address': getattr(user, 'address', ''),
            'role': user.role,
            'is_active': user.is_active,
            'date_joined': user.date_joined,
            'last_login': user.last_login,
        }
        
        # Statistiques selon le rôle
        if user.role in ['SYNDIC', 'SUPERADMIN']:
            context['stats'] = {
                'total_residents': User.objects.filter(role='RESIDENT').count(),
                'total_documents': Document.objects.count(),
                'total_expenses': Depense.objects.count(),
                'unread_notifications': Notification.objects.filter(
                    recipients=user, 
                    is_read=False
                ).count(),
            }
        elif user.role == 'RESIDENT':
            context['stats'] = {
                'my_documents': Document.objects.filter(resident=user).count(),
                'my_payments': Payment.objects.filter(document__resident=user).count(),
                'my_notifications': Notification.objects.filter(
                    recipients=user
                ).count(),
                'unread_notifications': Notification.objects.filter(
                    recipients=user, 
                    is_read=False
                ).count(),
            }
        
        return context

class SettingsView(View):
    """User settings page - edit profile, change password, preferences."""
    template_name = 'finance/settings.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Veuillez vous connecter.")
            return redirect('finance:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        user = request.user
        context = {
            'user_info': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': getattr(user, 'phone', ''),
                'apartment': getattr(user, 'apartment', ''),
                'address': getattr(user, 'address', ''),
                'role': user.role,
            }
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        user = request.user
        action = request.POST.get('action', 'update_profile')
        
        if action == 'update_profile':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.phone = request.POST.get('phone', '').strip()
            user.address = request.POST.get('address', '').strip()
            
            try:
                user.save()
                messages.success(request, "Profil mis à jour avec succès.")
            except Exception as e:
                messages.error(request, f"Erreur lors de la mise à jour : {e}")
        
        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            if not user.check_password(current_password):
                messages.error(request, "Le mot de passe actuel est incorrect.")
            elif len(new_password) < 6:
                messages.error(request, "Le nouveau mot de passe doit contenir au moins 6 caractères.")
            elif new_password != confirm_password:
                messages.error(request, "Les mots de passe ne correspondent pas.")
            else:
                user.set_password(new_password)
                user.save()
                login(request, user)
                messages.success(request, "Mot de passe modifié avec succès.")
        
        return redirect('finance:settings')
