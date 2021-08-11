from datetime import datetime, timedelta
import gc
import logging
import pdb
import objgraph

from django.utils.timezone import localtime, now
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from rest_framework import status
from rest_framework.response import Response
from marshmallow import ValidationError
from dateutil import tz
from django_rq import job, get_queue


from ..utils import DebugMessages, _parse_request
from .api_v2.core import (
    parse_datetime_args,
    query_pgdb,
    transform_and_aggregate_datetimes,
    apply_zerofill,
    format_results
)
from ..common.config import (
#from .api_v2.config import (
    DELIMITER,
    TZ,
    F_CSV,
    INTERVAL_15MIN,
    INTERVAL_DAILY,
    INTERVAL_HOURLY,
    INTERVAL_MONTHLY,
    INTERVAL_SUM,
    MAX_RECORDS
)
from .models import (
    RainfallEvent, 
    GarrObservation,
    GaugeObservation,
    RtrgObservation,
    RtrrObservation,
    RtrgRecord,
    GarrRecord,
    GaugeRecord,    
    RtrrRecord,
    MODELNAME_TO_GEOMODEL_LOOKUP
)
from .serializers import (
    ResponseSchema,
    parse_and_validate_args
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# SELECTOR+WORKER FOR THE HIGH LEVEL API VIEWS

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

    # if len(results) > 0:
            
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

    # else:
    #     # return the result
    #     messages.add("No records returned.")
    #     response = ResponseSchema(
    #         status_code=status.HTTP_200_OK,
    #         request_args=args,
    #         messages=messages.messages
    #     )
        
    
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

# -----------------------
# get latest observation timestamps

def _get_latest(model_class, timestamp_field="ts"):
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

def get_latest_garrobservation():
    return _get_latest(GarrRecord)

def get_latest_gaugeobservation():
    return _get_latest(GaugeRecord)

def get_latest_rtrrobservation():
    return _get_latest(RtrrRecord)

def get_latest_rtrgobservation():
    return _get_latest(RtrgRecord)

def get_latest_rainfallevent():
    return _get_latest(RainfallEvent, 'start_dt')

def get_rainfall_total_for(postgres_table_model, sensor_ids, back_to: timedelta):

    end_dt = localtime(now(), TZ)
    start_dt = end_dt - back_to

    rows = query_pgdb(postgres_table_model, sensor_ids, [start_dt, end_dt])
    if rows:
        return round(sum(x['val'] for x in rows if x['val']), 1)
    else:
        return None
# -----------------------
# get records using a timestamp delta

def _get_ts_by_delta(model_class, timedelta_kwargs):
    return model_class.objects.filter(ts__gte=(datetime.now()-timedelta(**timedelta_kwargs)))
