# SyndicPro - Production-Ready Architecture & Improvement Plan

> Senior Architecture Review & Implementation Roadmap  
> Last Updated: 2026-03-26

---

## 📋 Executive Summary

Your project has solid foundations but needs **architectural restructuring** to achieve production-grade quality. This document provides:

✅ Current state analysis  
✅ Architecture redesign  
✅ Code examples for each improvement  
✅ Priority-based implementation roadmap  
✅ Performance & security enhancements  

---

## 🔴 CRITICAL ISSUES (Fix First)

### 1. **Monolithic Structure**
- All logic mixed in views, models, and services
- No clear separation of concerns
- Difficult to test and maintain

### 2. **N+1 Query Problems**
- Navigation API queries without optimization
- No select_related/prefetch_related
- Database will slow down significantly with real data

### 3. **No Permission System**
- Only basic role checking in views
- No object-level permissions
- Residents can access each other's data

### 4. **Missing Validation & Error Handling**
- Inconsistent error responses
- No input sanitization
- SQL injection risks

### 5. **No API Versioning**
- `/api/navigation-stats/` with no version
- Breaking changes will affect clients

### 6. **Synchronous Overdue Detection**
- Cron job blocks request
- No notification queueing
- Will cause timeouts at scale

---

## 🎯 PRIORITY ROADMAP

```
PHASE 1 (Week 1-2): Critical Fixes
├─ Refactor to clean architecture
├─ Add Django permissions & DRF
├─ Optimize database queries
└─ Add API versioning

PHASE 2 (Week 3-4): Core Features
├─ Add authentication (JWT)
├─ Implement Celery for async tasks
├─ Add caching (Redis)
└─ Improve error handling

PHASE 3 (Week 5-6): Enhancement
├─ Multi-tenant support
├─ Payment integration
├─ Real-time notifications
└─ Advanced analytics

PHASE 4 (Week 7+): Scaling
├─ Dockerization
├─ CI/CD pipeline
├─ Performance optimization
└─ Production deployment
```

---

# PHASE 1: CRITICAL FIXES & ARCHITECTURE

## 1️⃣ CLEAN ARCHITECTURE RESTRUCTURING

### Current Problem:
```python
# finance/views.py (BAD - Mixed concerns)
class DocumentCreateView(CreateView):
    model = Document
    form_class = DocumentForm
    
    def form_valid(self, form):
        # Business logic mixed in view
        form.instance.uploaded_by = self.request.user
        
        # Query optimization missing
        residents = User.objects.filter(role='RESIDENT')
        
        # Validation missing
        return super().form_valid(form)
```

### Solution: Service Layer Architecture

**New folder structure:**
```
finance/
├── models/
│   ├── __init__.py
│   ├── document.py          # Domain models only
│   ├── payment.py
│   └── notification.py
├── services/
│   ├── __init__.py
│   ├── document_service.py  # Business logic
│   ├── payment_service.py
│   └── notification_service.py
├── repositories/
│   ├── __init__.py
│   ├── document_repository.py  # Data access
│   ├── payment_repository.py
│   └── user_repository.py
├── schemas/
│   ├── __init__.py
│   ├── document_schema.py   # DTOs & serializers
│   └── payment_schema.py
├── permissions/
│   ├── __init__.py
│   ├── document_permissions.py
│   └── object_permissions.py
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   ├── views.py       # Thin controllers
│   │   ├── serializers.py
│   │   └── urls.py
│   └── v2/
│       └── (future versions)
└── management/
    └── commands/
```

### Example Implementation:

**1. Domain Model** (`finance/models/document.py`):
```python
from django.db import models
from django.utils import timezone
from decimal import Decimal
from datetime import date

class Document(models.Model):
    """Domain model - pure data representation"""
    DOCUMENT_TYPES = [
        ('INVOICE', 'Facture'),
        ('NOTICE', 'Avis'),
        ('REMINDER', 'Rappel'),
        ('LEGAL', 'Document légal'),
        ('OTHER', 'Autre'),
    ]
    
    title = models.CharField(max_length=200, db_index=True)
    file = models.FileField(upload_to='documents/%Y/%m/')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=date.today, db_index=True)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    
    # Foreign keys with proper optimization
    resident = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='documents',
        db_index=True,
        limit_choices_to={'role': 'RESIDENT'}
    )
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='uploaded_documents',
        limit_choices_to={'role__in': ['SUPERADMIN', 'SYNDIC']}
    )
    
    is_paid = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        # Composite indexes for common queries
        indexes = [
            models.Index(fields=['resident', 'is_paid']),
            models.Index(fields=['resident', 'is_archived']),
            models.Index(fields=['date', 'is_paid']),
            models.Index(fields=['document_type', 'created_at']),
        ]
        verbose_name_plural = "Documents"

    def __str__(self):
        return f"{self.title} - {self.resident.username}"

    # Domain logic (not persistence logic)
    def mark_as_paid(self) -> None:
        """Mark document as paid"""
        if self.is_paid:
            raise ValueError("Document already marked as paid")
        self.is_paid = True

    def is_overdue(self, days_threshold: int = 30) -> bool:
        """Check if document is overdue"""
        if self.is_paid:
            return False
        from datetime import timedelta
        from django.utils import timezone
        return (timezone.now().date() - self.date).days > days_threshold

    def get_days_overdue(self, days_threshold: int = 30) -> int:
        """Calculate days overdue"""
        if self.is_paid:
            return 0
        from datetime import timedelta
        from django.utils import timezone
        overdue_days = (timezone.now().date() - self.date).days - days_threshold
        return max(0, overdue_days)
```

