import json
from datetime import datetime

import petl as etl
from dateutil import tz
from dateutil.parser import parse
from pynamodb.models import Model as PynamoDbModel
from pynamodb.attributes import (
    UnicodeAttribute, 
    NumberAttribute
)
from marshmallow import (
    Schema, 
    fields, 
    validate, 
    validates, 
    ValidationError, 
    EXCLUDE, 
    pre_load
)
from requests.status_codes import _codes as http_codes_lookup

from ...common.config import (
#from .config import (
    AWS_REGION,
    TARGET_TABLE_RTRR15,
    TARGET_TABLE_GARR15,
    TARGET_TABLE_GAUGE15,
    TZ_STRING, 
    TZI, 
    TZINFOS,
    INTERVAL_15MIN,
    INTERVAL_TRUTHS,
    ZEROFILL_TRUTHS,
    DELIMITER,
    JSEND_CODES,
    F_ARRAYS, 
    F_CSV,
    F_GEOJSON,
    F_JSON,
    F_MD
)
from .utils import datetime_encoder, dt_parser

## ----------------------------------------------------------------------------
## AWS DYNAMODB TABLE MODELS 

class RainfallObservation(PynamoDbModel):
    """Base model for rainfall observations stored in DynamoDB tables
    """
    # primary key
    ## partition key - sensor id
    id = UnicodeAttribute(hash_key=True)
    ## sort key - timestamp of the observation
    ts = UnicodeAttribute(range_key=True)
    # observation src code
    src = UnicodeAttribute(null=True, default=None)
    # observed value
    val = NumberAttribute(null=True, default=None)


class TableGARR15(RainfallObservation):

    class Meta: 
        table_name = TARGET_TABLE_GARR15
        region = AWS_REGION


class TableGauge15(RainfallObservation):

    class Meta: 
        table_name = TARGET_TABLE_GAUGE15
        region = AWS_REGION


class TableRTRR15(RainfallObservation):

    class Meta: 
        table_name = TARGET_TABLE_RTRR15
        region = AWS_REGION



## ----------------------------------------------------------------------------
## REQUEST PARSING MODEL FOR RAINFALL API v2

class RequestSchema(Schema):

    # constants

    ## parsed arguments
    # sensor ids, either pixels or gauges
    sensor_ids = fields.Str(default=None, missing=None, allow_none=True)
    # start and end times of the query
    start_dt = fields.DateTime()
    end_dt = fields.DateTime(default=None, missing=None, allow_none=True)
    # rollup, zerofill, and f(ormat) determine how query result gets post-processed
    rollup = fields.Str(default=INTERVAL_15MIN, missing=INTERVAL_15MIN, allow_none=True)
    zerofill = fields.Bool(default=True, missing=True, allow_none=True)
    f = fields.Str(default="JSON", missing="JSON", allow_none=True)

    @pre_load
    def preprocess_args(self, data, **kwargs):
        """pre-process the request args
        """
        # print(data)
        # parse interval arg, setting default if needed
        if 'rollup' in data.keys():
            data['rollup'] = INTERVAL_15MIN if data['rollup'].lower() not in INTERVAL_TRUTHS else data['rollup'].lower()
        
        # parse zerofill arg into a boolean
        if 'zerofill' in data.keys():
            data['zerofill'] = data['zerofill'].lower() in ZEROFILL_TRUTHS

        if 'f' in data.keys():
            data['f'] = data['f'].lower()

        # parse all the start and end date/times args into datetime objects
        # using dateutil.parser.parse behind the scenes here gives the end user some flexibility in how they submit date/times
        # we *assume* times submitted are for America/New-York Eastern timezone, even if not explicity provided that way
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


class ResponseSchema:
    """Implements the format for response delivered by the AWS API Gateway; handles
    formatting the body of the response (inspired by https://github.com/omniti-labs/jsend)
    """

    def __init__(self, request_args=None, response_data=None, status_code=None, message=None, meta=None, response_data_format=None, headers=None):
        """[summary]
        
        :param request_args: request args as parsed by the API, defaults to None
        :type request_args: dict, optional
        :param response_data: acts as the wrapper for any data returned by the API call. If the call returns no data, defaults to None
        :type response_data: list or dict, optional
        :param status_code: http status code, defaults to 200
        :type status_code: int, optional
        :param message: detailed message, defaults to None
        :type message: str, optional
        :param meta: contains anything passed in by the user; includes an auto-calc'd row count if response_data is parsed; defaults to None
        :type meta: dict, optional
        :param response_data_format: valid http response header Content-Types, e.g., 'application/json', 'text/csv'; defaults to 'application/json'
        :type response_data_format: str, optional
        :param headers: any user-provided response header content and will always includes Content-Type: based on the response_data_format param by default; defaults to None
        :type headers: dict, optional
        """
        
        # BODY
        self.args = datetime_encoder(request_args) if request_args else None
        self.data = response_data if response_data else []
        self.status_message = JSEND_CODES[status_code] if status_code else 'success'
        self.message = message if message else None #http_codes_lookup[status_code]

        self.meta = meta if meta else {}
        self.rowcount = len(response_data) if response_data else None
        if self.rowcount:
            self.meta.update({"records": self.rowcount})

        self._body = dict(
            args=self.args,
            meta=self.meta,
            data=self.data,
            status=self.status_message
        )
        # add a message if there is one
        if self.message:
            self._body.update({'message': self.message})

        # TOP-LEVEL
        self.status_code = status_code if status_code else 200
        self.headers = headers if headers else {}
        self.content_type = response_data_format if response_data_format else 'application/json'
        if self.content_type:
            self.headers.update({"Content-Type": self.content_type})

        # Have to add this *manually* to make CORS work! APIGW setting doesn't do it!
        self.headers.update({"Access-Control-Allow-Origin":"*"})

        # Exceptions: 
        # 1. if the requested output format was GeoJSON, we don't include the response metadata.
        if self.args:
            if self.args['f'] in F_GEOJSON:
                self._body = self.data
        # ...

        self._top_level = dict(
            statusCode = self.status_code,
            headers=self.headers,
            body=json.dumps(self._body)
        )
    
    def as_dict(self):
        """assemble the response as a dictionary
        """
        return self._top_level

    def __str__(self):
        return json.dumps(self.as_dict())