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
    get_myrain_pastweek,
    get_latest_realtime_data_for_timeseries_animation,
    get_radar_rainfall_summary_statistics
    
)

# -----------------------------------------------
# router for viewsets (low-level API endpoints)

router = ApiDefaultRouter()

router.register(r'gauges', GaugeGeoViewSet)
router.register(r'pixels', PixelGeoViewSet)
router.register(r'rainfall-events', RainfallEventViewset)

router.register(r'calibrated-radar', GarrRecordViewset)
router.register(r'calibrated-gauge', GaugeRecordViewset)
router.register(r'realtime-radar', RtrrRecordViewset)
router.register(r'realtime-gauge', RtrgRecordViewset)

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
    # custom routes

    path('v3/myrain/24hours/', get_myrain_24hours),
    path('v3/myrain/48hours/', get_myrain_48hours),
    path('v3/myrain/pastweek/', get_myrain_pastweek),

    path('v3/viz/realtime/', get_latest_realtime_data_for_timeseries_animation),
    path('v3/viz/radar-summary-stats/', get_radar_rainfall_summary_statistics),
    #path('v3/viz/radar-summary-stats/<hours>/', get_latest_radar_rainfall_summary_statistics),
    
    # --------------------------
    # low-level DRF-registered routes
    path('', include(router.urls))
]