from django.db import models

class Building(models.Model):
    """Représente un immeuble géré par le syndic."""
    name = models.CharField(max_length=200, verbose_name="Nom de l'immeuble")
    address = models.TextField(verbose_name="Adresse")
    total_apartments = models.PositiveIntegerField(verbose_name="Nombre d'appartements")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Immeuble"
        verbose_name_plural = "Immeubles"
        ordering = ['name']

    def __str__(self):
        return self.name
