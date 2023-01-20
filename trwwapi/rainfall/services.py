from datetime import datetime, timedelta
import gc
import logging
from typing import List, Union as Any
import pdb
import objgraph
import json

from django.utils.timezone import localtime, now
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import serialize
from django.db import models
from django.db.models import Value, Sum, F, Func
from django.db.models.functions import Concat
from django.contrib.gis.db.models import Union
from django.contrib.gis.db.models.functions import AsWKT, Centroid, SnapToGrid
from django.contrib.gis.geos import Point
from shapely import wkt
from rest_framework import status
from rest_framework.response import Response
from marshmallow import ValidationError
from dateutil import tz
from django_rq import job, get_queue
from django_pivot.pivot import pivot
import pandas as pd
import geopandas as gpd

from ..rainways.models import Boundary, Resource
from .models import Pixel, Gauge
from ..utils import DebugMessages, _parse_request, DateToChar, rounded_qtr_hour
from .api_v2.core import (
    parse_datetime_args,
    query_pgdb,
    transform_and_aggregate_datetimes,
    apply_zerofill,
    format_results
)
from ..common.config import (
    DELIMITER,
    TZ,
    TZI,
    F_CSV,
    MAX_RECORDS
)
from .models import (
    RainfallEvent,
    RtrgRecord,
    GarrRecord,
    GaugeRecord,    
    RtrrRecord,
    MODELNAME_TO_GEOMODEL_LOOKUP,
    GEOMODEL_SID_FIELD_LOOKUP
)
from .serializers import (
    ResponseSchema,
    parse_and_validate_args
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# SELECTOR+WORKER FOR THE ASYNC API VIEWS

@job
def get_rainfall_data(postgres_table_model, raw_args=None):
    """Generic function for handling GET or POST requests of any of the rainfall
    tables. Used for the high-level ReST API endpoints.

    Modeled off of the handler.py script from the original serverless version 
    of this codebase.
    """

    # print("request made to", postgres_table_model, raw_args)

    messages = DebugMessages(debug=True)
    results = []

    # handle missing arguments here:
    # Rollup = Sum
    # Format = Time-oriented
    # start and end datetimes: will attemp to look for the last rainfall event, 
    # otherwise will fallback to looking for 4 hours of the latest available data.

    if not raw_args:
        raw_args = {}
    
    # by default, if no start or end datetimes provided, get those from the
    # latest available rainfall report.
    if all(['start_dt' not in raw_args.keys(),'end_dt' not in raw_args.keys()]):
        latest_report = RainfallEvent.objects.first()
        # if there are events available, fall back to one of those
        if latest_report:
            # We explicitly convert to localtime here because Django assumes datetimes
            # in the DB are stored as UTC (even with timezone offset stored there)
            raw_args['start_dt'] = localtime(latest_report.start_dt, TZ).isoformat()
            raw_args['end_dt'] = localtime(latest_report.end_dt, TZ).isoformat()
            messages.add("Using the latest available rainfall event data by a default.")
        # if reports aren't available, then fallback to getting the latest 
        # available data
        else:
            try:
                last_data_point = postgres_table_model.objects.latest('timestamp')
                # print(last_data_point)
                latest = raw_args['end_dt'] = localtime(last_data_point.timestamp, TZ)
                before = latest - timedelta(hours=4)
                raw_args['start_dt'] = before.isoformat()
                raw_args['end_dt'] = latest.isoformat()
                messages.add("Using the latest available rainfall data by a default.")
            except ObjectDoesNotExist:
                messages.add("Unable to retrieve data: no arguments provided; unable to default to latest data.")
                response = ResponseSchema(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    messages=messages.messages
                )
                # return Response(data=response.as_dict(), status=status.HTTP_400_BAD_REQUEST)                
                # return response.as_dict()

        # raw_args['rollup'] = INTERVAL_SUM
        # raw_args['f'] = 'time' #sensor

                # response = ResponseSchema(
                #     status_code=400,
                #     messages="No arguments provided in the request. See documentation for example requests.",
                # )
                # return Response(data=response.as_dict(), status=status.HTTP_400_BAD_REQUEST)

    # print(raw_args)

    # -------------------------------------------------------------------
    # validate the request arguments

    # **validate** all request arguments using a marshmallow schema
    # this will convert datetimes to the proper format, check formatting, etc.
    args = {}
    try:
        # print("parse_and_validate_args")
        # print(type(raw_args), raw_args)
        raw_args = dict(**raw_args)
        # print(type(raw_args), raw_args)
        args = parse_and_validate_args(raw_args)
    # return errors from validation
    except ValidationError as e:
        messages.add("{1}. See documentation for example requests.".format(e.messages))
        # print(e.messages)
        response = ResponseSchema(
            status_code=status.HTTP_400_BAD_REQUEST,
            messages=messages.messages
        )
        # return Response(data=response.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        # return response.as_dict()
    except KeyError as e:
        messages.add("Invalid request arguments ({0}). See documentation for example requests".format(e))
        response = ResponseSchema(
            status_code=status.HTTP_400_BAD_REQUEST,
            messages=messages.messages
        )
        # return Response(data=response.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        #return response.as_dict()

    # -------------------------------------------------------------------
    # build a query from request args and submit it 

    # here we figure out all possible datetimes and sensor ids. The combination of these
    # make up the primary keys in the database
    
    # parse the datetime parameters into a complete list of all possible date times
    # print("parse_datetime_args")
    dts, interval_count = parse_datetime_args(args['start_dt'], args['end_dt'], args['rollup'])
    # print(dts)

    # parse sensor ID string to a list. if not provided, the subsequent query will return all sensors.
    sensor_ids = []
    if args['sensor_ids']:
        sensor_ids = [str(i) for i in args['sensor_ids'].split(DELIMITER)]


    # SAFETY VALVE: kill the response if the query will return more than we can handle.
    # The default threshold ~ is slightly more than 1 month of pixel records for our largest catchment area

    # if any([
    #     # 15-minute: < 1 week 
    #     args['rollup'] == INTERVAL_15MIN and len(dts) > (24 * 4 * 7),
    #     # hourly < 1 month
    #     args['rollup'] == INTERVAL_HOURLY and len(dts) > (4 * 24 * 31),
    #     # daily: < 3 months
    #     args['rollup'] == INTERVAL_DAILY and len(dts) > (4 * 24 * 90),
    #     # monthly: < 1 year
    #     args['rollup'] == INTERVAL_MONTHLY and len(dts) > (4 * 24 * 366),
    #     # sum: < 1 year
    #     args['rollup'] == INTERVAL_SUM and len(dts) > (4 * 24 * 366)
    # ]):
        # messages.add("The submitted request would generate a larger response than we can manage for you right now. Use one of the following combinations of rollup and datetime ranges: 15-minute: < 1 week; hourly < 1 month; daily: < 3 months; monthly: < 1 year; sum: < 1 year. Please either reduce the date/time range queried or increase the time interval for roll-up parameter.")
    record_count = interval_count * len(sensor_ids)
    # print(interval_count, len(sensor_ids))
    print("record_count", record_count)

    if record_count > MAX_RECORDS:
        messages.add("The request is unfortunately a bit more than we can handle for you right now: this query would return {0:,} data points and we can handle ~{1:,} at the moment. Please reduce the date/time range.".format(record_count, MAX_RECORDS))
        response = ResponseSchema(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_args=args,
            messages=messages.messages
        )
        return response.as_dict()


    # use parsed args and datetime list to query the database
    try:
        # print("query_pgdb")
        results = query_pgdb(postgres_table_model, sensor_ids, dts)
    #print(results)
    
    except Exception as e:
        print(e)
        messages.add("Could not retrieve records from the database. Error(s): {0}".format(str(e)))
        response = ResponseSchema(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_args=args,
            messages=messages.messages
        )
        return Response(data=response.as_dict(), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        #return response.as_dict()

    # -------------------------------------------------------------------
    # post process the query results, if any

    if len(results) > 0:
            
        # perform selects and/or aggregations based on zerofill and interval args
        # print("aggregate_results_by_interval")
        transformed_results = transform_and_aggregate_datetimes(results, args['rollup'])
        #print("aggregated results\n", etl.fromdicts(aggregated_results))
        # print("apply_zerofill")
        # zerofilled_results = apply_zerofill(transformed_results, args['zerofill'], dts)
        # transform the data to the desired format, if any
        # print("format_results")
        response_data = format_results(
            transformed_results, 
            args['f'],
            MODELNAME_TO_GEOMODEL_LOOKUP[postgres_table_model._meta.object_name]
        )

        # return the result
        # print("completed, returning the results")
        # pdb.set_trace()

        # if the request was for a csv in the legacy teragon format, then we only return that
        if args['f'] in F_CSV:
            # print('returning legacy CSV format')
            return Response(response_data, status=status.HTTP_200_OK, content_type="text/csv")
        else:
            response = ResponseSchema(
                status_code=status.HTTP_200_OK,
                request_args=args,
                response_data=response_data,
                messages=messages.messages
            )
            #return Response(response.as_dict(), status=status.HTTP_200_OK)
            #return response.as_dict()

    else:
        # return the result
        messages.add("No records returned for {0}".format(args['sensor_ids']))
        response = ResponseSchema(
            status_code=status.HTTP_200_OK,
            request_args=args,
            messages=messages.messages
        )
        
    
    # print("RESPONSE", response.as_dict())
    
    return response.as_dict()


def handle_request_for(rainfall_model, request, *args, **kwargs):
    """Helper function that handles the routing of requests through 
    get_rainfall_data to a job queue. Returns responses with a 
    URL to the job results. Responsible for forming the shape, but not content, 
    of the response.
    """
    # logger.debug("STARTING handle_request_for")
    # logger.debug(objgraph.show_growth())

    job_meta = None
    raw_args = _parse_request(request)
    # print(args, kwargs, raw_args)

    # if the incoming request includes the jobid path argument,
    # then we check for the job in the queue and return its status
    if 'jobid' in kwargs.keys():

        q = get_queue()
        #queued_job_ids = q.job_ids
        job = q.fetch_job(kwargs['jobid'])
        # print("fetched job", job)

        # if that job exists then we return the status and results, if any
        if job:
            # print("{} is in the queue".format(job.id))
            
            # in this case, the absolute URI is the one that got us here,
            # and includes the job id.
            job_url = request.build_absolute_uri()
            job_meta = {
                "jobId": job.id,
                "jobUrl": job_url
            }
            # job status: one of [queued, started, deferred, finished, failed]
            # (comes direct from Python-RQ)
            job_status = job.get_status()

            # if result isn't None, then the job is completed (may be a success 
            # or failure)
            if job.result:

                # mash up job metadata with any that comes from the 
                # completed task
                meta = job.result['meta']
                meta.update(job_meta)

                # assemble the response object. In addition to the results, 
                # status, and meta, it returns the request arguments **as they
                # were interpreted by the parsers** (this is a good way to see
                # if the arguments were submitted correctly)
                response = ResponseSchema(
                    # queued, started, deferred, finished, or failed
                    status_message=job_status,
                    request_args=job.result['args'],
                    messages=job.result['messages'],
                    response_data=job.result['data'],
                    meta=meta
                )
            else:
                # if there is no result, we return with an updated status 
                # but nothing else will change
                response = ResponseSchema(
                    # queued, started, deferred, finished, or failed
                    request_args=raw_args,
                    status_message=job_status,
                    # messages=['running job {0}'.format(job.id)],
                    meta=job_meta
                )

            # logger.debug(objgraph.show_growth())
            gc.collect()
            return Response(response.as_dict(), status=response.status_code)
        else:
            # if the job ID wasn't found, we kick it back.
            response = ResponseSchema(
                request_args={},
                status_message="does not exist",
                messages=['The requested job {} does not exist.'.format(kwargs['jobid'])],
                meta=job_meta
            )
            # logger.debug(objgraph.show_growth())
            gc.collect()
            return Response(response.as_dict(), status=response.status_code)

    # If not, this is a new request. Queue it up and return the job status
    # and a URL for checking on the job status
    else:
        logger.debug("This is a new request.")
        job = get_rainfall_data.delay(rainfall_model, raw_args)
        job_url = "{0}{1}/".format(request.build_absolute_uri(request.path), job.id)
        response = ResponseSchema(
            # queued, started, deferred, finished, or failed
            request_args=raw_args,
            status_message=job.get_status(),
            messages=['running job {0}'.format(job.id)],
            meta={
                "jobId": job.id,
                "jobUrl": job_url
            }
        )

        # return redirect(job_url)
        # logger.debug(objgraph.show_growth()) 
        gc.collect()
        return Response(response.as_dict(), status=status.HTTP_200_OK)


# ------------------------------------------------------------------------------
# SELECTORS

# -------------------------------------
# basic queries

def select_rainfall_records_back_by_timedelta(
    model_class:Any[GarrRecord, GaugeRecord, RtrgRecord, RtrrRecord], 
    timedelta_kwargs:dict,
    round_to_last_quater_hour=True
    ) -> models.QuerySet:
    """builds queryset to returns all rainfall records for a given model 
    from now back in time from the most recent quarter hour using a time delta.

    Args:
        model_class (Any[GarrRecord, GaugeRecord, RtrgRecord, RtrrRecord]): _description_
        timedelta_kwargs (dict): datetime.timedelta keyword arguments (e.g., {"hours":2})
        round_to_last_quater_hour (bool, optional): round timezone.now() to the most recent quarter hour. Defaults to True.

    Returns:
        models.QuerySet: a rainfall model queryset with a datetime-based filter applied.
    """
    if round_to_last_quater_hour:
        dt = rounded_qtr_hour(now()) - timedelta(**timedelta_kwargs)
    else:
        dt = now() - timedelta(**timedelta_kwargs)
    return model_class.objects.filter(ts__gte=dt)

def get_rainfall_total_for(model_class, sensor_ids, back_to: timedelta):

    end_dt = localtime(now(), TZ)
    start_dt = end_dt - back_to

    rows = query_pgdb(model_class, sensor_ids, [start_dt, end_dt])
    if rows:
        return round(sum(x['val'] for x in rows if x['val']), 1)
    else:
        return None

# -------------------------------------
# get latest observation timestamps

def get_latest_observation_for(model_class, timestamp_field="ts"):
    """gets the latest record from the model, by default using the 
    timestamp_field arg. Returns a single instance of model_class.
    """
    fields = [f.name for f in model_class._meta.fields]
    # print(model_class)
    
    r = None
    try:
        if 'ts' in fields:
            r = model_class.objects.latest(timestamp_field)
        else:
            r = model_class.objects\
                .annotate(ts=models.ExpressionWrapper(models.F(timestamp_field), output_field=models.DateTimeField()))\
                .latest(timestamp_field)
        return r
    except (model_class.DoesNotExist, AttributeError):
        return None

def get_latest_garr_ts():
    return get_latest_observation_for(GarrRecord)

def get_latest_gauge_ts():
    return get_latest_observation_for(GaugeRecord)

def get_latest_rtrr_ts():
    return get_latest_observation_for(RtrrRecord)

def get_latest_rtrg_ts():
    return get_latest_observation_for(RtrgRecord)

def get_latest_rainfallevent():
    return get_latest_observation_for(RainfallEvent, 'start_dt')

def get_latest_timestamps_for_all_models():
    raw_summary = {
        "calibrated-radar": get_latest_garr_ts(),
        "calibrated-gauge": get_latest_gauge_ts(),
        "realtime-radar": get_latest_rtrr_ts(),
        "realtime-gauge": get_latest_rtrg_ts(),
        "rainfall-events": get_latest_rainfallevent(),
    }

    summary = {
        k: v.ts.astimezone(TZI).isoformat() if v is not None else None
        for k, v in 
        raw_summary.items()
    }

    return summary


# -------------------------------------
# select reference geographies

# provide data for generating a pick list of municipalites, watersheds, etc.
def get_reference_geographies_for_pick_list(
    municipalities_resource_slug="allegheny-county-municipalities", 
    watersheds_resource_slug="allegheny-county-municipalities"
    ):
    result = dict()
    if municipalities_resource_slug:
        result['municipalities'] = Boundary.objects.filter(layer__slug=municipalities_resource_slug).values('id','label')
    if watersheds_resource_slug:
        result['watersheds'] = Boundary.objects.filter(layer__slug=watersheds_resource_slug).values('id','label')
    return result

# return a list of pixels and gauges that overlap with one or more reference geographies
def get_sensors_for_reference_geographies(boundary_ids:List[int]):
    
    boundaries = Boundary.objects.filter(id__in=boundary_ids).aggregate(geom=Union('geom'))['geom']
    pixel_ids = Pixel.objects.filter(geom__intersects=boundaries).values('pixel_id')
    gauge_ids = Gauge.objects.filter(geom__intersects=boundaries).values('web_id')

    return pixel_ids, gauge_ids


# -------------------------------------
# My Rain (speech to text to speech)

def get_myrain_for(lat, lng, srid, back_to:timedelta=timedelta(days=2), back_to_text:str="over the past 48 hours"):
    """get a human-readable (or virtual assistant-readable!) text string
    describing the rainfall total for a specific latitude/longitude and recent
    timeframe
    """
    text ="That didn't work."

    if all([lat, lng]):

        p = Point(float(lng), float(lat)) #, srid=srid if srid else 4326)
        p.srid = srid if srid else 4326
        pixels = Pixel.objects.filter(geom__contains=p)

        if len(list(pixels)) > 0:

            total = get_rainfall_total_for(RtrrRecord, [pixel.pixel_id for pixel in pixels], back_to)

            if total:
                text = """According to 3 Rivers Wet Weather, your location received approximately {0} inches of rainfall {1}.""".format(total, back_to_text)
            else:
                text = "Sorry, it looks like rainfall data is unavailable for your location for that timeframe. Check back soon!"
        else:
            text = "Sorry, we can't get detailed rainfall data for your location."
    else:        
        text = "Sorry, you didn't provide enough location data to answer your question."

    # text += " For more information about rainfall and infrastructure in the greater Pittsburgh area, visit w w w dot 3 rivers wet weather dot org."
    text += " For more information about rainfall and infrastructure in the greater Pittsburgh area, visit www.3riverswetweather.org"

    return text


# -------------------------------------
# Cross-Tabbed ("Wide") Rainfall Summaries

def get_rainfall_data_as_crosstab(
    model_class:Any[GarrRecord, GaugeRecord, RtrgRecord, RtrrRecord],
    start_dt,
    end_dt,
    sids:List[str]=None
    ) -> Any[models.QuerySet, List]:
    
    filters=dict(
        ts__gte=start_dt,
        ts__lte=end_dt
    )

    if sids:
        filters["sid__in"] = sids
    
    r1 = model_class.objects\
        .filter(**filters)\
        .annotate(xts=DateToChar(F('ts'), Value('yyyyMMDD-HHMI00')))#yyyyMMDD_HHMI
        # .annotate(xts=DateToChar(F('ts'), Value('yyyyMMDD_HHMI'))) yyyyMMDDHHMI00 #yyyyMMDD_HHMI

    r2 = pivot(queryset=r1, rows="sid", column="xts", data="val", aggregation=Sum)
    
    return r2

def get_lastest_rainfall_as_crosstab(
    model_class:Any[GarrRecord, GaugeRecord, RtrgRecord, RtrrRecord]=RtrrRecord,
    hours:Any[int,float]=2, 
    ) -> Any[models.QuerySet, List]:
    """Generate a table of rainfall data where records are sensors and columns
    are date/times. This format is useful for spatial timeseries data visualization.
    Any/all sensors in the table are queried

    Args:
        hours (any[int,float], optional): hours before now to query. Defaults to 2.
        model_class (any[GarrRecord, GaugeRecord, RtrgRecord, RtrrRecord], optional): Type of rainfall records to get. Defaults to RtrrRecord.

    Returns:
        queryset: a Queryset

    Returns:
        Union[models.QuerySet, List]: Queryset where items are sensors, and each 
        items contains timeseries-ordered rainfall values.
    """
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(hours=hours)

    return get_rainfall_data_as_crosstab(
        model_class=model_class,
        start_dt=start_dt,
        end_dt=end_dt
    )

def get_rainfall_data_as_geocrosstab(
    model_class:Any[GarrRecord, GaugeRecord, RtrgRecord, RtrrRecord],
    start_dt,
    end_dt,
    sids:List[str]=None,
    only_points:bool=True
) -> gpd.GeoDataFrame:
    """get rainfall data for a specific time period, optionally for specific 
    sensors, and get it back as a geodataframe where rows are sensor features, 
    columns are time intervals, and values are rainfall amounts.

    Args:
        model_class (Any[GarrRecord, GaugeRecord, RtrgRecord, RtrrRecord]): _description_
        start_dt (datetime.datetime): _description_
        end_dt (datetime.datetime): _description_
        sids (List[str], optional): _description_. Defaults to None.
        only_points (bool, optional): Only return point geometries. If sensor geometry is not a point, it gets converted to one (e.g., pixels to pixel centroids)

    Returns:
        dict: _description_
    """
    # ---------------------------------
    # derive some info about the data requested

    # lookup the geo model class, its sensor ID field, and its non-geometry fields
    geo_model_class = MODELNAME_TO_GEOMODEL_LOOKUP[model_class._meta.object_name]
    geo_model_sid_field = GEOMODEL_SID_FIELD_LOOKUP[geo_model_class._meta.object_name]
    geo_model_fields = [f.name for f in geo_model_class._meta.fields if f.name != "geom"]

    # --------------------------------- 
    # rainfall data

    # query the rainfall data table for the timeframe and sensors, get crosstab
    data = get_rainfall_data_as_crosstab(
        model_class=model_class,
        start_dt=start_dt,
        end_dt=end_dt,
        sids=sids
    )
    
    # --------------------------------- 
    # pixel/gauge location
    
    locations:Any[models.QuerySet, List]=None
    # filter locations by SIDs if those were provided 
    if sids:
        kwargs={f"{geo_model_sid_field}__in": sids}
        locations = geo_model_class.objects.filter(**kwargs)
    else:
        locations = geo_model_class.objects.all()

    # serialize to geojson
    # location_gj = serialize('geojson', locations, geometry_field='geom')        

    # selectively handle sensor location types, and add WKT geometry field

    # for gauges, filter out inactive sites and those without IDs
    if geo_model_class._meta.object_name == "Gauge":
        locations = locations\
            .filter(active=True)\
            .exclude(web_id=None)\
            .annotate(wkt=AsWKT('geom'))

    # for pixels, calculate the Centroid and return as WKT
    if geo_model_class._meta.object_name == "Pixel":
        locations = locations\
            .annotate(wkt=AsWKT(Centroid('geom')))

    # add that wkt field to the list
    geo_model_fields.append("wkt")
    # return as list of dictionaries
    locations = locations.values(*geo_model_fields)

    # --------------------------------- 
    # join 

    # read rainfall data into a dataframe
    df = pd.DataFrame(data)
    df.set_index("sid", inplace=True)

    # read the location data into a geodataframe
    ldf = pd.DataFrame(locations)
    ldf['wkt'] = gpd.GeoSeries.from_wkt(ldf['wkt'])
    ldf['sid'] = ldf[geo_model_sid_field]
    gdf = gpd.GeoDataFrame(ldf, geometry='wkt')
    gdf.set_index('sid', inplace=True)

    xdf = gdf.join(df, how="inner")
    xdf.drop(columns=["id"], inplace=True)

    return xdf


# -------------------------------------
# "Long" Geo Rainfall Summaries

def get_latest_realtime_rainfall_as_gdf(
    hours:Any[int,float]=2,
    return_pixels=True, 
    return_gauges=True,
    ) -> gpd.GeoDataFrame:
    """produce a "long" table of real-time rainfall records for pixels and gauges, 
    with geometries joined to those records (all as points).

    This approach, where geometries are replicated for all timeseries observations,
    ultimately supports off-the-shelf timeseries animation in ArcGIS Online.

    Args:
        hours (Any[int,float], optional): _description_. Defaults to 2.
        return_pixels (bool, optional): _description_. Defaults to True.
        return_gauges (bool, optional): _description_. Defaults to True.

    Returns:
        gpd.GeoDataFrame: _description_
    """    

    if not any([return_pixels, return_gauges]):
        return pd.DataFrame()

    dfs = []
    
    if return_pixels:
        # rainfall records for pixels
        latest_rainfall_on_pixels = select_rainfall_records_back_by_timedelta(
            RtrrRecord, 
            dict(hours=hours)
        ).values("ts", "sid", "val", "src").iterator()
        pixel_data_df = pd.DataFrame(latest_rainfall_on_pixels)
        pixel_data_df.set_index('sid', inplace=True)
        
        # pixel geometries (as points)
        pixels = Pixel.objects\
            .annotate(
                sid=F("pixel_id"),
                wkt=AsWKT(SnapToGrid(Centroid('geom'), 0.001)),
                # metadata=None
            )\
            .values("sid", "wkt")
        pixels_df = pd.DataFrame(pixels)
        pixels_df.set_index('sid', inplace=True)

        # join pixel geometries to pixel rainfall records dataframe
        pixels_xdf = pixel_data_df.join(pixels_df, how="left")
        pixels_xdf.reset_index(level=0, inplace=True)
        dfs.append(pixels_xdf)

    if return_gauges:
        latest_rainfall_on_gauges = select_rainfall_records_back_by_timedelta(
            RtrgRecord, 
            dict(hours=hours)
        ).values("ts", "sid", "val", "src").iterator()
        gauge_data_df = pd.DataFrame(latest_rainfall_on_gauges)
        gauge_data_df.set_index('sid', inplace=True)
    
        gauges = Gauge.objects\
            .annotate(
                sid=F("web_id"),
                wkt=AsWKT(SnapToGrid('geom', 0.0001)),
                #metadata={**all_other_fields}
            )\
            .values("sid", "wkt")
        gauges_df = pd.DataFrame(gauges)
        gauges_df.set_index('sid', inplace=True)

        # join gauge geometries to gauge rainfall records dataframe
        gauges_xdf = gauge_data_df.join(gauges_df, how="left")
        gauges_xdf.reset_index(level=0, inplace=True)
        dfs.append(gauges_xdf)

    # combine the dataframes
    df = pd.concat(dfs)
    # remove the index
    df.reset_index(level=0, inplace=True)
    # convert Timestamps to string
    df['ts'] = df['ts'].apply(lambda v: v.strftime('%Y-%m-%d %X'))
    # convert WKT to geos object
    df['wkt'] = gpd.GeoSeries.from_wkt(df['wkt'])
    # read into geodataframe
    gdf = gpd.GeoDataFrame(df, geometry='wkt')
    # remove extra columns
    gdf.drop(columns=["index"], inplace=True)

    return gdf