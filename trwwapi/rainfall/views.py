from datetime import timedelta
from collections import OrderedDict
import json

from django.utils.safestring import mark_safe
from django.core.paginator import Paginator
from django.utils.functional import cached_property
from django_filters import filters
from django.contrib.gis.geos import Point
from django.shortcuts import render
from django.utils import timezone

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.filters import SearchFilter
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework import viewsets, permissions, routers
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination, CursorPagination 
from django_filters.rest_framework import FilterSet, DjangoFilterBackend

from dateutil.parser import parse

from .serializers import (
    GaugeSerializer,
    PixelSerializer,
    GarrRecordSerializer, 
    GaugeRecordSerializer,
    RtrgRecordSerializer, 
    RainfallEventSerializer,
    RtrrRecordSerializer,
    GarrRecordSerializer,
    GaugeRecordSerializer,
    RtrrRecordSerializer,
    RtrgRecordSerializer
)
from .services import (
    handle_request_for,
    myrain_for,
    latest_timestamps_for_all_models,
    latest_realtime_rainfall_as_gdf,
    radar_rainfall_summary_statistics,
    latest_radar_rainfall_summary_statistics
)
from .models import (
    GarrRecord, 
    GaugeRecord, 
    RtrrRecord,
    RtrgRecord,
    RainfallEvent, 
    Pixel, 
    Gauge
)

from ..common.config import DELIMITER, TZ, TZI
from ..common.models import TrwwApiResponseSchema


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
# ASYNCHRONOUS API VIEWS
# these views are for the big, long-running queries. Each view can be polled 
# for job status and, when the query as completed or failed, results or an error
#  message, respectively.

class RainfallGaugeApiView(GenericAPIView):
    """Rain Gauge data, fully QA/QC'd and provided by 3RWW + ALCOSAN.
    """

    def post(self, request, *args, **kwargs):
        return handle_request_for(GaugeRecord, request, *args, **kwargs)


class RainfallGarrApiView(GenericAPIView):
    """Gauge-Adjusted Radar Rainfall Data. Radar-based rainfall estimated calibrated with rain gauges, interpolated to 1km pixels. Historic data only. Provided by Vieux Associates.
    """

    def post(self, request, *args, **kwargs):
        return handle_request_for(GarrRecord, request, *args, **kwargs)


class RainfallRtrrApiView(GenericAPIView):
    """Real-time Radar Rainfall data. Provided through Vieux Associates. Data is provisional and has not be through a QA/QC process.
    """        

    def post(self, request, *args, **kwargs):
        return handle_request_for(RtrrRecord, request, *args, **kwargs)


class RainfallRtrgApiView(GenericAPIView):
    """Real-time Rain Gauge data. Provided through Datawise. Data is provisional and has not be through a QA/QC process.
    """    

    def post(self, request, *args, **kwargs):
        return handle_request_for(RtrgRecord, request, *args, **kwargs)


# -------------------------------------------------------------------
# SYNCHRONOUS API VIEWS - views on tables
# These return data from the tables in the database as-is.
# They show up in the django-rest-framework's explorable API pages.
# All rainfall data accessed from these views is paginated.

# --------------------
# ViewSet Pagination:

class FasterDjangoPaginator(Paginator):
    @cached_property
    def count(self):
        # only select 'id' for counting, much cheaper
        #return self.object_list.values('id').count()
        return len(self.object_list)

class NoCountPaginator(Paginator):
    def count(self):
        return 0

class PixelResultsSetPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = 'page_size'
    max_page_size = 3

