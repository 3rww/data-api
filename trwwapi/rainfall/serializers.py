import json
from django.conf import settings
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer 
#from dateutil.parser import parse

from marshmallow import (
    Schema, 
    fields, 
    validate, 
    validates, 
    ValidationError, 
    EXCLUDE, 
    pre_load
)

from ..common.config import (
#from .api_v2.config import (
    TZ_STRING, 
    TZI, 
    TZINFOS,
    INTERVAL_SUM,
    INTERVAL_TRUTHS,
    ZEROFILL_TRUTHS,
)
from .api_v2.utils import datetime_encoder, dt_parser

from .models import (
    RainfallEvent, Pixel, Gauge,
    GarrRecord, GaugeRecord, RtrrRecord, RtrgRecord
)

from rest_framework import serializers

class RainfallQueryResultSerializer(serializers.Serializer):
    id = serializers.CharField()
    ts = serializers.DateTimeField()
    val = serializers.FloatField(required=False)
    src = serializers.CharField(required=False)

    # def to_representation(self, instance):
    #     """Convert `ts` to an ISO-formatted, timezone aware datetime string."""
    #     ret = super().to_representation(instance)
    #     ret['ts'] = parse(ret['ts']).astimezone(TZI).isoformat()
    #     return ret



# ------------------------
# Reference Models

class RainfallEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = RainfallEvent
        fields = ("start_dt", "end_dt", "report_label", "event_label", "duration")


class PixelSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Pixel
        geo_field = "geom"
        fields = '__all__'


class GaugeSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Gauge
        geo_field = "geom"
        fields = '__all__'


# ------------------------
# Record Models


class GarrRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = GarrRecord
        fields = ('ts', 'sid', 'val', 'src')


class GaugeRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = GaugeRecord
        fields = ('ts', 'sid', 'val')


class RtrgRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RtrgRecord
        fields = ('ts', 'sid', 'val')


class RtrrRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RtrrRecord
        fields = ('ts', 'sid', 'val')


class RequestSchema(Schema):
    """Custom Marshmallow serializer for request parameters. Used for the high-level api

    :param Schema: [description]
    :type Schema: [type]
    :return: [description]
    :rtype: [type]
    """

    # constants

    ## parsed arguments
    # sensor ids, either pixels or gauges
    sensor_ids = fields.Str(default=None, missing=None, allow_none=True)
    # start and end times of the query
    start_dt = fields.DateTime()
    end_dt = fields.DateTime(default=None, missing=None, allow_none=True)
    # rollup, zerofill, and f(ormat) determine how query result gets post-processed
    rollup = fields.Str(default=INTERVAL_SUM, missing=INTERVAL_SUM, allow_none=True)
    zerofill = fields.Bool(default=True, missing=True, allow_none=True)
    f = fields.Str(default="JSON", missing="JSON", allow_none=True)

    @pre_load
    def preprocess_args(self, data, **kwargs):
        """pre-process the request args
        """
        
        # parse interval arg, setting default if needed
        if 'rollup' in data.keys():
            data['rollup'] = INTERVAL_SUM if data['rollup'].lower() not in INTERVAL_TRUTHS else data['rollup'].lower()
        else:
            data['rollup'] = INTERVAL_SUM
        
        # parse zerofill arg into a boolean
        if 'zerofill' in data.keys():
            data['zerofill'] = data['zerofill'].lower() in ZEROFILL_TRUTHS
        
        # parse the output format, fallback to a default if none provided
        if 'f' in data.keys():
            data['f'] = data['f'].lower()
        else:
            data['f'] = 'time'

        # parse all the start and end date/times args into datetime objects
        # using dateutil.parser.parse behind the scenes here gives the end user some flexibility in how they submit date/times
        # we assume naive timestamps submitted are for America/New-York Eastern timezone, even if not explicity provided that way
        # if timezone info is attached (ISO or otherwise, we should be able to get that)
        data['start_dt'] = dt_parser(data['start_dt'], tz_string=TZ_STRING, tzi=TZI, tzinfos=TZINFOS)
        if 'end_dt' in data.keys():
            data['end_dt'] = dt_parser(data['end_dt'], tz_string=TZ_STRING, tzi=TZI, tzinfos=TZINFOS)
        else:
            data['end_dt'] = None

        # parse the contents of the pixel or gauge arg to the sensor_ids arg
        # if there isn't one, set to None--this will get handled with an appropriate 
        # fallback later on
        try:
            if 'pixels' in data.keys():
                sensor_ids = data.pop('pixels')
            elif 'gauges' in data.keys():
                sensor_ids = data.pop('gauges')
            else:
                sensor_ids = None
            data['sensor_ids'] = sensor_ids
        except ValidationError as err:
            print(err.messages)
            
        return data

    class Meta:
        unknown = EXCLUDE
        ordered = True


def parse_and_validate_args(raw_args):
    """validate request args and parse using Marshmallow pre-processor schema.
    
    :param raw_args: kwargs parsed from request
    :type raw_args: dict
    :return: validated kwargs
    :rtype: dict
    """
    request_schema = RequestSchema()
    return request_schema.load(raw_args)


class ResponseSchema:
    """Implements the format for response delivered by the AWS API Gateway; handles
    formatting the body of the response (inspired by https://github.com/omniti-labs/jsend)
    """

    def __init__(self, 
        request_args=None, 
        response_data=None, 
        status_code=None, 
        status_message=None,
        messages=None, 
        meta=None,
    ):
        """[summary]
        
        :param request_args: request args **as parsed by the API**, defaults to None
        :type request_args: dict, optional
        :param response_data: acts as the wrapper for any data returned by the API call. If the call returns no data, defaults to None
        :type response_data: list or dict, optional
        :param status_code: http status code, defaults to 200
        :type status_code: int, optional
        :param message: message, one of [queued, started, deferred, finished, failed]; defaults to success
        :type message: str, optional
        :param meta: contains job metadata and post-processing stats, including an auto-calc'd row count if response_data is parsed; defaults to None
        :type meta: dict, optional
        """
        
        # BODY
        self.args = datetime_encoder(request_args) if request_args else None
        self.meta = meta if meta else {}
        self.data = response_data if response_data else None
        self.status_message = status_message if status_message else 'success'
        self.messages = messages if messages else [] #http_codes_lookup[status_code]
        self.status_code = status_code if status_code else 200
        self.rowcount = len(response_data) if response_data else None
        if self.rowcount:
            self.meta.update({"records": self.rowcount})

        self._body = dict(
            args=self.args,
            meta=self.meta,
            data=self.data,
            status=self.status_message,
            status_code=self.status_code,
            messages=self.messages
        )
    
    def as_dict(self):
        """assemble the response as a dictionary
        """
        return self._body

    def __str__(self):
        return json.dumps(self.as_dict())