from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils import timezone
import os


class User(AbstractUser):
    class Roles(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Super Administrateur"
        SYNDIC = "SYNDIC", "Syndic (Gestionnaire)"
        RESIDENT = "RESIDENT", "Résident"

    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.RESIDENT)
    apartment = models.CharField(max_length=50, blank=True, help_text="Appartement / Lot")
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_resident = models.BooleanField(default=False, help_text="Marque si c'est un résident")
    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='created_residents', 
                                 help_text="Utilisateur qui a créé ce compte")
    email_verified = models.BooleanField(default=False, help_text="Adresse email vérifiée")
    email_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = []
        if os.getenv("DB_ENGINE") != "django_mongodb_backend":
            constraints.append(
                models.UniqueConstraint(
                    fields=['apartment'],
                    condition=(Q(role='RESIDENT') & Q(apartment__isnull=False) & ~Q(apartment='')),
                    name='unique_apartment_per_resident',
                    violation_error_message="Un résident existe déjà pour cet appartement."
                )
            )
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['is_active', 'role']),
        ]

    def __str__(self) -> str:
        full = self.get_full_name().strip() or self.username
        return f"{full} ({self.apartment})" if self.apartment else full

    def clean(self):
        """Validate the user data"""
        super().clean()
        
        # Check email uniqueness manually for MongoDB
        if self.email:
            existing_email = User.objects.filter(email=self.email).exclude(pk=self.pk)
            if existing_email.exists():
                raise ValidationError({'email': f'Un utilisateur avec l\'email {self.email} existe déjà.'})

        # Check username uniqueness manually for MongoDB
        if self.username:
            existing_username = User.objects.filter(username=self.username).exclude(pk=self.pk)
            if existing_username.exists():
                raise ValidationError({'username': f'Le nom d\'utilisateur {self.username} est déjà pris.'})
        
        # Check apartment uniqueness for residents
        if self.role == self.Roles.RESIDENT and self.apartment:
            existing_resident = User.objects.filter(
                role=self.Roles.RESIDENT, 
                apartment=self.apartment
            ).exclude(pk=self.pk)
            
            if existing_resident.exists():
                raise ValidationError({
                    'apartment': f'Un résident existe déjà pour l\'appartement {self.apartment}'
                })
    
    def save(self, *args, **kwargs):
        # Auto-set is_resident based on role
        self.is_resident = (self.role == self.Roles.RESIDENT)
        
        # Validate before saving
        self.clean()
        
        # Normalize verification fields
        if self.email_verified and self.email_verified_at is None:
            self.email_verified_at = timezone.now()
        if not self.email_verified:
            self.email_verified_at = None
        
        super().save(*args, **kwargs)

    @property
    def can_manage_residents(self):
        """Check if user can manage residents"""
        return self.role in [self.Roles.SUPERADMIN, self.Roles.SYNDIC]

    @property
    def can_manage_finances(self):
        """Check if user can manage finances"""
        return self.role in [self.Roles.SUPERADMIN, self.Roles.SYNDIC]

    @property
    def can_send_notifications(self):
        """Check if user can send notifications"""
        return self.role in [self.Roles.SUPERADMIN, self.Roles.SYNDIC]

    @property
    def can_view_own_data_only(self):
        """Check if user can only view their own data"""
        return self.role == self.Roles.RESIDENT