class PixelResultsSetPagination2(CursorPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    ordering = ['ts']
    # django_paginator_class = NoCountPaginator
    # def get_paginated_response(self, data):
    #     return Response(OrderedDict([
    #         ('next', self.get_next_link()),
    #         ('previous', self.get_previous_link()),
    #         ('results', data)
    #     ]))

class GaugeResultsSetPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 10

class GaugeResultsSetPagination2(CursorPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    ordering = ['ts']

# --------------------
# ViewSet Filters: Events

class RainfallEventFilter(FilterSet):
    event_after = filters.DateFilter(field_name="start_dt", lookup_expr="gte")
    event_before = filters.DateFilter(field_name="end_dt", lookup_expr="lte")
    
    class Meta:
        model = RainfallEvent
        fields = ['event_label', 'start_dt', 'end_dt']


class RainfallEventViewset(viewsets.ReadOnlyModelViewSet):
    """Get a lists of rainfall event time periods in Allegheny County since 2000. Events are identified by Vieux Associates; more detail on each event is provided in Vieux's monthly report to 3 Rivers Wet Weather. Please note that the list is not comprehensive.
    """

    queryset = RainfallEvent.objects.all()
    serializer_class = RainfallEventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'event_label'
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RainfallEventFilter

# --------------------
# ViewSet Filters: Rainfall Records

class RainfallRecordFilter(FilterSet):
    start_dt = filters.DateTimeFilter(field_name="ts", lookup_expr="gt")
    end_dt = filters.DateTimeFilter(field_name="ts", lookup_expr="lte")

class GaugeRecordFilter(RainfallRecordFilter):
    gauge = filters.TypedMultipleChoiceFilter(
        field_name="sid",
        choices=[(i.web_id, "{0}: {1}".format(i.web_id, i.name)) for i in Gauge.objects.all().order_by('web_id')]
    )
    class Meta:
        model = GaugeRecord
        fields = ['gauge', 'start_dt', 'end_dt']

class RtrgRecordFilter(RainfallRecordFilter):
    gauge = filters.TypedMultipleChoiceFilter(
        field_name="sid",
        choices=[(i.web_id, "{0}: {1}".format(i.web_id, i.name)) for i in Gauge.objects.all().order_by('web_id')]
    )
    class Meta:
        model = RtrgRecord
        fields = ['gauge', 'start_dt', 'end_dt']

class RtrrRecordFilter(RainfallRecordFilter):
    pixel = filters.TypedMultipleChoiceFilter(
        field_name="sid",
        choices=[(i.pixel_id, i.pixel_id) for i in Pixel.objects.all().order_by('pixel_id')]
    )
    class Meta:
        model = RtrrRecord
        fields = ['pixel', 'start_dt', 'end_dt']

class GarrRecordFilter(RainfallRecordFilter):
    pixel = filters.TypedMultipleChoiceFilter(
        field_name="sid",
        choices=[(i.pixel_id, i.pixel_id) for i in Pixel.objects.all().order_by('pixel_id')]
    )
    class Meta:
        model = GarrRecord
        fields = ['pixel', 'start_dt', 'end_dt']


# --------------------
# Default Rainfall Record Viewsets

class RainfallRecordReadOnlyViewset(viewsets.ReadOnlyModelViewSet):
    """parent class, provides shared properties for the default rainfall record model-based viewsets"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'timestamp'
    filter_backends = (DjangoFilterBackend,)


class GarrRecordViewset(RainfallRecordReadOnlyViewset):
    """
    Get calibrated, gauge-adjusted radar rainfall observations for 15-minute time intervals. Data created by Vieux Associates for 3 Rivers Wet Weather from available NEXRAD and local rain gauges.

    Note: use available time- and pixel-based filtering options to get useful subsets of this data.
    """    
    queryset = GarrRecord.objects.all()
    serializer_class  = GarrRecordSerializer
    filterset_class = GarrRecordFilter
    pagination_class = PixelResultsSetPagination2


class GaugeRecordViewset(RainfallRecordReadOnlyViewset):
    """
    Get QA/QC'd rainfall gauge observations for 15-minute time intervals. Data captured by 3 Rivers Wet Weather and ALCOSAN.

    Note: use available time- and gauge-based filtering options to get useful subsets of this data.
    """
    queryset = GaugeRecord.objects.all()
    serializer_class  = GaugeRecordSerializer
    filterset_class = GaugeRecordFilter
    pagination_class = GaugeResultsSetPagination2


class RtrrRecordViewset(RainfallRecordReadOnlyViewset):
    """
    Get real-time radar rainfall observations for 15-minute time intervals. Data captured by Vieux Associates from NEXRAD radar in Moon Township, PA for 3 Rivers Wet Weather. Please note that this data is provisional.

    Note: use available time- and pixel-based filtering options to get useful subsets of this data.
    """
    queryset = RtrrRecord.objects.all()
    serializer_class  = RtrrRecordSerializer
    filterset_class = RtrrRecordFilter
    pagination_class = PixelResultsSetPagination2


class RtrgRecordViewset(RainfallRecordReadOnlyViewset):
    """
    Get real-time rainfall gauge observations for 15-minute time intervals. Data captured by 3 Rivers Wet Weather and Datawise. Please note that this data is provisional and that observations may be missing due to technical/transmission difficulties.

    Note: use available time- and gauge-based filtering options to get useful subsets of this data.
    """
    queryset = RtrgRecord.objects.all()
    serializer_class  = RtrgRecordSerializer
    filterset_class = RtrgRecordFilter
    pagination_class = GaugeResultsSetPagination2

# --------------------
# Sensor Geography Viewsets

class GaugeGeoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Gauge.objects.all()
    serializer_class = GaugeSerializer
    filter_backends = [SearchFilter]
    search_fields = ['active']

class ActiveGaugeGeoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Gauge.objects.filter()
    serializer_class = GaugeSerializer
    def get_queryset(self):
        # filter queryset for active gauges
        return self.queryset.filter(active=True)

class PixelGeoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Pixel.objects.all()
    serializer_class = PixelSerializer


# -------------------------------------------------------------------
# Rainfall metadata  

class LatestObservationTimestampsSummary(viewsets.ReadOnlyModelViewSet):
    """provides a lookup of the last date/time of data available for each of the
    rainfall sensor data types, as well as the timestamp of the last logged 
    event
    """
    def retrieve(self, request, format=None):
        summary = latest_timestamps_for_all_models()
        return Response(summary)

    def list(self, request, format=None):
        summary = latest_timestamps_for_all_models()
        return Response(summary)

# -------------------------------------------------------------------
# Rainfall summaries as text

def get_myrain_24hours(request):
    lat, lng, srid = request.GET.get('lat'), request.GET.get('lng'), request.GET.get('srid')
    text = myrain_for(lat, lng, srid, timedelta(days=1), "over the past 24 hours")
    return render(request, 'speech.html', {"text": text})
    
def get_myrain_48hours(request):
    lat, lng, srid = request.GET.get('lat'), request.GET.get('lng'), request.GET.get('srid')
    text = myrain_for(lat, lng, srid, timedelta(days=2), "over the past 48 hours")
    return render(request, 'speech.html', {"text": text})

def get_myrain_pastweek(request):
    lat, lng, srid = request.GET.get('lat'), request.GET.get('lng'), request.GET.get('srid')
    text = myrain_for(lat, lng, srid, timedelta(days=7), "over the past week")
    return render(request, 'speech.html', {"text": text})

# -------------------------------------------------------------------
# Rainfall summaries for AGO

@api_view(["GET"])
def get_latest_realtime_data_for_timeseries_animation(request:Request):
    """get 

    Args:
        hours (float): hours before now to get rainfall, defaults to 2
        format (str): output format "json" or "html". defaults to json
        f (str): "geojson" will return response as GeoJSON. If not provided, returns as an object with columns property and data property, the latter being a 2D array

    Returns:
        JSON: "GeoJSON" or a "split" columns/data object
    """
    hours = request.GET.get("hours", 2)
    f = request.GET.get("f", "split")
    
    gdf = latest_realtime_rainfall_as_gdf(hours=float(hours))

    if f == "geojson":
        r = json.loads(
            gdf.to_json(drop_id=True)
        )
        return Response(r)

    else: #elif f == "split"
        # separate x and y columns from wkt column
        gdf['x'] = gdf['wkt'].x
        gdf['y'] = gdf['wkt'].y
        # remove wkt column
        gdf.drop(columns=["wkt"], inplace=True)
        # convert to 2D columns array
        r = gdf.to_dict(orient="split")
        i = r.pop("index")

        x = TrwwApiResponseSchema(
                args=request.query_params,
                data=r
            )
        return Response(TrwwApiResponseSchema.Schema().dump(x))



@api_view(["GET"])
def get_radar_rainfall_summary_statistics(request:Request):
    """_summary_

    Args:
        start_dt (datetime): _description_
        end_dt (datetime): _description_
        pixels (string): comma-delimited list of radar pixel IDs
    """

    # get required parameters and handle if not provided
    try:
        start_dt = request.query_params.get("start_dt", None)
        # start_dt = timezone.localtime(parse(start_dt), TZ)
        start_dt = parse(start_dt).astimezone(TZI)
        end_dt = request.GET.get("end_dt", None)
        # end_dt = timezone.localtime(parse(end_dt), TZ)
        end_dt = parse(end_dt).astimezone(TZI)
    except Exception as e:
        r = TrwwApiResponseSchema(
            args=request.query_params,
            status_code=status.HTTP_400_BAD_REQUEST, 
            status='fail',
            messages=[
                e,
                "Must provide start date/time (`start_dt`) and ending datetime (`end_dt`) query string parameters."
            ]
        )
        return Response(
            data=TrwwApiResponseSchema.Schema().dump(r), 
            status=r.status_code
        )

    # parse optional pixels parameter

    pixels = request.query_params.get("pixels", None)
    if pixels:
        sensor_ids = [str(i) for i in pixels.split(DELIMITER)]
    else:
        sensor_ids = None
    
    results = radar_rainfall_summary_statistics(
        start_dt=start_dt,
        end_dt=end_dt,
        sensor_ids=sensor_ids
    )

    data = [r for r in results]

    if data:
        r = TrwwApiResponseSchema(
            args=request.query_params,
            data=data
        )
    else:
        r = TrwwApiResponseSchema(
            args=request.query_params,
            status_code=status.HTTP_204_NO_CONTENT, 
            status='fail',
            messages=["No data returned"]
        )
    
    return Response(
        data=TrwwApiResponseSchema.Schema().dump(r),
        status=r.status_code
    )