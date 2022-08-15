from django.urls import path, include
from rest_framework.schemas import get_schema_view
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

# high-level endpoints
from .views import ApiDefaultRouter
from .views import (
    RainfallGarrApiView,
    RainfallGaugeApiView,
    RainfallRtrrApiView,
    RainfallRtrgApiView,
    GarrRecordViewset,
    GaugeRecordViewset,
    RtrrRecordViewset,
    RtrgRecordViewset,
    GaugeGeoViewSet,
    PixelGeoViewSet,
    RainfallEventViewset,
    LatestObservationTimestampsSummary,
    get_myrain_24hours,
    get_myrain_48hours,
    get_myrain_pastweek
)

# -----------------------------------------------
# router for viewsets (low-level API endpoints)

router = ApiDefaultRouter()
router.register(r'calibrated-radar', GarrRecordViewset)
router.register(r'calibrated-gauge', GaugeRecordViewset)
router.register(r'realtime-radar', RtrrRecordViewset)
router.register(r'realtime-gauge', RtrgRecordViewset)
router.register(r'rainfall-events', RainfallEventViewset)
router.register(r'gauges', GaugeGeoViewSet)
router.register(r'pixels', PixelGeoViewSet)
router.register(r'v2/latest-observations', LatestObservationTimestampsSummary, basename='latest_observations')

# -----------------------------------------------
# API URLs for high-level endpoints

urlpatterns = [
    
    # --------------------------
    # custom asynchronous views

    # GARR
    path('v2/pixel/historic/', RainfallGarrApiView.as_view()),
    path('v2/pixel/historic/<str:jobid>/', RainfallGarrApiView.as_view()),
    # RTRR
    path('v2/pixel/realtime/', RainfallRtrrApiView.as_view()),
    path('v2/pixel/realtime/<str:jobid>/', RainfallRtrrApiView.as_view()),
    # GAUGE
    path('v2/gauge/historic/', RainfallGaugeApiView.as_view()),
    path('v2/gauge/historic/<str:jobid>/', RainfallGaugeApiView.as_view()),
    #RTRG
    path('v2/gauge/realtime/', RainfallRtrgApiView.as_view()),
    path('v2/gauge/realtime/<str:jobid>/', RainfallRtrgApiView.as_view()),

    # --------------------------
    # custom routes (for function-based views)

    path('v3/myrain/24hours/', get_myrain_24hours),
    path('v3/myrain/48hours/', get_myrain_48hours),
    path('v3/myrain/pastweek/', get_myrain_pastweek),
    
    # --------------------------
    # low-level DRF-registered routes
    path('', include(router.urls))
]