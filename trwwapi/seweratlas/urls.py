from django.urls import path, include

from .views import atlas_auth, ApiDefaultRouter

router = ApiDefaultRouter()

urlpatterns = [
    # --------------------------
    # DRF-registered routes
    path('', include(router.urls)),
    # --------------------------
    # custom routes (for function-based views)    
    path('auth/', atlas_auth, name='atlas_auth')
]