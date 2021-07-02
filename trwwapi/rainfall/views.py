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

from ..common.config import TZI
# from .api_v2.config import TZI

from .serializers import (
    GarrObservationSerializer,
    GarrRecordSerializer, 
    GaugeObservationSerializer,
    GaugeRecordSerializer,
    RtrgRecordSerializer, 
    RtrrObservationSerializer, 
    RtrgObservationSerializer,
    RainfallEventSerializer,
    RtrrRecordSerializer,
    GarrRecordSerializer,
    GaugeRecordSerializer,
    RtrrRecordSerializer,
    RtrgRecordSerializer
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
    GarrRecord, 
    GaugeObservation,
    GaugeRecord, 
    RtrrObservation, 
    RtrrRecord,
    RtrgObservation,
    RtrgRecord,
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
        text = "<p>The 3RWW Rainfall API provides access to real-time (provisional) and historic (calibrated) rainfall data for the physical rain gauges and 'virtual' gauges (calibrated radar pixels) in Allegheny County.</p><p>3 Rivers Wet Weather, with support from Vieux Associates, uses calibrated data from the NEXRAD radar located in Moon Township, PA with rain gauge measurements collected during the same time period and rain event for every square kilometer in Allegheny County. The resulting rainfall data is equivalent in accuracy to having 2,276 rain gauges placed across the County. Since April 2000, 3 Rivers has accumulated a massive repository of this high resolution spatiotemporal calibrated radar rainfall data for Allegheny County, which now includes nearly 2 billion data points.</p>"
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
    """Rain Gauge data, fully QA/QC'd and provided by 3RWW + ALCOSAN.
    """

    # def get(self, request, *args, **kwargs):
    #     return handle_request_for(GaugeObservation, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return handle_request_for(GaugeObservation, request, *args, **kwargs)


class RainfallGarrApiView(GenericAPIView):
    """Gauge-Adjusted Radar Rainfall Data. Radar-based rainfall estimated calibrated with rain gauges, interpolated to 1km pixels. Historic data only. Provided by Vieux Associates.
    """

    # def get(self, request, *args, **kwargs):
    #     return handle_request_for(GarrObservation, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return handle_request_for(GarrObservation, request, *args, **kwargs)


class RainfallRtrrApiView(GenericAPIView):
    """Real-time Radar Rainfall data. Provided through Vieux Associates. Data is provisional and has not be through a QA/QC process.
    """        

    # def get(self, request, *args, **kwargs):
    #     return handle_request_for(RtrrObservation, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return handle_request_for(RtrrObservation, request, *args, **kwargs)


class RainfallRtrgApiView(GenericAPIView):
    """Real-time Rain Gauge data. Provided through Datawise. Data is provisional and has not be through a QA/QC process.
    """    

    # def get(self, request, *args, **kwargs):
    #     return handle_request_for(RtrgObservation, request, *args, **kwargs)

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
    """
    Get a lists of rainfall event time periods in Allegheny County since 2000. Events are identified by Vieux Associates; more detail on each event is provided in Vieux's monthly report to 3 Rivers Wet Weather. Please note that the list is not comprehensive.
    """

    queryset = RainfallEvent.objects.all()
    serializer_class = RainfallEventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'event_label'
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RainfallEventFilter


class GarrRecordViewset(viewsets.ReadOnlyModelViewSet):
    """
    Get calibrated, gauge-adjusted radar rainfall observations for 15-minute time intervals. Data created by Vieux Associates for 3 Rivers Wet Weather from available NEXRAD and local rain gauges.
    """    
    queryset = GarrRecord.objects.all()
    serializer_class  = GarrRecordSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'timestamp'
    pagination_class = PixelResultsSetPagination


class GaugeRecordViewset(viewsets.ReadOnlyModelViewSet):
    """
    Get QA/QC'd rainfall gauge observations for 15-minute time intervals. Data captured by 3 Rivers Wet Weather and ALCOSAN.
    """
    queryset = GaugeRecord.objects.all()
    serializer_class  = GaugeRecordSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field='timestamp'
    pagination_class = GaugeResultsSetPagination

class RtrrRecordViewset(viewsets.ReadOnlyModelViewSet):
    """
    Get real-time radar rainfall observations for 15-minute time intervals. Data captured by Vieux Associates from NEXRAD radar in Moon Township, PA for 3 Rivers Wet Weather. Please note that this data is provisional.
    """  
    queryset = RtrrRecord.objects.all()
    serializer_class  = RtrrRecordSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field='timestamp'
    pagination_class = PixelResultsSetPagination

class RtrgRecordViewset(viewsets.ReadOnlyModelViewSet):
    """
    Get real-time rainfall gauge observations for 15-minute time intervals. Data captured by 3 Rivers Wet Weather and Datawise. Please note that this data is provisional and that observations may be missing due to technical/transmission difficulties.
    """
    queryset = RtrgRecord.objects.all()
    serializer_class  = RtrgRecordSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field='timestamp'
    pagination_class = GaugeResultsSetPagination

# -------------------------------------------------------------------
# HELPER VIEWS
# These provide helpers for specific use cases

# @api_view(['GET'])
# def get_latest_observation_timestamps_summary(request):
class LatestObservationTimestampsSummary(viewsets.ReadOnlyModelViewSet):
    
    def list(self, request, format=None):
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