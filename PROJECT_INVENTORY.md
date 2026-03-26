# Project Inventory - SyndicPro

## 📱 Django Apps

### 1. **accounts** - User & Authentication Management
Located: `/accounts/`

**Models:**
- `User` (AbstractUser) - Custom user with roles (SUPERADMIN, SYNDIC, RESIDENT)
  - Fields: role, apartment, phone, address, is_resident, created_by
  - Constraints: Unique apartment per resident

**Views:**
- `CustomLoginView` - User authentication
- `CustomLogoutView` - User logout
- `RegisterView` - User registration
- `UserProfileView` - User profile management
- `SettingsView` - User settings

**URLs:**
- `system/accounts/`

---

### 2. **finance** - Core Finance & Document Management
Located: `/finance/`

**Models:**
- `OperationLog` - Unified history log for actions
- `Event` - Calendar events (meetings, deadlines)
- `ResidentReport` - Resident issue reports
- `ReportComment` - Comments on reports
- `Document` - Documents uploaded by syndic
- `Notification` - Notification system
- `Payment` - Payment records
- `Depense` - Expense tracking
- `ResidentStatus` - Resident status tracking
- `OverdueNotificationLog` - Overdue payment tracking
- `Reminder` - Payment reminders
- `ChatbotFAQ` - FAQ for chatbot
- `ChatbotConversation` - Chatbot conversations
- `ChatbotMessage` - Chatbot messages

**Views:**
- **Authentication & Home:**
  - `HomeView` - Home page
  - `CustomLoginView` - Login
  - `RegisterView` - Registration
  - `CustomLogoutView` - Logout

- **Dashboards:**
  - `SyndicDashboardView` - Syndic dashboard
  - `ResidentDashboardView` - Resident dashboard

- **Resident Management:**
  - `ResidentManagementView` - List residents
  - `ResidentCreateView` - Create resident
  - `ResidentDetailView` - View resident details
  - `ResidentUpdateView` - Update resident

- **Syndic Management:**
  - `SyndicManagementView` - List syndics
  - `SyndicCreateView` - Create syndic
  - `SyndicDetailView` - View syndic details
  - `SyndicUpdateView` - Update syndic

- **Document Management:**
  - `DocumentListView` - List documents
  - `DocumentCreateView` - Create document (with form validation)
  - `DocumentDetailView` - View document details

- **Payment Management:**
  - `PaymentListView` - List payments
  - `PaymentDetailView` - Payment details
  - `PaymentUpdateView` - Update payment
  - `PaymentCreateView` - Create payment
  - `PaymentProofView` - Payment proof
  - `PaymentUploadAPI` - API for payment upload
  - `PaymentVerificationAPI` - API for payment verification

- **Notifications:**
  - `NotificationListView` - List notifications
  - `NotificationCreateView` - Create notification
  - `NotificationDetailView` - View notification

- **Reports:**
  - `ResidentReportListView` - List reports
  - `ResidentReportCreateView` - Create report
  - `ResidentReportDetailView` - View report
  - `ReportManagementView` - Manage reports
  - `ReportUpdateView` - Update report
  - `ReportCommentCreateView` - Add comment to report

- **Calendar:**
  - `CalendarListView` - View calendar
  - `EventCreateView` - Create event

- **Expenses:**
  - `DepenseListView` - List expenses
  - `DepenseCreateView` - Create expense
  - `DepenseDetailView` - View expense
  - `DepenseUpdateView` - Update expense
  - `DepenseDeleteView` - Delete expense

- **Overdue Payments:**
  - `OverduePaymentsDashboardView` - Overdue dashboard
  - `ResidentPaymentHistoryView` - Payment history
  - `SendReminderView` - Send payment reminder
  - `RunOverdueDetectionView` - Run overdue detection

- **API Endpoints:**
  - `NavigationStatsAPI` - Navigation statistics (GET)
  - `SendNotificationAPI` - Send notification

**Forms:**
- `DocumentForm` - Form for creating/updating documents with proper date handling

**Services:**
- `dashboard_service.py` - Build syndic dashboard context
- `navigation_service.py` - Build navigation stats (unread notifications, document counts, etc.)

**Management Commands:**
- `daily_overdue_check.py` - Daily overdue payment check
- `detect_overdue_payments.py` - Detect and process overdue payments
- `test_email.py` - Test email functionality
- `test_resident_notification.py` - Test resident notifications

**APIs:**
- `api_views.py` - NavigationStatsAPI

**URLs:** `/` (root paths)

---

### 3. **tickets** - Ticket & Complaint Management
Located: `/tickets/`

**Models:**
- `TicketCategory` - Categories (water, electricity, elevator, etc.)
- `Ticket` - Main ticket model with status workflow
  - Status: OPEN, IN_PROGRESS, RESOLVED, CLOSED
  - Priority levels: CRITICAL, HIGH, MEDIUM, LOW
  - SLA tracking
- `TicketMessage` - Messages on tickets
- `TicketAttachment` - Attachments to tickets
- `TicketSLA` - SLA configuration
- `TicketActivityLog` - Audit trail for tickets

**Views:**
- `TicketListView` - List tickets
- `TicketCreateView` - Create ticket
- `TicketDetailView` - View ticket details
- `TicketUpdateStatusView` - Update ticket status
- `TicketAssignView` - Assign ticket
- `TicketMessageCreateView` - Add message to ticket
- `TicketAttachmentUploadView` - Upload attachment
- `TicketDashboardView` - Ticket dashboard

