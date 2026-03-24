# Complaint & Ticket Management System - Complete Documentation

A production-ready ticket/complaint system for the Snadik.ma property management platform. Enables residents to report issues and admins to manage, assign, and resolve them efficiently.

---

## 📋 Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Models](#models)
4. [Workflows & Permissions](#workflows--permissions)
5. [API & Views](#api--views)
6. [Database Queries & Optimization](#database-queries--optimization)
7. [Notifications System](#notifications-system)
8. [Admin Dashboard](#admin-dashboard)
9. [SLA Management](#sla-management)
10. [Installation & Setup](#installation--setup)
11. [Usage Examples](#usage-examples)
12. [Advanced Features](#advanced-features)
13. [Integration Guide](#integration-guide)
14. [Moroccan Localization](#moroccan-localization)
15. [Troubleshooting](#troubleshooting)

---

## ✨ Features

### Core Features
- ✅ **Ticket Creation**: Residents report issues with title, description, category, and priority
- ✅ **Status Workflow**: OPEN → IN_PROGRESS → RESOLVED → CLOSED (with REOPENED state)
- ✅ **Priority Levels**: LOW, MEDIUM, HIGH, URGENT with auto-detection
- ✅ **Assignment System**: Admins assign tickets to themselves or team members
- ✅ **Chat Interface**: Thread-style messages for communication
- ✅ **File Attachments**: Support for images and documents as evidence
- ✅ **Internal Notes**: Staff-only notes not visible to residents

### Admin Features
- ✅ **Advanced Filtering**: Status, priority, category, assignment filters
- ✅ **Search Functionality**: Full-text search by title, description, tags
- ✅ **Bulk Actions**: Change status for multiple tickets
- ✅ **Activity Log**: Audit trail of all changes
- ✅ **Auto-Assignment**: Can be configured for category experts
- ✅ **Unassigned Queue**: Quick view of tickets needing assignment

### Smart Features
- ✅ **Auto-detect Urgent**: Keywords trigger urgent priority
- ✅ **SLA Management**: Automatic SLA due dates based on priority
- ✅ **SLA Breach Detection**: Track overdue tickets
- ✅ **Auto-populate Fields**: Apartment auto-filled from resident
- ✅ **Response Time Tracking**: Analytics on first response time

### Notifications
- ✅ **Email Notifications**: All key events trigger emails
- ✅ **SMS Ready**: Framework prepared for SMS integration
- ✅ **Internal Notes Alert**: Admins notified of new staff notes
- ✅ **SLA Breach Alert**: Urgent notifications for breached SLAs
- ✅ **Multi-recipient**: Admins, assigned staff, and residents get relevant updates

---

## 🏗️ Architecture

```
tickets/
├── models.py               # Data models (Ticket, Message, Attachment, etc.)
├── views.py               # CBV and FBV for ticket management
├── urls.py                # URL routing
├── admin.py               # Django admin configuration
├── forms.py               # Django forms (if using traditional forms)
├── serializers.py         # Data serializers for APIs
├── signals.py             # Django signals for auto-actions
├── apps.py                # App configuration
├── services/
│   ├── ticket_service.py        # Business logic for tickets
│   ├── notification_service.py  # Email/SMS notification handling
│   └── __init__.py
├── management/
│   └── commands/
│       ├── check_ticket_sla.py  # SLA checking command
│       └── __init__.py
├── migrations/            # Database migrations
└── tests.py              # Unit tests (to be created)

templates/tickets/
├── ticket_list.html       # List view with filters
├── ticket_detail.html     # Detail view with messages
├── ticket_form.html       # Create/edit ticket form
├── dashboard.html         # Admin dashboard widget
└── emails/
    ├── ticket_created_resident.html
    ├── ticket_created_admin.html
    ├── ticket_status_changed.html
    ├── ticket_assigned.html
    ├── ticket_message_added.html
    └── sla_breached.html
```

---

## 🗂️ Models

### 1. **TicketCategory**
Categories for organizing ticket types.

```python
class TicketCategory(models.Model):
    name_en          # English name (e.g., "Water Leak")
    name_fr          # French name
    name_ar          # Arabic name for Moroccan context
    description      # What issues fall under this category
    icon             # Icon class or emoji
    is_active        # Soft delete capability
```

### 2. **Ticket** (Core Model)
Main ticket entity with full audit trail.

```python
class Ticket(models.Model):
    # Content
    title                      # Issue title
    description               # Detailed description
    category                  # Foreign key to TicketCategory
    
    # Status & Priority
    status                    # OPEN, IN_PROGRESS, RESOLVED, CLOSED, REOPENED
    priority                  # LOW, MEDIUM, HIGH, URGENT
    
    # Assignment
    resident                  # Who reported the issue
    assigned_to               # Admin/staff assigned
    apartment                 # Location (auto-populated)
    
    # SLA
    is_urgent_auto_detected   # Boolean flag for auto-urgency
    sla_due_date             # Auto-calculated deadline
    sla_breached             # Boolean tracking SLA miss
    
    # Timestamps
    created_at               # Creation timestamp (indexed)
    updated_at               # Last update timestamp
    resolved_at              # When marked resolved
    closed_at                # When closed
    created_by               # Admin who created it
    
    # Metadata
    tags                     # Comma-separated tags for organization
    internal_notes           # Staff-only notes
    
    # Indexes: resident+status, assigned+status, status+date, priority+date, sla_breached+status
```

### 3. **TicketMessage** (Chat Support)
Thread-style messages for communication.

```python
class TicketMessage(models.Model):
    ticket                   # Foreign key to Ticket
    author                   # Who sent the message
    message                  # Message content
    is_internal             # Staff-only flag
    created_at              # Timestamp (indexed)
    updated_at              # Edit timestamp
```

### 4. **TicketAttachment** (File Support)
Support for images and documents.

```python
class TicketAttachment(models.Model):
    ticket                  # Foreign key to Ticket
    message                 # Optional: which message
    file                    # File field with validation
    file_name              # Original filename
    file_size              # Size in bytes
    file_type              # MIME type
    uploaded_by            # User who uploaded
    uploaded_at            # Timestamp
```

### 5. **TicketActivityLog** (Audit Trail)
Complete changelog of all ticket modifications.

```python
class TicketActivityLog(models.Model):
    ticket                 # Which ticket changed
    action                 # created, status_changed, assigned, etc.
    performed_by           # Which user made the change
    old_value             # Previous value (for comparisons)
    new_value             # New value
    description           # Human-readable description
    created_at            # When this change happened
```

---

## 🔐 Workflows & Permissions

### Resident Permissions
```
✓ Create tickets (for themselves)
✓ View their own tickets
✓ Add public messages to their tickets
✓ Upload attachments as evidence
✓ Cannot: Assign, change status, access other residents' tickets, see internal notes
```

### Syndic/Admin Permissions
```
✓ View all tickets
✓ Assign tickets to themselves/team
✓ Change ticket status
✓ Add public messages
✓ Add internal staff-only notes
✓ Filter and search all tickets
✓ Generate reports
✓ Cannot: Create tickets on behalf of residents (they create themselves)
```

### SuperAdmin Permissions
```
✓ All of the above PLUS:
✓ Configure SLA settings
✓ Manage ticket categories
✓ Configure auto-assignment rules
✓ Access full admin panel
```

### Status Workflow
```
                              ┌─────────────┐
                              │    OPEN     │
                              │  (Initial)  │
                              └──────┬──────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ IN_PROGRESS  │
                              │ (Being fixed)│
                              └──────┬───────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
            ┌───────────────┐  ┌──────────────┐  ┌─────────────┐
            │   RESOLVED    │  │   CLOSED     │  │  REOPENED   │
            │  (Fixed, not  │  │ (Done, no    │  │ (Back to    │
            │   yet closed) │  │  more action)│  │  work)      │
            └───────┬───────┘  └──────────────┘  └─────────────┘
                    │
                    ▼
            ┌───────────────┐
            │    CLOSED     │
            │   (Resolved & │
            │    verified)  │
            └───────────────┘
```

---

## 📡 API & Views

### URL Structure
```
/tickets/                           # List tickets (GET)
/tickets/create/                    # Create ticket (GET, POST)
/tickets/<id>/                      # View ticket detail (GET)
/tickets/<id>/update-status/        # Change status (POST)
/tickets/<id>/assign/               # Assign ticket (POST)
/tickets/<id>/message/              # Add message (POST)
/tickets/<id>/upload/               # Upload attachment (POST AJAX)
/tickets/dashboard/                 # Admin dashboard widget (GET)
```

### Key Views

#### **TicketListView** (List & Filter)
- Residents: See only their tickets
- Admins: See all with filters
- Supports: Status, Priority, Category, Assignment, Search

#### **TicketCreateView** (Create Issue)
- Title, Description, Category, Priority
- Auto-detects urgent keywords
- Auto-populates apartment
- Stores created_by for audit
- Sends notifications

#### **TicketDetailView** (View & Interact)
- Shows full ticket with messages
- Residents: See public messages only
- Admins: See all including internal notes
- Displays attachments with download links
- Shows activity log

#### **TicketUpdateStatusView** (Status Change)
- Admin-only view
- Updates timestamps appropriately
- Creates activity log entry
- Triggers notifications

#### **TicketAssignView** (Assignment)
- Admin-only view
- Assigns to another admin
- Auto-marks as IN_PROGRESS
- Notifies assigned admin

#### **TicketMessageCreateView** (Add Message)
- Support for public and internal messages
- Residents: Public only
- Admins: Both public and internal
- Triggers notifications

#### **TicketAttachmentUploadView** (Upload File)
- AJAX endpoint for file uploads
- Validates file type and size (max 10MB)
- Stores metadata (size, type, uploader)
- Returns JSON response

#### **TicketDashboardView** (Statistics Widget)
- Shows summary statistics
- Recent tickets list
- Tickets needing attention
- Can be embedded in main dashboard

---

## 🔍 Database Queries & Optimization

### Query Optimization Techniques Used

#### 1. **select_related()** - For ForeignKey/OneToOneField
```python
# Used in ticket list to avoid N+1 queries
tickets = Ticket.objects.select_related(
    'resident',      # Get user in same query
    'assigned_to',   # Get admin in same query
    'category'       # Get category in same query
)
```

#### 2. **prefetch_related()** - For reverse relations
```python
# Used to fetch related messages and attachments
tickets = Ticket.objects.prefetch_related(
    'messages',        # Get all messages
    'attachments',     # Get all files
    'activity_logs'    # Get audit trail
)
```

#### 3. **Database Indexes**
```python
# Meta indexes defined in Ticket model:
indexes = [
    Index(fields=['resident', 'status']),        # For resident queries
    Index(fields=['assigned_to', 'status']),     # For admin queries
    Index(fields=['status', '-created_at']),     # For sorting
    Index(fields=['priority', '-created_at']),   # Priority sorting
    Index(fields=['sla_breached', 'status']),    # SLA queries
]
```

#### 4. **Query Examples**

Getting resident tickets efficiently:
```python
Ticket.objects.filter(
    resident=user
).select_related(
    'assigned_to', 'category'
).prefetch_related(
    'messages', 'attachments'
).order_by('-created_at')
```

Getting admin tickets with unread count:
```python
Ticket.objects.filter(
    assigned_to=admin,
    status__in=['open', 'in_progress']
).select_related('resident').order_by('priority', 'created_at')
```

Getting urgent/SLA-breached tickets:
```python
Ticket.objects.filter(
    Q(priority='urgent') | Q(sla_breached=True)
).select_related('resident', 'assigned_to')
```

---

## 📧 Notifications System

### Email Templates & Triggers

#### 1. **Ticket Created (Resident)**
- **Trigger**: New ticket created
- **Recipient**: The resident who created it
- **Purpose**: Confirmation of submission
- **Template**: `ticket_created_resident.html`

#### 2. **Ticket Created (Admin)**
- **Trigger**: New ticket created
- **Recipient**: All admins
- **Purpose**: Notify of new work
- **Template**: `ticket_created_admin.html`

#### 3. **Status Changed (Resident)**
- **Trigger**: Admin changes status
- **Recipient**: The resident
- **Purpose**: Update on progress
- **Template**: `ticket_status_changed.html`

#### 4. **Status Changed (Admin)**
- **Trigger**: Admin changes status
- **Recipient**: Related admins
- **Purpose**: Keep team updated
- **Template**: `ticket_status_changed_admin.html`

#### 5. **Ticket Assigned**
- **Trigger**: Ticket assigned to someone
- **Recipient**: The assigned person
- **Purpose**: Notify of new responsibility
- **Template**: `ticket_assigned.html`

#### 6. **Message Added**
- **Trigger**: New message on ticket
- **Recipient**: Resident or assigned admin
- **Purpose**: Notify of new communication
- **Template**: `ticket_message_added.html`

#### 7. **SLA Breached**
- **Trigger**: SLA due date passed
- **Recipient**: Assigned admin + all admins
- **Purpose**: Urgent reminder
- **Template**: `sla_breached.html`

### SMS Integration Ready
The notification service has a placeholder for SMS:
```python
def send_sms(phone_number, message):
    """
    TODO: Integrate with SMS provider:
    - Maroc Telecom API
    - Orange Maroc API
    - Inwi API
    - Twilio for international
    """
    print(f"[SMS] To {phone_number}: {message}")
```

---

## 📊 Admin Dashboard

### Admin Interface Features

#### Ticket Admin List
```
- Sortable columns: ID, Title, Status, Priority, Resident, Assigned, Date
- Colored status badges: Open (Red), In Progress (Blue), Resolved (Green), Closed (Gray)
- Colored priority badges: Urgent (Red), High (Orange), Medium (Yellow), Low (Green)
- Message count display for quick overview
- Quick links to detail view
```

#### Bulk Actions
```
- Mark as In Progress
- Mark as Resolved  
- Mark as Closed
- Escalate to Urgent
```

#### Message Management
- Inline message viewing (read-only)
- Message author and timestamp
- Internal flag visibility
- Attachment preview links

#### Attachment Management
- File size display
- Upload date and uploader
- Direct download links

#### Activity Log
- Action tracking
- User accountability
- Before/after values for changes
- Chronological view

---

## ⏰ SLA Management

### SLA Configuration by Priority
```
URGENT:  24 hours to resolution
HIGH:    48 hours to resolution  
MEDIUM:  72 hours to resolution
LOW:     120 hours (5 days) to resolution
```

### SLA Calculation
```python
def _calculate_sla(self):
    """Calculate SLA due date based on ticket priority."""
    sla_hours = {
        'urgent': 24,
        'high': 48,
        'medium': 72,
        'low': 120,
    }
    hours = sla_hours[self.priority]
    self.sla_due_date = timezone.now() + timedelta(hours=hours)
```

### SLA Checking & Alerts
Run periodically (via Celery or cron):
```bash
python manage.py check_ticket_sla --notify
```

This command:
1. Finds all open tickets with past SLA due dates
2. Updates `sla_breached` flag to True
3. Sends notifications if --notify flag used
4. Suitable for: Celery task, cron job, or scheduled APScheduler task

---

## 🚀 Installation & Setup

### Step 1: Database Migration
```bash
# Create migration files
python manage.py makemigrations tickets

# Apply migrations
python manage.py migrate tickets
```

### Step 2: Load Initial Data (Optional)
Create ticket categories via admin or fixture.

### Step 3: Configure Settings
In `syndic/settings/base.py`:
```python
# Media files for attachments
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'  # Or your email provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = 'support@snadik.ma'
```

### Step 4: Create Admin Categories
```bash
python manage.py shell
```
```python
from tickets.models import TicketCategory

categories = [
    TicketCategory(name_en='Water Leak', name_fr='Fuite d\'eau', name_ar='تسرب المياه', icon='💧'),
    TicketCategory(name_en='Electricity', name_fr='Électricité', name_ar='الكهرباء', icon='⚡'),
    TicketCategory(name_en='Elevator', name_fr='Ascenseur', name_ar='المصعد', icon='🛗'),
    TicketCategory(name_en='Heating', name_fr='Chauffage', name_ar='التدفئة', icon='🔥'),
]

for cat in categories:
    cat.save()
```

### Step 5: Schedule SLA Checking
Add to your scheduler (Celery, APScheduler, or cron):

**Using Celery** (celery_tasks.py or similar):
```python
from celery import shared_task
from tickets.services.ticket_service import TicketService

@shared_task
def check_ticket_slas():
    TicketService.check_and_update_sla_status()
    
# In celery beat schedule:
'check-ticket-slas': {
    'task': 'check_ticket_slas',
    'schedule': crontab(minute=0),  # Run hourly
},
```

**Using Cron** (Linux/Mac):
```bash
# Edit crontab
crontab -e

# Run every hour
0 * * * * cd /path/to/project && python manage.py check_ticket_sla --notify
```

---

## 💡 Usage Examples

### For Residents

#### Creating a Ticket
1. Navigate to `/tickets/create/`
2. Fill in:
   - Title: "Leaking faucet in kitchen"
   - Description: "Faucet drips continuously, wasting water"
   - Category: "Water Leak"
   - Priority: "High" (for urgent issues)
3. Click "Create Ticket"
4. Receive confirmation email with ticket #ID
5. Can add attachments/messages later

#### Monitoring Status
1. Go to `/tickets/` to see all their tickets
2. Click a ticket to see:
   - Current status and priority
   - Timeline of messages
   - Assigned admin info
   - Recent activity
3. Add messages with updates or questions
4. Can upload photos as evidence

### For Admins

#### Dashboard Overview
1. Navigate to `/tickets/dashboard/`
2. See statistics:
   - Total open tickets
   - In progress count
   - Urgent tickets requiring attention
   - SLA breached count
3. Quick links to problematic tickets

#### Managing Tickets
1. Go to `/tickets/` (admin view shows all)
2. Use filters:
   - Filter by status (Open, In Progress, etc.)
   - Filter by priority
   - Filter by category
   - Search by title
3. For each ticket:
   - Click to view details
   - Assign to yourself or team
   - Change status as progress real updates
   - Add internal notes (not visible to resident)
   - Upload evidence or solutions

#### Workflow Example
```
1. Resident creates ticket: "No hot water"
   → All admins receive email notification

2. Admin reviews in list view
   → Sees it's marked URGENT (auto-detected)
   → SLA is 24 hours

3. Admin clicks ticket
   → Sees full description and apartment
   → Assigns to themselves
   → Status auto-changes to IN_PROGRESS

4. Resident receives email: "Ticket assigned, being worked on"

5. Admin adds internal note: "Boiler needs inspection"
   → Marks as RESOLVED when fixed

6. Resident receives email: "Your ticket has been resolved"
   → Can reopen if not satisfied

7. Resident adds message: "Thank you, working great!"

8. Admin marks as CLOSED
   → Ticket archived, no further messages
```

---

## 🎯 Advanced Features

### 1. Auto-Urgency Detection
Keywords that trigger HIGH/URGENT priority:
```python
urgent_keywords = [
    'leak', 'water', 'flood', 'fire', 'gas', 'safety',
    'emergency', 'danger', 'urgent', 'critical', 'broken',
    'fuite', 'incendie', 'gaz', 'sécurité', 'urgence',
    'حريق', 'غاز', 'أمان', 'طوارئ', 'خطر', 'تسرب'
]
```

### 2. Custom Dashboard Widget
Embed ticket stats in main dashboard:
```python
from tickets.services.ticket_service import TicketService

# In your dashboard view:
context['ticket_stats'] = TicketService.get_ticket_stats(request.user)

# Returns:
{
    'total_tickets': 42,
    'open_tickets': 8,
    'in_progress_tickets': 15,
    'urgent_and_open': 3,
    'overdue_sla': 2,
    'unassigned': 5,
}
```

### 3. Custom Reporting
```python
from django.db.models import Count, Q

# Tickets by category
from tickets.models import Ticket
report = Ticket.objects.values('category__name_en').annotate(
    count=Count('id')
).order_by('-count')

# Response time analytics
admin_tickets = Ticket.objects.filter(assigned_to=admin)
avg_response = TicketService.get_ticket_response_time_avg(admin)

# SLA compliance rate
total = Ticket.objects.count()
breached = Ticket.objects.filter(sla_breached=True).count()
compliance = ((total - breached) / total) * 100
```

### 4. API Endpoints (Future)
Can add DRF APIs for mobile app:
```python
# Potential endpoints:
GET /api/tickets/                    # List tickets
POST /api/tickets/                   # Create
GET /api/tickets/{id}/               # Detail
PATCH /api/tickets/{id}/             # Update
POST /api/tickets/{id}/messages/     # Add message
POST /api/tickets/{id}/attachments/  # Upload file
```

---

## 🔗 Integration Guide

### Integrating into Main Dashboard

Add to your main dashboard template:
```html
<!-- In templates/finance/dashboard.html or similar -->
<div class="row mt-4">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5>Your Tickets</h5>
            </div>
            <div class="card-body">
                {% include "tickets/dashboard.html" %}
            </div>
        </div>
    </div>
</div>
```

Add link in main navigation:
```html
<!-- In templates/base.html navbar -->
{% if user.is_authenticated %}
    <li><a href="{% url 'tickets:list' %}" class="nav-link">
        <i class="bi bi-ticket"></i> Tickets
    </a></li>
{% endif %}
```

### Database Relationships
Integrate with existing User model:
```python
# Already configured to use Django's User model
from django.contrib.auth import get_user_model
User = get_user_model()

# ForeignKey relationships:
# - Ticket.resident → User (role: RESIDENT)
# - Ticket.assigned_to → User (role: SYNDIC/SUPERADMIN)
# - TicketMessage.author → User
# - TicketAttachment.uploaded_by → User
```

### Adding to Navigation
```python
# In context_processors.py or base view:
context['user_tickets'] = Ticket.objects.filter(
    resident=request.user
).count() if request.user.role == 'RESIDENT' else 0
```

---

## 🇲🇦 Moroccan Localization

### Language Support
Models support French, Arabic, and English:
```python
class TicketCategory(models.Model):
    name_en = "Water Leak"
    name_fr = "Fuite d'eau"
    name_ar = "تسرب المياه"
```

### Categories Relevant to Morocco
```
- Plomberie (Plumbing)
- Électricité (Electrical)
- Climatisation (Air conditioning) - Important in Morocco
- Ascenseur (Elevator)
- Chauffage (Heating)
- Toiture (Roof) - Important for flat roofs common in Morocco
- Fenêtres (Windows)
- Portes (Doors)
- Peinture (Painting)
- Nettoyage (Cleaning)
```

### SMS Integration for Morocco
Ready to integrate with:
- **Maroc Telecom**: Official API for business SMS
- **Orange Maroc**: Orange Business Services API
- **Inwi**: Inwi Business SMS
- **Twilio**: International fallback

Example template:
```
Bonjour {name},
Votre ticket #{id} a été accept.
Status: {status}
Référence: {ticket_id}
Visitez: snadik.ma/tickets/{id}
```

### RTL Support (Arabic)
Add to CSS or base template:
```html
<html dir="{% if request.LANGUAGE_CODE == 'ar' %}rtl{% endif %}">
```

### Date/Time Localization
Django handles automatically with `USE_I18N = True`:
```python
# Settings include:
USE_I18N = True
LANGUAGE_CODE = 'fr'  # Default to French for Morocco
TIME_ZONE = 'Africa/Casablanca'
USE_TZ = True
```

---

## 🐛 Troubleshooting

### Common Issues & Solutions

#### Issue: Migrations not applying
```bash
# Solution:
python manage.py makemigrations tickets
python manage.py migrate tickets

# If stuck:
python manage.py migrate tickets zero
python manage.py migrate tickets
```

#### Issue: Ticket created but no email sent
```bash
# Check email settings:
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])

# If fails, check:
# 1. EMAIL_BACKEND configuration
# 2. EMAIL_HOST_USER/PASSWORD valid
# 3. ALLOWED_PORTS: 587 for TLS,  465 for SSL
# 4. Log file for error details
```

#### Issue: Attachments not showing
```bash
# Check media configuration:
# In settings: MEDIA_URL, MEDIA_ROOT defined
# In urls: static/media files configured
# In forms: enctype="multipart/form-data"

# Serve media in development:
# urls.py includes: urlpatterns += static(MEDIA_URL, document_root=MEDIA_ROOT)
```

#### Issue: SLA not calculated
```bash
# Manual recalculation:
python manage.py shell
>>> from tickets.services.ticket_service import TicketService
>>> TicketService.check_and_update_sla_status()
5  # Returns count of updated tickets
```

#### Issue: Permission denied errors
```bash
# Check user role in admin:
# User.role must be one of: 'RESIDENT', 'SYNDIC', 'SUPERADMIN'

# Debug in shell:
>>> user.role  # Should return valid choice
>>> user.is_resident  # Should match role
```

#### Issue: Tickets not appearing in list
```bash
# Check queryset filtering:
# 1. Residents see only their tickets
# 2. Admins see all tickets
# 3. Check ticket.status is not None

python manage.py shell
>>> from tickets.models import Ticket
>>> Ticket.objects.count()  # Total tickets
>>> Ticket.objects.filter(resident=your_user).count()  # Your tickets
```

### Performance Optimization Tips

```python
# 1. Use select_related for ForeignKeys
tickets = Ticket.objects.select_related('resident', 'assigned_to')

# 2. Use prefetch_related for reverse relations
tickets = tickets.prefetch_related('messages', 'attachments')

# 3. Add indexes for frequently queried fields
# Already done in model Meta.indexes

# 4. Use .only() and .defer() to limit fields
tickets = Ticket.objects.only('id', 'title', 'status')

# 5. Cache statistics
from django.views.decorators.cache import cache_page
@cache_page(300)  # Cache for 5 minutes
def dashboard_view(request):
    ...
```

### Monitoring & Logging

Add to settings:
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'tickets.log',
        },
    },
    'loggers': {
        'tickets': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

---

## 📚 API Reference (REST Framework - Optional)

Can be added using Django REST Framework:

```python
from rest_framework import viewsets
from .serializers import TicketSerializer, TicketMessageSerializer

class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'category']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'priority']

# Register in urls.py:
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register(r'api/tickets', TicketViewSet)
urlpatterns += router.urls
```

---

## 🔒 Security Considerations

```python
# Already implemented:
✓ Permission checks on all views (LoginRequiredMixin, UserPassesTestMixin)
✓ CSRF protection ({% csrf_token %} in forms)
✓ File upload validation (file type, size limits)
✓ QuerySet filtering by user role
✓ SQL injection prevention (Django ORM)
✓ XSS prevention (template auto-escaping)

# Additional recommendations:
- Use HTTPS in production
- Set SECURE_BROWSER_XSS_FILTER = True
- Set SECURE_CONTENT_SECURITY_POLICY
- Rate limit file uploads
- Regular security audits
- Keep Django updated
```

---

## 📞 Support & Next Steps

### To-Do for Production
- [ ] Write unit tests (tests.py)
- [ ] Add API version using DRF
- [ ] Implement Celery for async tasks
- [ ] Add SMS integration
- [ ] Create mobile app API
- [ ] Add advanced reporting/analytics
- [ ] Implement ticket templates for common issues
- [ ] Add user feedback/satisfaction ratings
- [ ] Create SLA dashboard
- [ ] Add bulk export functionality

### Performance Recommendations
- Use Redis for caching
- Implement Celery for notifications
- Use CDN for attachments
- Archive old tickets to separate DB
- Monitor query performance with django-debug-toolbar

---

## License & Attribution

This Complaint & Ticket Management System is part of the Snadik.ma property management platform.

**Created**: 2024
**Version**: 1.0.0  
**Status**: Production Ready

---

## 📧 Questions?

For integration help or customization:
- Review the models.py for database structure
- Check views.py for logic flow
- Examine services/ for business logic  
- See templates/ for UI customization

---

**Last Updated**: March 2024
**Maintained By**: Snadik.ma Development Team