**2. Repository Pattern** (`finance/repositories/document_repository.py`):
```python
from typing import List, Optional, Tuple
from django.db.models import QuerySet, Prefetch
from django.contrib.auth import get_user_model
from ..models import Document
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class DocumentRepository:
    """Data access layer - handles all database queries"""
    
    @staticmethod
    def get_document_by_id(doc_id: int) -> Optional[Document]:
        """Retrieve document with optimized queries"""
        return Document.objects.select_related(
            'resident',
            'uploaded_by'
        ).filter(id=doc_id).first()
    
    @staticmethod
    def get_resident_documents(
        resident_id: int,
        is_archived: bool = False,
        include_paid: bool = True
    ) -> QuerySet:
        """Get documents for a resident with optimization"""
        qs = Document.objects.filter(
            resident_id=resident_id,
            is_archived=is_archived
        ).select_related('uploaded_by').order_by('-date')
        
        if not include_paid:
            qs = qs.filter(is_paid=False)
        
        return qs
    
    @staticmethod
    def get_overdue_documents(
        days_threshold: int = 30
    ) -> QuerySet:
        """Get all overdue unpaid documents"""
        cutoff_date = timezone.now().date() - timedelta(days=days_threshold)
        return Document.objects.filter(
            is_paid=False,
            is_archived=False,
            date__lt=cutoff_date
        ).select_related('resident', 'uploaded_by')
    
    @staticmethod
    def get_documents_by_resident(
        resident_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[QuerySet, int]:
        """Paginated documents for a resident"""
        qs = Document.objects.filter(
            resident_id=resident_id
        ).select_related('resident', 'uploaded_by')
        
        total = qs.count()
        documents = qs[offset:offset+limit]
        
        return documents, total
    
    @staticmethod
    def create_document(
        title: str,
        file,
        amount: float,
        date,
        document_type: str,
        resident_id: int,
        uploaded_by_id: int,
        description: str = ""
    ) -> Document:
        """Create new document"""
        document = Document.objects.create(
            title=title,
            file=file,
            amount=amount,
            date=date,
            document_type=document_type,
            resident_id=resident_id,
            uploaded_by_id=uploaded_by_id,
            description=description
        )
        return document
    
    @staticmethod
    def bulk_update_documents(
        document_ids: List[int],
        **fields
    ) -> int:
        """Bulk update documents"""
        return Document.objects.filter(
            id__in=document_ids
        ).update(**fields)
```

**3. Service Layer** (`finance/services/document_service.py`):
```python
from typing import List, Dict, Optional
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

from ..repositories.document_repository import DocumentRepository
from ..models import Document
from ..schemas.document_schema import DocumentCreateSchema

User = get_user_model()

class DocumentService:
    """Business logic layer - handles operations and validations"""
    
    CACHE_KEY_OVERDUE = "documents:overdue:count"
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self):
        self.repository = DocumentRepository()
    
    def create_document(
        self,
        data: DocumentCreateSchema,
        uploaded_by: User
    ) -> Document:
        """Create a new document with validation"""
        # Validation
        if uploaded_by.role not in ['SUPERADMIN', 'SYNDIC']:
            raise PermissionError("Only SYNDIC or SUPERADMIN can create documents")
        
        # Check resident exists
        resident = User.objects.filter(
            id=data.resident_id,
            role='RESIDENT'
        ).first()
        
        if not resident:
            raise ValueError(f"Resident {data.resident_id} not found")
        
        # Create document
        document = self.repository.create_document(
            title=data.title,
            file=data.file,
            amount=data.amount,
            date=data.date,
            document_type=data.document_type,
            resident_id=data.resident_id,
            uploaded_by_id=uploaded_by.id,
            description=data.description
        )
        
        # Clear cache
        cache.delete(self.CACHE_KEY_OVERDUE)
        
        # Trigger notifications (via Celery later)
        # from core.tasks import send_document_notification
        # send_document_notification.delay(document.id)
        
        return document
    
    def get_resident_documents_paginated(
        self,
        resident_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> Dict:
        """Get paginated documents for resident"""
        offset = (page - 1) * page_size
        documents, total = self.repository.get_documents_by_resident(
            resident_id,
            limit=page_size,
            offset=offset
        )
        
        return {
            'documents': documents,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }
    
    def get_overdue_count(self, use_cache: bool = True) -> int:
        """Get count of overdue documents (with caching)"""
        if use_cache:
            count = cache.get(self.CACHE_KEY_OVERDUE)
            if count is not None:
                return count
        
        count = self.repository.get_overdue_documents().count()
        cache.set(self.CACHE_KEY_OVERDUE, count, self.CACHE_TTL)
        return count
    
    def get_overdue_documents(self) -> List[Document]:
        """Get all overdue documents"""
        return list(self.repository.get_overdue_documents())
    
    def mark_document_as_paid(
        self,
        document_id: int,
        paid_by: User
    ) -> Document:
        """Mark document as paid with authorization check"""
        document = self.repository.get_document_by_id(document_id)
        
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Authorization check
        if not self._can_mark_as_paid(document, paid_by):
            raise PermissionError("Not authorized to mark this document as paid")
        
        # Update using transaction for data integrity
        with transaction.atomic():
            document.mark_as_paid()
            document.save()
        
        # Clear caches
        cache.delete(self.CACHE_KEY_OVERDUE)
        
        # Send notification
        # from core.tasks import send_payment_notification
        # send_payment_notification.delay(document.id)
        
        return document
    
    def _can_mark_as_paid(self, document: Document, user: User) -> bool:
        """Check if user can mark document as paid"""
        return (
            user.role in ['SUPERADMIN', 'SYNDIC'] or
            document.resident_id == user.id
        )
    
    def get_documents_summary(self, resident_id: int) -> Dict:
        """Get summary statistics for resident's documents"""
        documents = self.repository.get_resident_documents(resident_id)
        
        total = documents.count()
        paid = documents.filter(is_paid=True).count()
        unpaid = total - paid
        total_amount = sum(d.amount for d in documents)
        paid_amount = sum(d.amount for d in documents if d.is_paid)
        
        return {
            'total_documents': total,
            'paid_documents': paid,
            'unpaid_documents': unpaid,
            'total_amount': float(total_amount),
            'paid_amount': float(paid_amount),
            'unpaid_amount': float(total_amount - paid_amount)
        }
```

