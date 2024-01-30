from datetime import timedelta
from collections import OrderedDict
import json

from django.utils.safestring import mark_safe
from django.core.paginator import Paginator
from django.utils.functional import cached_property
from django_filters import filters
from django.contrib.gis.geos import Point
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework import viewsets, permissions, routers
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination, CursorPagination 
from django_filters.rest_framework import FilterSet, DjangoFilterBackend


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
    get_myrain_for,
    get_latest_timestamps_for_all_models,
    get_latest_realtime_rainfall_as_gdf,
    read_report,
    save_events_from_report
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
from .forms import UploadVieuxRainfallReport


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
        # filter queryset by public visibility
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
        summary = get_latest_timestamps_for_all_models()
        return Response(summary)

    def list(self, request, format=None):
        summary = get_latest_timestamps_for_all_models()
        return Response(summary)

# -------------------------------------------------------------------
# Rainfall summaries as text

def get_myrain_24hours(request):
    lat, lng, srid = request.GET.get('lat'), request.GET.get('lng'), request.GET.get('srid')
    text = get_myrain_for(lat, lng, srid, timedelta(days=1), "over the past 24 hours")
    return render(request, 'speech.html', {"text": text})
    
def get_myrain_48hours(request):
    lat, lng, srid = request.GET.get('lat'), request.GET.get('lng'), request.GET.get('srid')
    text = get_myrain_for(lat, lng, srid, timedelta(days=2), "over the past 48 hours")
    return render(request, 'speech.html', {"text": text})

def get_myrain_pastweek(request):
    lat, lng, srid = request.GET.get('lat'), request.GET.get('lng'), request.GET.get('srid')
    text = get_myrain_for(lat, lng, srid, timedelta(days=7), "over the past week")
    return render(request, 'speech.html', {"text": text})

# -------------------------------------------------------------------
# Rainfall summaries for AGO

@api_view(["GET"])
def get_latest_realtime_data_for_ago_animation(request:Request):
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
    
    gdf = get_latest_realtime_rainfall_as_gdf(hours=float(hours))

    if f == "geojson":
        r = json.loads(
            gdf.to_json(drop_id=True)
        )
    else: #elif f == "split"
        # separate x and y columns from wkt column
        gdf['x'] = gdf['wkt'].x
        gdf['y'] = gdf['wkt'].y
        # remove wkt column
        gdf.drop(columns=["wkt"], inplace=True)
        # convert to 2D columns array
        r = gdf.to_dict(orient="split")
        i = r.pop("index")

    return Response(r)


@login_required
def upload_vieuxreport_file(request):
    """form-based view for uploading a Hobolink CSV
    """
    if request.method == 'POST':
        form = UploadVieuxRainfallReport(request.POST, request.FILES)
        if form.is_valid():
            events = read_report(fstream=request.FILES['file'])
            status = save_events_from_report(events)
            if status:
                # HttpResponse(f'The file is saved {status}')
                if status['status'] == "success":
                    for log in status['logs']:
                        messages.add_message(request, messages.INFO, log)
                    messages.add_message(request, messages.SUCCESS, f"The Vieux Rainfall Report was successfully uploaded. {len(status['logs'])} events were created.")
                else:
                    messages.add_message(request, messages.ERROR, 'There was a problem processing the file you provided.')
                    for log in status['logs']:
                        messages.add_message(request, messages.ERROR, log)
            else:
                messages.add_message(request, messages.WARNING, 'No input provided.')
            return redirect('uploadvieuxreport')
    else:
        form = UploadVieuxRainfallReport()
    return render(request, 'upload-vieux.html', {
        'form': form, 
        'title': 'Upload | Vieux Rainfall Report PDF',
        'breadcrumblist': [('Rainfall', '/rainfall/'), ('Upload Vieux Report', '/rainfall/upload-vieux-report/')]
        }
    )