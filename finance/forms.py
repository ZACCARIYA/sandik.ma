"""Django forms for finance app."""

from django import forms
from django.forms import ModelForm
from .models import Document


class DocumentForm(ModelForm):
    """Form for creating and updating documents."""
    
    date = forms.DateField(
        label="Date du Document",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'required': 'required'
        }),
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'],
        help_text="Format: YYYY-MM-DD"
    )
    
    class Meta:
        model = Document
        fields = ['title', 'file', 'amount', 'date', 'document_type', 'resident', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Facture charges Janvier 2024'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'document_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'resident': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Informations supplémentaires sur ce document'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.png'
            })
        }