**4. DTO/Schema** (`finance/schemas/document_schema.py`):
```python
from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional
from decimal import Decimal

class DocumentCreateSchema(BaseModel):
    """Input validation schema"""
    title: str = Field(..., min_length=5, max_length=200)
    amount: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    date: date
    document_type: str = Field(..., regex="^(INVOICE|NOTICE|REMINDER|LEGAL|OTHER)$")
    resident_id: int = Field(..., gt=0)
    description: str = Field(default="", max_length=500)
    
    @validator('title')
    def title_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "title": "Facture charges Janvier 2024",
                "amount": 1500.00,
                "date": "2024-01-15",
                "document_type": "INVOICE",
                "resident_id": 5,
                "description": "Charges collectives"
            }
        }

class DocumentResponseSchema(BaseModel):
    """Serialized response"""
    id: int
    title: str
    amount: float
    date: date
    document_type: str
    is_paid: bool
    is_archived: bool
    created_at: str
    
    class Config:
        from_attributes = True
```

**5. Thin View** (`finance/api/v1/views.py`):
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from finance.models import Document
from finance.services.document_service import DocumentService
from finance.schemas.document_schema import DocumentCreateSchema
from .serializers import DocumentSerializer
from .permissions import IsDocumentOwnerOrSyndic

class DocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for documents.
    
    Thin controller - delegates to service layer
    """
    permission_classes = [IsAuthenticated, IsDocumentOwnerOrSyndic]
    serializer_class = DocumentSerializer
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = DocumentService()
    
    def get_queryset(self):
        """Filter documents based on user role"""
        user = self.request.user
        
        if user.role == 'RESIDENT':
            return Document.objects.filter(resident=user)
        elif user.role in ['SUPERADMIN', 'SYNDIC']:
            return Document.objects.all()
        
        return Document.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a new document"""
        try:
            schema = DocumentCreateSchema(**request.data)
            document = self.service.create_document(schema, request.user)
            serializer = self.get_serializer(document)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PermissionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
    
    def list(self, request, *args, **kwargs):
        """List documents with pagination"""
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        
        try:
            page = int(page)
            page_size = min(int(page_size), 100)  # Max 100 per page
        except ValueError:
            page = 1
            page_size = 20
        
        if request.user.role == 'RESIDENT':
            data = self.service.get_resident_documents_paginated(
                request.user.id,
                page=page,
                page_size=page_size
            )
            serializer = self.get_serializer(data['documents'], many=True)
            return Response({
                'results': serializer.data,
                'count': data['total'],
                'next': f"/api/v1/documents/?page={page+1}" if page < data['total_pages'] else None,
                'previous': f"/api/v1/documents/?page={page-1}" if page > 1 else None
            })
        
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get documents summary for current user"""
        if request.user.role != 'RESIDENT':
            return Response(
                {'error': 'Only residents can view their summary'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        summary = self.service.get_documents_summary(request.user.id)
        return Response(summary)
    
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        """Mark document as paid"""
        try:
            document = self.service.mark_document_as_paid(pk, request.user)
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except (ValueError, PermissionError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
```

---

## 2️⃣ PERMISSION & AUTHORIZATION SYSTEM

### Current Problem:
```python
# Current approach - scattered role checks
def dispatch(self, request, *args, **kwargs):
    if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
        return redirect('finance:home')
    return super().dispatch(request, *args, **kwargs)
```

### Solution: DRF Permissions + Custom Backend

**New file: `finance/permissions/object_permissions.py`:**
```python
from rest_framework.permissions import BasePermission
from django.contrib.auth import get_user_model

User = get_user_model()

class IsDocumentOwnerOrSyndic(BasePermission):
    """
    Custom permission: Document owner or SYNDIC can access
    """
    def has_object_permission(self, request, view, obj):
        # SUPERADMIN and SYNDIC can access everything
        if request.user.role in ['SUPERADMIN', 'SYNDIC']:
            return True
        
        # Residents can only access their own documents
        if request.user.role == 'RESIDENT':
            return obj.resident == request.user
        
        return False

class IsSyndicOrSuperAdmin(BasePermission):
    """Only SYNDIC and SUPERADMIN can perform action"""
    def has_permission(self, request, view):
        return request.user.role in ['SUPERADMIN', 'SYNDIC']

class IsResident(BasePermission):
    """Only residents can perform action"""
    def has_permission(self, request, view):
        return request.user.role == 'RESIDENT'

class IsOwner(BasePermission):
    """User must be the owner of the object"""
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user or request.user.role == 'SUPERADMIN'

class CanManageBuilding(BasePermission):
    """User must be the SYNDIC managing the building"""
    def has_permission(self, request, view):
        return request.user.role in ['SUPERADMIN', 'SYNDIC']
```

**New file: `finance/permissions/rbac.py`:**
```python
from enum import Enum
from typing import List

class Permission(Enum):
    """Define all system permissions"""
    # Document permissions
    CREATE_DOCUMENT = "create_document"
    VIEW_DOCUMENT = "view_document"
    EDIT_DOCUMENT = "edit_document"
    DELETE_DOCUMENT = "delete_document"
    
    # Payment permissions
    CREATE_PAYMENT = "create_payment"
    VERIFY_PAYMENT = "verify_payment"
    
    # Resident permissions
    VIEW_RESIDENT = "view_resident"
    CREATE_RESIDENT = "create_resident"
    EDIT_RESIDENT = "edit_resident"
    
    # Notification permissions
    SEND_NOTIFICATION = "send_notification"
    
    # Ticket permissions
    CREATE_TICKET = "create_ticket"
    ASSIGN_TICKET = "assign_ticket"

class Role(Enum):
    """User roles"""
    SUPERADMIN = "SUPERADMIN"
    SYNDIC = "SYNDIC"
    RESIDENT = "RESIDENT"

# Define role-based permissions
ROLE_PERMISSIONS = {
    Role.SUPERADMIN: [
        Permission.CREATE_DOCUMENT, Permission.VIEW_DOCUMENT,
        Permission.EDIT_DOCUMENT, Permission.DELETE_DOCUMENT,
        Permission.CREATE_PAYMENT, Permission.VERIFY_PAYMENT,
        Permission.VIEW_RESIDENT, Permission.CREATE_RESIDENT,
        Permission.SEND_NOTIFICATION, Permission.CREATE_TICKET,
        Permission.ASSIGN_TICKET
    ],
    Role.SYNDIC: [
        Permission.CREATE_DOCUMENT, Permission.VIEW_DOCUMENT,
        Permission.EDIT_DOCUMENT, Permission.CREATE_PAYMENT,
        Permission.VERIFY_PAYMENT, Permission.VIEW_RESIDENT,
        Permission.CREATE_RESIDENT, Permission.SEND_NOTIFICATION,
        Permission.CREATE_TICKET, Permission.ASSIGN_TICKET
    ],
    Role.RESIDENT: [
        Permission.VIEW_DOCUMENT, Permission.VIEW_RESIDENT,
        Permission.CREATE_TICKET
    ]
}

def has_permission(user, permission: Permission) -> bool:
    """Check if user has permission"""
    role = Role(user.role)
    return permission in ROLE_PERMISSIONS.get(role, [])
```

---

## 3️⃣ DATABASE QUERY OPTIMIZATION

### Problem Analysis:
```python
# N+1 query example (BAD)
documents = Document.objects.all()  # Query 1
for doc in documents:
    print(doc.resident.username)  # Query N - N+1 problem!
    print(doc.uploaded_by.email)  # More N+1!
```

### Solution: Smart Query Optimization

**Create: `finance/managers/document_manager.py`:**
```python
from django.db.models import Manager, QuerySet, Prefetch, Count, Q
from django.db.models import F, Case, When, DecimalField
from datetime import timedelta
from django.utils import timezone

class DocumentQuerySet(QuerySet):
    """Custom QuerySet with optimized queries"""
    
    def with_user_details(self):
        """Include related user details"""
        return self.select_related(
            'resident',
            'uploaded_by'
        )
    
    def with_payment_info(self):
        """Include payment-related data"""
        return self.select_related(
            'resident__payment_set'
        ).prefetch_related(
            'payment_set'
        )
    
    def for_resident(self, resident_id: int):
        """Filter for specific resident"""
        return self.filter(resident_id=resident_id).with_user_details()
    
    def unpaid_only(self):
        """Only unpaid documents"""
        return self.filter(is_paid=False)
    
    def overdue(self, days: int = 30):
        """Overdue documents"""
        cutoff = timezone.now().date() - timedelta(days=days)
        return self.filter(
            is_paid=False,
            date__lt=cutoff
        )
    
    def active(self):
        """Non-archived documents"""
        return self.filter(is_archived=False)
    
    def with_statistics(self):
        """Add aggregated statistics"""
        return self.annotate(
            total_amount=F('amount'),
            is_overdue=Case(
                When(
                    Q(is_paid=False) & Q(date__lt=timezone.now() - timedelta(days=30)),
                    then=True
                ),
                default=False
            )
        )

class DocumentManager(Manager):
    """Custom manager for Document model"""
    
    def get_queryset(self):
        return DocumentQuerySet(self.model, using=self._db)
    
    def with_user_details(self):
        return self.get_queryset().with_user_details()
    
    def for_resident(self, resident_id: int):
        return self.get_queryset().for_resident(resident_id)
    
    def overdue(self, days: int = 30):
        return self.get_queryset().overdue(days)
    
    def unpaid_documents(self):
        return self.get_queryset().unpaid_only().with_user_details()
```

**Update the Document model to use custom manager:**
```python
class Document(models.Model):
    # ... fields ...
    
    objects = DocumentManager()  # Add custom manager
    
    class Meta:
        # ... existing meta ...
```

**Usage in service:**
```python
# BEFORE (N+1 problem)
documents = Document.objects.all()
for doc in documents:
    print(doc.resident.username)

# AFTER (Optimized)
documents = Document.objects.with_user_details()  # 2 queries only!
for doc in documents:
    print(doc.resident.username)

# Get overdue documents optimized
overdue = Document.objects.overdue(days=30).with_user_details()
```

---

## 4️⃣ API VERSIONING & STANDARDIZED RESPONSES

### Problem: No versioning, inconsistent responses

### Solution:

**Create: `core/api/responses.py`:**
```python
from typing import Any, Optional, List
from rest_framework.response import Response
from rest_framework import status

class APIResponse:
    """Standardized API response builder"""
    
    @staticmethod
    def success(
        data: Any = None,
        message: str = "Success",
        status_code: int = status.HTTP_200_OK,
        meta: Optional[dict] = None
    ) -> Response:
        """Return success response"""
        return Response({
            'success': True,
            'message': message,
            'data': data,
            'meta': meta or {}
        }, status=status_code)
    
    @staticmethod
    def error(
        error: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[dict] = None,
        errors: Optional[List[dict]] = None
    ) -> Response:
        """Return error response"""
        return Response({
            'success': False,
            'error': error,
            'details': details or {},
            'errors': errors or []
        }, status=status_code)
    
    @staticmethod
    def paginated(
        results: List[Any],
        total: int,
        page: int,
        page_size: int,
        message: str = "Success"
    ) -> Response:
        """Return paginated response"""
        total_pages = (total + page_size - 1) // page_size
        return Response({
            'success': True,
            'message': message,
            'data': {
                'results': results,
                'pagination': {
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': total_pages,
                    'has_next': page < total_pages,
                    'has_previous': page > 1
                }
            }
        }, status=status.HTTP_200_OK)
```

**Create: `finance/api/v1/urls.py`:**
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, PaymentViewSet

# API v1 URLs
router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
]
```

**Create: `syndic/urls.py` (updated):**
```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API versioning
    path('api/v1/', include('finance.api.v1.urls')),
    path('api/v2/', include('finance.api.v2.urls')),  # Future
    
    # Legacy URLs (for compatibility)
    path('', include('finance.urls')),
    path('system/accounts/', include('accounts.urls')),
    path('system/residents/', include('residents.urls')),
    path('system/documents/', include('documents.urls')),
    path('system/notifications/', include('notifications.urls')),
    path('tickets/', include('tickets.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 5️⃣ JWT AUTHENTICATION

### Replace session-based with JWT:

**Settings: `syndic/settings/base.py`:**
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Keep for admin
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
```

**Create: `accounts/api/v1/serializers.py`:**
```python
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from accounts.models import User

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token with user details"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        refresh = self.get_token(self.user)
        data['access'] = str(refresh.access_token)
        data['refresh'] = str(refresh)
        
        # Add user info
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': self.user.role,
            'apartment': self.user.apartment
        }
        
        return data

class LoginSerializer(serializers.Serializer):
    """Login input validation"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