**URLs:** `/tickets/`

---

### 4. **notifications** - Notifications App
Located: `/notifications/`

**Views:**
- `NotificationsHealthView` - Health check

**URLs:** `/system/notifications/`

---

### 5. **residents** - Residents App
Located: `/residents/`

**Views:**
- `ResidentsHealthView` - Health check

**URLs:** `/system/residents/`

---

### 6. **documents** - Documents App
Located: `/documents/`

**Views:**
- `DocumentsHealthView` - Health check

**URLs:** `/system/documents/`

---

## 🎨 Templates

Located: `/templates/`

**Base Template:**
- `base.html` - Main base template with navigation, sidebars, and JavaScript utilities

**Finance Templates:**
- `finance/home.html` - Home page
- `finance/document_form.html` - Document create/edit form
- `finance/document_detail.html` - Document details

**Components:**
- `components/form_field.html` - Reusable form field component with date input support
- `components/page_header.html` - Page header with title and actions
- Other component templates

**Email Templates:**
- `emails/` - Email notification templates

---

## 🛠️ Services & Utilities

### Finance Services:
- **dashboard_service** - Builds syndic dashboard context with statistics
- **navigation_service** - Builds navigation statistics for badge updates

### Tickets Services:
- Located in `tickets/services/`

---

## 🗄️ Database Models Summary

**Total Models: 19**

| Model | App | Purpose |
|-------|-----|---------|
| User | accounts | User authentication & roles |
| OperationLog | finance | Action history |
| Event | finance | Calendar events |
| ResidentReport | finance | Issue reports from residents |
| ReportComment | finance | Comments on reports |
| Document | finance | Document management |
| Notification | finance | Notification system |
| Payment | finance | Payment tracking |
| Depense | finance | Expense tracking |
| ResidentStatus | finance | Resident status |
| OverdueNotificationLog | finance | Overdue tracking |
| Reminder | finance | Payment reminders |
| ChatbotFAQ | finance | FAQ system |
| ChatbotConversation | finance | Chatbot conversations |
| ChatbotMessage | finance | Chatbot messages |
| TicketCategory | tickets | Ticket categories |
| Ticket | tickets | Ticket tracking |
| TicketMessage | tickets | Ticket messages |
| TicketAttachment | tickets | Ticket attachments |
| TicketSLA | tickets | SLA configuration |
| TicketActivityLog | tickets | Ticket audit trail |

---

## 🌐 API Endpoints

### Navigation Stats API:
- **GET** `/api/navigation-stats/` - Get dashboard statistics
  - Requires login (SYNDIC or SUPERADMIN)
  - Returns: total_residents, total_documents, total_expenses, overdue_count, unread_notifications, etc.

### Finance APIs:
- **POST** `/api/payments/upload/` - Upload payment proof
- **POST** `/api/payments/<id>/verify/` - Verify payment
- **POST** `/api/send-notification/` - Send notification
- **POST** `/api/run-overdue-detection/` - Trigger overdue detection

---

## 📁 Static Files

Located: `/static/`

**CSS:**
- `/css/saas-system.css` - Main styling

**Images:**
- `/images/` - Image assets

---

## 🔧 Configuration

**Settings:** `syndic/settings/`
- `base.py` - Base settings (shared config)
- `dev.py` - Development settings
- `prod.py` - Production settings

**Date Format Settings:**
- `DATE_FORMAT = "Y-m-d"`
- `DATE_INPUT_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]`

**Database:**
- SQLite (default) or configurable via `.env`
- Timezone: Africa/Casablanca
- Language: French (fr)

---

## 📦 Key Features

✅ **User Management**
- Three roles: SUPERADMIN, SYNDIC (Manager), RESIDENT
- User authentication & authorization

✅ **Document Management**
- Create, list, view documents
- Document archiving
- File uploads with proper date handling

✅ **Payment Tracking**
- Track document payments
- Overdue payment detection (>30 days)
- Payment proof uploads
- Payment verification

✅ **Notifications**
- Notification system with read/unread status
- Email notifications
- SMS notifications (configured)

✅ **Expense Management**
- Create and track expenses
- Expense categorization
- Monthly expense summaries

✅ **Ticket System**
- Create complaints/tickets
- Multiple ticket statuses
- SLA tracking
- Attachments support
- Message system for tickets

✅ **Calendar/Events**
- Create shared events
- Event notifications
- Participant management

✅ **Reporting**
- Resident issue reports
- Report categorization
- Report comments
- Status tracking

✅ **Dashboard**
- Syndic dashboard with statistics
- Resident dashboard
- Real-time badge updates via API

---

## 🚀 Management Commands

- **daily_overdue_check** - Runs daily overdue payment detection
- **detect_overdue_payments** - Detects and processes overdue payments
- **test_email** - Tests email functionality
- **test_resident_notification** - Tests resident notifications

---

## 🔒 Authentication & Permissions

- Login required for most views
- Role-based access control (SUPERADMIN, SYNDIC, RESIDENT)
- CSRF protection on all forms
- Secure file uploads

---

## 📊 Key Statistics Tracked

Via Navigation API:
- Total residents
- Total documents
- Total expenses
- Overdue document count
- Unread notifications
- New issue reports
- Documents created this month
- Payments received this month
- Expenses this month
- New residents this month

---

Generated on: 2026-03-26
