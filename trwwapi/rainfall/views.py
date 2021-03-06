# from django.contrib.auth.models import User, Group
from django.utils.safestring import mark_safe
from django.conf import settings
from django_filters import filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework import viewsets, permissions, routers
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import FilterSet, DjangoFilterBackend

from .api_civicmapper.config import TZI

from .serializers import (
    GarrObservationSerializer, 
    GaugeObservationSerializer, 
    RtrrObservationSerializer, 
    RtrgObservationSerializer,
    RainfallEventSerializer
)
from .selectors import (
    handle_request_for,
    get_latest_garrobservation,
    get_latest_gaugeobservation,
    get_latest_rainfallevent,
    get_latest_rtrgobservation,
    get_latest_rtrrobservation
)
from .models import (
    GarrObservation, 
    GaugeObservation, 
    RtrrObservation, 
    RtrgObservation,
    RainfallEvent, 
    Pixel, 
    Gauge
)


# -------------------------------------------------------------------
# API ROOT VIEW

class ApiRouterRootView(routers.APIRootView):
    """
    Controls appearance of the API root view
    """

    def get_view_name(self):
        return "3RWW Rainfall Data API"

    def get_view_description(self, html=False):
        text = "Get 3RWW high-resolution rainfall data"
        if html:
            return mark_safe(f"<p>{text}</p>")
        else:
            return text

class ApiDefaultRouter(routers.DefaultRouter):
    APIRootView = ApiRouterRootView

# -------------------------------------------------------------------
# HIGH-LEVEL API VIEWS
# these are the views that do the work for us

class RainfallGaugeApiView(GenericAPIView):

    def get(self, request, *args, **kwargs):
        return handle_request_for(GaugeObservation, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return handle_request_for(GaugeObservation, request, *args, **kwargs)


class RainfallGarrApiView(GenericAPIView):

    def get(self, request, *args, **kwargs):
        return handle_request_for(GarrObservation, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return handle_request_for(GarrObservation, request, *args, **kwargs)


class RainfallRtrrApiView(GenericAPIView):

    def get(self, request, *args, **kwargs):
        return handle_request_for(RtrrObservation, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return handle_request_for(RtrrObservation, request, *args, **kwargs)


class RainfallRtrgApiView(GenericAPIView):

    def get(self, request, *args, **kwargs):
        return handle_request_for(RtrgObservation, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return handle_request_for(RtrgObservation, request, *args, **kwargs)


# -------------------------------------------------------------------
# LOW LEVEL API VIEWS
# These return paginated data from the tables in the database as-is.
# They show up in the django-rest-framework's explorable API pages.

class PixelResultsSetPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = 'page_size'
    max_page_size = 3

class GaugeResultsSetPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 10

class RainfallEventFilter(FilterSet):
    event_after = filters.DateFilter(field_name="start_dt", lookup_expr="gte")
    event_before = filters.DateFilter(field_name="end_dt", lookup_expr="lte")
    
    class Meta:
        model = RainfallEvent
        fields = ['event_label', 'start_dt', 'end_dt']

class RainfallEventViewset(viewsets.ReadOnlyModelViewSet):
    queryset = RainfallEvent.objects.all()
    serializer_class = RainfallEventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'event_label'
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RainfallEventFilter


class GarrObservationViewset(viewsets.ReadOnlyModelViewSet):
    queryset = GarrObservation.objects.all()
    serializer_class  = GarrObservationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'timestamp'
    pagination_class = PixelResultsSetPagination


class GaugeObservationViewset(viewsets.ReadOnlyModelViewSet):
    queryset = GaugeObservation.objects.all()
    serializer_class  = GaugeObservationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field='timestamp'
    pagination_class = GaugeResultsSetPagination

class RtrrObservationViewset(viewsets.ReadOnlyModelViewSet):
    queryset = RtrrObservation.objects.all()
    serializer_class  = RtrrObservationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field='timestamp'
    pagination_class = PixelResultsSetPagination

class RtrgbservationViewset(viewsets.ReadOnlyModelViewSet):
    queryset = RtrgObservation.objects.all()
    serializer_class  = RtrgObservationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field='timestamp'
    pagination_class = GaugeResultsSetPagination

# -------------------------------------------------------------------
# HELPER VIEWS
# These provide helpers for specific use cases

@api_view(['GET'])
def get_latest_observation_timestamps_summary(request):
    
    raw_summary = {
        "calibrated-radar": get_latest_garrobservation(),
        "calibrated-gauge": get_latest_gaugeobservation(),
        "realtime-radar": get_latest_rtrrobservation(),
        "realtime-gauge": get_latest_rtrgobservation(),
        "rainfall-events": get_latest_rainfallevent(),
    }

    summary = {
        k: v.timestamp.astimezone(TZI).isoformat() if v is not None else None
        for k, v in 
        raw_summary.items()
    }

    return Response(summary)