```

**Create: `accounts/api/v1/views.py`:**
```python
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from core.api.responses import APIResponse
from .serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    """JWT token endpoint"""
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return APIResponse.success(
            data=response.data,
            message="Login successful"
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """Logout - blacklist token"""
    # Token will auto-expire, but can implement blacklist
    return APIResponse.success(message="Logged out successfully")
```

---

## 6️⃣ ASYNC TASKS WITH CELERY

### Problem: Synchronous overdue detection blocks requests

### Solution:

**Install:** `pip install celery redis celery-beat`

**Create: `core/celery.py`:**
```python
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'syndic.settings.dev')

app = Celery('syndic')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks schedule
app.conf.beat_schedule = {
    'detect-overdue-payments': {
        'task': 'finance.tasks.detect_overdue_payments',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    'send-payment-reminders': {
        'task': 'finance.tasks.send_payment_reminders',
        'schedule': crontab(hour=10, minute=0, day_of_week='mon'),  # Weekly Monday
    },
    'generate-monthly-reports': {
        'task': 'finance.tasks.generate_monthly_reports',
        'schedule': crontab(0, 0, day_of_month=1),  # Monthly on 1st
    }
}
```

**Create: `finance/tasks.py`:**
```python
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta

from .services.document_service import DocumentService
from .services.notification_service import NotificationService

@shared_task
def detect_overdue_payments():
    """Detect and process overdue payments"""
    service = DocumentService()
    overdue_docs = service.get_overdue_documents()
    
    for document in overdue_docs:
        # Send notification to resident
        send_overdue_notification.delay(document.id)
        
        # Log operation
        from .models import OperationLog
        OperationLog.objects.create(
            action='OVERDUE_DETECTED',
            target_id=str(document.id),
            target_type='DOCUMENT',
            meta={'resident_id': document.resident_id}
        )
    
    return f"Processed {len(overdue_docs)} overdue documents"

@shared_task
def send_overdue_notification(document_id: int):
    """Send email notification for overdue document"""
    from .models import Document
    
    document = Document.objects.select_related('resident').get(id=document_id)
    
    context = {
        'resident_name': document.resident.get_full_name(),
        'document_title': document.title,
        'days_overdue': document.get_days_overdue(),
        'amount': document.amount,
    }
    
    html_message = render_to_string('emails/overdue_notification.html', context)
    
    send_mail(
        subject=f"Payment Reminder: {document.title}",
        message="",
        from_email='no-reply@syndic.local',
        recipient_list=[document.resident.email],
        html_message=html_message,
        fail_silently=True,
    )

@shared_task
def send_payment_reminders():
    """Send payment reminders to residents"""
    from .models import Document, Notification
    
    # Get documents due within 7 days
    cutoff = timezone.now().date() + timedelta(days=7)
    upcoming = Document.objects.filter(
        is_paid=False,
        date__lte=cutoff,
        date__gte=timezone.now().date()
    ).select_related('resident')
    
    for doc in upcoming:
        send_payment_reminder_email.delay(doc.id)

@shared_task
def generate_monthly_reports():
    """Generate monthly financial reports"""
    from .models import Document, Payment, Depense
    
    current_month = timezone.now().date().replace(day=1)
    
    # Calculate statistics
    docs = Document.objects.filter(created_at__date__gte=current_month)
    payments = Payment.objects.filter(payment_date__gte=current_month)
    expenses = Depense.objects.filter(date_depense__gte=current_month)
    
    # Generate report (save to database, send email, etc.)
    return "Monthlyreport generated"
```

**Settings: `syndic/settings/base.py`:**
```python
# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Casablanca'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
```

---

## 7️⃣ CACHING WITH REDIS

**Create: `core/cache.py`:**
```python
from django.core.cache import cache
from typing import Any, Optional
from functools import wraps
import hashlib
import json

class CacheManager:
    """Centralized cache management"""
    
    # Cache keys
    DOCUMENT_COUNT = "documents:count:{}"
    OVERDUE_COUNT = "documents:overdue:count"
    USER_NOTIFICATIONS = "notifications:user:{}"
    BUILDING_STATS = "building:stats:{}"
    
    # TTLs
    TTL_SHORT = 300  # 5 minutes
    TTL_MEDIUM = 3600  # 1 hour
    TTL_LONG = 86400  # 24 hours
    
    @staticmethod
    def get_or_set(key: str, func, timeout: int = 300):
        """Get from cache or set from function"""
        value = cache.get(key)
        if value is None:
            value = func()
            cache.set(key, value, timeout)
        return value
    
    @staticmethod
    def invalidate(pattern: str):
        """Invalidate cache keys matching pattern"""
        cache.delete_pattern(f"{pattern}*")

def cached_result(timeout: int = 300):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            key = f"{func.__name__}:{hashlib.md5(json.dumps(str(args) + str(kwargs)).encode()).hexdigest()}"
            
            result = cache.get(key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(key, result, timeout)
            
            return result
        return wrapper
    return decorator

# Usage in services
from core.cache import CacheManager, cached_result

class DocumentService:
    def get_overdue_count(self) -> int:
        return CacheManager.get_or_set(
            CacheManager.OVERDUE_COUNT,
            lambda: self.repository.get_overdue_documents().count(),
            timeout=CacheManager.TTL_SHORT
        )
    
    @cached_result(timeout=CacheManager.TTL_MEDIUM)
    def get_building_stats(self, building_id: int):
        return self.repository.get_building_stats(building_id)
```

---

# PHASE 2: CORE FEATURES

## 8️⃣ MULTI-TENANT SUPPORT

**Create: `core/middleware.py`:**
```python
from django.utils.functional import SimpleLazyObject
from .models import Building

def get_building(request):
    """Get building from subdomain or header"""
    # Extract from subdomain: building1.sandik.local
    host = request.get_host().split(':')[0]  # Remove port
    parts = host.split('.')
    
    if len(parts) > 2:  # Subdomain exists
        subdomain = parts[0]
        building = Building.objects.filter(subdomain=subdomain).first()
        return building
    
    # Fallback to header
    building_id = request.GET.get('building_id')
    if building_id:
        return Building.objects.filter(id=building_id).first()
    
    # Default first building for user
    if request.user and request.user.is_authenticated:
        return request.user.managedbuildings.first()
    
    return None

class BuildingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        request.building = SimpleLazyObject(lambda: get_building(request))
        response = self.get_response(request)
        return response
```

**Create: `core/models.py`:**
```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Building(models.Model):
    """Represents a building/syndicate"""
    name = models.CharField(max_length=200)
    subdomain = models.SlugField(unique=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    
    # Managers
    syndic = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='managed_buildings',
        limit_choices_to={'role': 'SYNDIC'}
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    logo = models.ImageField(upload_to='buildings/', null=True, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    
    # Billing
    subscription_plan = models.CharField(
        max_length=20,
        choices=[
            ('STARTER', 'Starter'),
            ('PRO', 'Pro'),
            ('ENTERPRISE', 'Enterprise')
        ],
        default='STARTER'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Buildings"
    
    def __str__(self):
        return self.name
```

**Update Document model for multi-tenancy:**
```python
class Document(models.Model):
    # ... existing fields ...
    
    # Add building reference
    building = models.ForeignKey(
        'core.Building',
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    class Meta:
        # ... existing meta ...
        # Ensure documents are unique per building
        unique_together = [['building', 'id']]
```

---

## 9️⃣ PAYMENT INTEGRATION (Stripe-like)

**Create: `payments/models.py`:**
```python
from django.db import models
from django.utils import timezone

class PaymentProvider(models.Model):
    """Payment provider configuration"""
    PROVIDERS = [
        ('STRIPE', 'Stripe'),
        ('PAYPAL', 'PayPal'),
        ('MAROC_TELECOM', 'Maroc Telecom'),
        ('MANUAL', 'Manual Transfer')
    ]
    
    provider = models.CharField(max_length=20, choices=PROVIDERS)
    api_key = models.CharField(max_length=255)  # Encrypted
    secret_key = models.CharField(max_length=255, blank=True)  # Encrypted
    webhook_secret = models.CharField(max_length=255, blank=True)
    
    is_active = models.BooleanField(default=True)

class PaymentIntent(models.Model):
    """Payment transaction"""
    STATUSES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded')
    ]
    
    document = models.ForeignKey(
        'finance.Document',
        on_delete=models.CASCADE,
        related_name='payment_intents'
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='MAD')
    
    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default='PENDING'
    )
    
    provider_transaction_id = models.CharField(max_length=255, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

**Create: `payments/services.py`:**
```python
from typing import Optional
from decimal import Decimal
import stripe

class PaymentService:
    """Handle all payment operations"""
    
    def __init__(self):
        stripe.api_key = os.getenv('STRIPE_API_KEY')
    
    def create_payment_intent(
        self,
        document_id: int,
        amount: Decimal,
        customer_email: str
    ) -> dict:
        """Create Stripe payment intent"""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency='mad',
                receipt_email=customer_email,
                metadata={'document_id': document_id}
            )
            
            return {
                'client_secret': intent.client_secret,
                'amount': amount,
                'status': 'created'
            }
        except stripe.error.StripeError as e:
            return {'error': str(e), 'status': 'failed'}
    
    def verify_payment(self, intent_id: str) -> bool:
        """Verify Stripe payment intent completion"""
        try:
            intent = stripe.PaymentIntent.retrieve(intent_id)
            return intent.status == 'succeeded'
        except stripe.error.StripeError:
            return False
```

---

## 🔟 REAL-TIME NOTIFICATIONS (WebSocket)

**Install:** `pip install channels channels-redis`

**Create: `core/asgi.py`:**
```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'syndic.settings.dev')

django_asgi_app = get_asgi_application()

from notifications.consumers import NotificationConsumer

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path('ws/notifications/', NotificationConsumer.as_asgi()),
        ])
    ),
})
```

**Create: `notifications/consumers.py`:**
```python
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_authenticated:
            self.user_group_name = f'user_{self.user.id}'
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
    
    # Handle messages from group
    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'message': event['message'],
            'data': event.get('data')
        }))

# Send notification to user
async def send_notification(user_id: int, message: str, data: dict = None):
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f'user_{user_id}',
        {
            'type': 'notification_message',
            'message': message,
            'data': data or {}
        }
    )
```

---

# PHASE 3 & 4: DEVOPS & DEPLOYMENT

## Complete Docker Setup

**Create: `Dockerfile`:**
```dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run migrations and start server
CMD ["gunicorn", "syndic.wsgi:application", "--bind", "0.0.0.0:8000"]
```

**Create: `docker-compose.yml`:**
```yaml
version: '3.9'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Django Web Server
  web:
    build: .
    environment:
      DEBUG: ${DEBUG}
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
    command: >
      sh -c "python manage.py migrate &&
             gunicorn syndic.wsgi:application --bind 0.0.0.0:8000"

  # Celery Worker
  celery:
    build: .
    environment:
      DEBUG: ${DEBUG}
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
    command: celery -A syndic worker -l info

  # Celery Beat (Scheduler)
  celery_beat:
    build: .
    environment:
      DEBUG: ${DEBUG}
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    depends_on:
      - postgres
      - redis
    volumes:
      - .:/app
    command: celery -A syndic beat -l info

volumes:
  postgres_data:
  redis_data:
```

---

## CI/CD Pipeline (GitHub Actions)

**Create: `.github/workflows/ci.yml`:**
```yaml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-django pytest-cov
    
    - name: Run migrations
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        DEBUG: False
        SECRET_KEY: test-key
      run: python manage.py migrate
    
    - name: Run tests with coverage
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        DEBUG: False
        SECRET_KEY: test-key
      run: pytest --cov=. --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to Railway/Render
      run: |
        # Your deployment script here
        echo "Deploying ${{ github.sha }}"
```

---

## Security Checklist

**Create: `.env.example`:**
```env
# Django
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=syndic_db
DB_USER=syndic_user
DB_PASSWORD=secure-password
DB_HOST=localhost
DB_PORT=5432

# Cache
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# JWT
JWT_SECRET_KEY=your-jwt-secret

# Stripe
STRIPE_API_KEY=sk_live_...
STRIPE_PUBLIC_KEY=pk_live_...

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Security
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
```

---

## Testing Structure

**Create: `tests/__init__.py`:**
```python
# Remove in __init__.py
```

**Create: `tests/test_document_service.py`:**
```python
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from finance.services.document_service import DocumentService
from finance.models import Document

User = get_user_model()

class DocumentServiceTest(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self):
        self.syndic = User.objects.create_user(
            username='syndic',
            email='syndic@test.com',
            password='test123',
            role='SYNDIC'
        )
        self.resident = User.objects.create_user(
            username='resident',
            email='resident@test.com',
            password='test123',
            role='RESIDENT'
        )
        self.service = DocumentService()
    
    def test_create_document(self):
        from finance.schemas.document_schema import DocumentCreateSchema
        
        schema = DocumentCreateSchema(
            title="Test Invoice",
            amount=1000.00,
            date="2024-01-15",
            document_type="INVOICE",
            resident_id=self.resident.id,
            description="Test"
        )
        
        doc = self.service.create_document(schema, self.syndic)
        
        assert doc.title == "Test Invoice"
        assert doc.amount == 1000.00
        assert doc.is_paid == False
    
    def test_overdue_calculation(self):
        from datetime import timedelta
        from django.utils import timezone
        
        # Create old unpaid document
        old_date = timezone.now().date() - timedelta(days=35)
        doc = Document.objects.create(
            title="Old Invoice",
            amount=500,
            date=old_date,
            document_type="INVOICE",
            resident=self.resident,
            uploaded_by=self.syndic
        )
        
        assert doc.is_overdue() == True
        assert doc.get_days_overdue() > 0
```

---

# BUSINESS STRATEGY

## SaaS Monetization Model

```
PRICING PLANS
├── Starter ($29/month)
│   ├─ 1 Building
│   ├─ Up to 100 Residents
│   ├─ Basic Dashboard
│   └─ Email Support
│
├── Pro ($99/month)
│   ├─ 5 Buildings
│   ├─ Up to 500 Residents
│   ├─ Advanced Analytics
│   ├─ Payment Integration
│   ├─ API Access
│   └─ Priority Support
│
└── Enterprise (Custom)
    ├─ Unlimited Buildings
    ├─ Unlimited Residents
    ├─ White Label
    ├─ Custom Integration
    └─ Dedicated Account Manager
```

**Key Metrics to Track:**
- Monthly Recurring Revenue (MRR)
- Customer Acquisition Cost (CAC)
- Lifetime Value (LTV)
- Churn Rate
- Active Users
- Payment Collection Rate

---

# PRIORITY IMPLEMENTATION ROADMAP

## Week 1-2: Critical Fixes
- [ ] Refactor to clean architecture
- [ ] Add Django REST Framework
- [ ] Implement custom permissions
- [ ] Optimize database queries

## Week 3-4: Core Features
- [ ] JWT authentication
- [ ] Celery async tasks
- [ ] Redis caching
- [ ] API versioning

## Week 5-6: Enhancement
- [ ] Multi-tenant support
- [ ] Stripe integration
- [ ] WebSocket notifications
- [ ] Advanced analytics

## Week 7+: Production
- [ ] Docker setup
- [ ] CI/CD pipeline
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Launch!

---

## Quick Start Commands

```bash
# Clone and setup
git clone <repo>
cd sandik-pro
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup Django
cp .env.example .env
# Edit .env with your settings
python manage.py migrate
python manage.py createsuperuser

# Run with Docker
docker-compose up

# Run tests
pytest --cov

# Run Celery
celery -A syndic worker -l info
celery -A syndic beat -l info
```

---

**Next Steps:**
1. Start with Phase 1 (Architecture refactoring)
2. Implement database optimizations first
3. Add authentication/permissions
4. Then tackle async tasks
5. Finally, add multi-tenancy

This roadmap will get your project to **production-grade quality** in 2 months!
