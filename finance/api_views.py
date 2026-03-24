from django.http import JsonResponse
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from .services.navigation_service import build_navigation_stats


@method_decorator(login_required, name='dispatch')
class NavigationStatsAPI(View):
    """API pour les statistiques de navigation en temps réel"""
    
    def get(self, request):
        if request.user.role not in ['SUPERADMIN', 'SYNDIC']:
            return JsonResponse({'error': 'Accès non autorisé'}, status=403)
        
        try:
            stats = build_navigation_stats(request.user)
            return JsonResponse(stats)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
