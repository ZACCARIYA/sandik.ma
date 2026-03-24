# Tickets App - Quick Start Guide

A complete, production-ready complaint & ticket management system for Snadik.ma.

## 🚀 Quick Setup

### 1. Run Migrations
```bash
python manage.py migrate tickets
```

### 2. Create Initial Data
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
    TicketCategory(name_en='Plumbing', name_fr='Plomberie', name_ar='السباكة', icon='🔧'),
    TicketCategory(name_en='Roof/Structural', name_fr='Toiture/Structure', name_ar='السقف/الهيكل', icon='🏠'),
    TicketCategory(name_en='Common Areas', name_fr='Espaces Communs', name_ar='المناطق المشتركة', icon='🌳'),
]

for cat in categories:
    cat.save()

print("Categories created successfully!")
```

### 3. Configure Email (Optional but Recommended)
In `syndic/settings/base.py`:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = 'support@snadik.ma'
```

### 4. Schedule SLA Checks (Optional)
Add to crontab to run hourly:
```bash
0 * * * * cd /path/to/project && python manage.py check_ticket_sla --notify
```

## 📋 URLs

| URL | Purpose | Auth | Description |
|-----|---------|------|-------------|
| `/tickets/` | List tickets | Required | View all tickets (residents only see theirs) |
| `/tickets/create/` | Create ticket | RESIDENT | Report new issue |
| `/tickets/<id>/` | View detail | Required | View ticket + messages |
| `/tickets/<id>/update-status/` | Change status | ADMIN | Update workflow status |
| `/tickets/<id>/assign/` | Assign ticket | ADMIN | Assign to staff member |
| `/tickets/<id>/message/` | Add message | Required | Add communication |
| `/tickets/<id>/upload/` | Upload file | Required | Attach evidence/doc |
| `/tickets/dashboard/` | Statistics | Any | Widget with stats |

## 🎨 Templates

### For Residents
- **ticket_list.html**: See only their tickets, filtered
- **ticket_form.html**: Beautiful form to create issue
- **ticket_detail.html**: View progress, add messages

### For Admins
- **ticket_list.html**: See all, with advanced filters
- **ticket_detail.html**: Full control, internal notes
- **dashboard.html**: Statistics widget

### Admin Interface
- Full-featured Django admin for management
- Bulk actions, search, filters
- Inline messages and attachments

## 📊 Key Features

### For Residents
✅ Report issues easily
✅ Track status in real-time  
✅ Communicate with admin
✅ Upload evidence (photos, docs)
✅ Get email notifications
✅ Reopen if not satisfied

### For Admins
✅ View all tickets
✅ Assign to team members
✅ Manage workflow with statuses  
✅ Add internal staff notes
✅ Track SLA compliance
✅ See activity history
✅ Search & filter
✅ Export/report

### Smart Features
✅ Auto-detect urgent issues
✅ Auto-calculate SLA deadlines
✅ Alert on SLA breaches
✅ Activity audit trail
✅ Permission-based access
✅ Optimized queries (no N+1)
✅ File upload validation
✅ Email notifications

## 🔄 Status Workflow

```
OPEN → IN_PROGRESS → RESOLVED → CLOSED
              ↓
           REOPENED
```

## 🎯 Priority Levels

| Priority | SLA | Color | When |
|----------|-----|-------|------|
| URGENT | 24h | 🔴 Red | Critical issues (fire, gas, safety) |
| HIGH | 48h | 🟠 Orange | Major problems (no water, power) |
| MEDIUM | 72h | 🟡 Yellow | Standard maintenance |
| LOW | 120h | 🟢 Green | Minor issues (cosmetic) |

## 🔍 Filtering & Search

**By Status**: Open, In Progress, Resolved, Closed, Reopened
**By Priority**: Urgent, High, Medium, Low
**By Category**: Water, Electricity, Elevator, etc.
**By Assignment**: Unassigned, Assigned to Me
**By Apartment**: Text search
**By Title/Description**: Full-text search

## 📧 Notifications

Emails sent automatically for:
- ✅ New ticket created
- ✅ Status changed
- ✅ Ticket assigned
- ✅ Message added  
- ✅ SLA breached

SMS integration ready (configure provider)

## 🛠️ Admin Commands

### Check SLA Status
```bash
# Find breached SLAs and update
python manage.py check_ticket_sla

# Also send notifications
python manage.py check_ticket_sla --notify
```

