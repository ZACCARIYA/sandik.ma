from django import forms
from .models import Document, Event

class DocumentForm(forms.ModelForm):
    """Form to create/update documents with proper widgets for better UX."""
    
    class Meta:
        model = Document
        fields = ['title', 'file', 'amount', 'date', 'document_type', 'resident', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'resident': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

class EventForm(forms.ModelForm):
    """Form to create/update events with HTML5 datetime-local widgets."""
    
    class Meta:
        model = Event
        fields = ['title', 'description', 'event_type', 'start_at', 'end_at', 'audience', 'participants', 'reminder_minutes_before']
        widgets = {
            'start_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'participants': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
