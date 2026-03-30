from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import Http404
from .models import Building

class SyndicRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a SYNDIC or SUPERADMIN."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role in ['SYNDIC', 'SUPERADMIN']

class BuildingListView(LoginRequiredMixin, SyndicRequiredMixin, ListView):
    model = Building
    template_name = 'properties/building_list.html'
    context_object_name = 'buildings'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Gestion des Immeubles"
        context['page_actions'] = [
            {
                'label': 'Ajouter un immeuble',
                'url': reverse('properties:building_create'),
                'icon': 'fas fa-plus',
                'type': 'primary'
            }
        ]
        return context

class BuildingCreateView(LoginRequiredMixin, SyndicRequiredMixin, CreateView):
    model = Building
    template_name = 'properties/building_form.html'
    fields = ['name', 'address', 'total_apartments']
    success_url = reverse_lazy('properties:building_list')

    def form_valid(self, form):
        messages.success(self.request, f"L'immeuble '{form.instance.name}' a été créé avec succès.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Ajouter un immeuble"
        context['page_actions'] = [
            {
                'label': 'Retour à la liste',
                'url': reverse('properties:building_list'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        return context

class BuildingUpdateView(LoginRequiredMixin, SyndicRequiredMixin, UpdateView):
    model = Building
    template_name = 'properties/building_form.html'
    fields = ['name', 'address', 'total_apartments']
    success_url = reverse_lazy('properties:building_list')

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        if pk in (None, '', 'None', 'null'):
            raise Http404("Identifiant d'immeuble invalide")
        return super().get_object(queryset)

    def form_valid(self, form):
        messages.success(self.request, f"L'immeuble '{form.instance.name}' a été mis à jour.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Modifier {self.object.name}"
        context['page_actions'] = [
            {
                'label': 'Retour à la liste',
                'url': reverse('properties:building_list'),
                'icon': 'fas fa-arrow-left',
                'type': 'outline'
            }
        ]
        return context

class BuildingDeleteView(LoginRequiredMixin, SyndicRequiredMixin, DeleteView):
    model = Building
    template_name = 'properties/building_confirm_delete.html'
    success_url = reverse_lazy('properties:building_list')

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        if pk in (None, '', 'None', 'null'):
            raise Http404("Identifiant d'immeuble invalide")
        return super().get_object(queryset)

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"L'immeuble '{obj.name}' a été supprimé.")
        return super().delete(request, *args, **kwargs)
def redirect_building_list(request, *args, **kwargs):
    """Soft-redirect invalid building links back to the list."""
    return redirect('properties:building_list')