### Shell Access
```bash
python manage.py shell

# Get statistics
from tickets.services.ticket_service import TicketService
stats = TicketService.get_ticket_stats()
print(stats)

# Check overdue ticket
overdue = TicketService.get_overdue_tickets()
print(overdue.count())

# Check urgent
urgent = TicketService.get_urgent_tickets()
print(urgent.count())
```

## 💾 Database Models

### Ticket
Main ticket entity
- title, description, category
- status (workflow)
- priority (impact level)
- resident (who reported)
- assigned_to (who's working)
- sla_due_date, sla_breached
- timestamps (created, updated, resolved, closed)

### TicketMessage  
Chat-style messages
- ticket (parent)
- author (who wrote)
- message (content)
- is_internal (staff-only)
- timestamps

### TicketAttachment
Files uploaded
- ticket (parent)
- message (optional reference)
- file (actual file)
- uploader, timestamps

### TicketActivityLog
Audit trail
- ticket
- action (what changed)
- old_value, new_value
- performed_by, created_at

### TicketCategory
Taxonomy
- name (en, fr, ar)
- icon
- is_active

## 🧪 Testing

### Manual Test Flow

#### 1. Create Ticket (as Resident)
1. Login as resident
2. Go to `/tickets/create/`
3. Fill form with issue
4. Submit
5. Should see confirmation + receive email

#### 2. View in Admin (as Admin)
1. Login as admin
2. Go to `/tickets/` (all visible)
3. See ticket in list
4. Click to view detail
5. Should see all info + messages

#### 3. Manage (as Admin)
1. Click ticket detail
2. Assign to yourself
3. Change status to IN_PROGRESS
4. Add message with update
5. Add internal note
6. Resident receives only messages (not notes)

#### 4. SLA Check
1. Run: `python manage.py check_ticket_sla --notify`
2. Overdue tickets marked with sla_breached=True
3. Admins receive alerts

## 🐛 Troubleshooting

### Migrations failing?
```bash
python manage.py migrate tickets --fake-initial
```

### Media files not showing?
```python
# In settings, add:
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# In urls.py, add:
from django.conf import settings
from django.conf.urls.static import static
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### No emails sending?
```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Body', 'from@example.com', ['to@example.com'])
# If fails, check EMAIL settings in base.py
```

### Permissions denied?
```bash
# Check user.role matches expected
# RESIDENT = resident user
# SYNDIC/SUPERADMIN = admin
```

## 📈 Performance Tips

```python
# Use queries efficiently:
from tickets.services.ticket_service import TicketService

# ✅ Good (optimized):
TicketService.get_admin_tickets(filters={'status': 'open'})

# ❌ Bad (N+1 queries):
for ticket in Ticket.objects.all():
    print(ticket.resident.name)  # Query per ticket!
```

## 🔐 Security

- ✅ All views require login (LoginRequiredMixin)
- ✅ Permission checks (UserPassesTestMixin)
- ✅ CSRF protection ({% csrf_token %})
- ✅ File validation (type, size)
- ✅ QuerySet filtering by user
- ✅ Sensitive data protection

## 🌍 Moroccan Localization

### Languages
- English (en)
- French (fr) - Default
- Arabic (ar) - For Morocco

### SMS Providers Ready
- Maroc Telecom
- Orange Maroc
- Inwi
- Twilio (fallback)

### Categories for Morocco
- Plomberie (Plumbing)
- Électricité (Electrical)
- Climatisation (A/C)
- Toiture (Roof)
- Ascenseur (Elevator)

## 📚 Full Documentation

See `docs/TICKET_SYSTEM_DOCUMENTATION.md` for:
- Full API reference
- Database schema details
- Integration guide
- Advanced features
- SMS integration setup
- Analytics examples
- Security hardening

## 🚀 Next Steps

1. **Test locally**: Create some test tickets
2. **Configure emails**: Set up email provider
3. **Customize**: Add your categories and workflows
4. **Deploy**: Follow Django deployment guidelines
5. **Monitor**: Set up SLA checking job
6. **Extend**: Add SMS, API, mobile app, etc.

## 📞 Need Help?

Check the full documentation or examine:
- `models.py`: Database structure
- `views.py`: Business logic
- `services/`: Core functionality
- `admin.py`: Admin interface
- `templates/`: UI/UX

---

**Status**: Production Ready ✅  
**Version**: 1.0.0  
**Updated**: March 2024
