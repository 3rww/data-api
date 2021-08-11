import json
from os import environ
from datetime import datetime, timedelta
from dateutil.parser import parse
from pytz import timezone

def dt_parser(dt_string, tz_string, tzi, tzinfos):
    """Parses a datetime string with date-util's parser, reads the timezone 
    if it's available *or assigns timezone if there is none using the supplied 
    params*, then converts it to the local timezone specificed in the params. 
    Returns ISO-8061 formatted string.
    """

    if dt_string:
        tz = timezone(tz_string)

        # try:
        dt = parse(dt_string, tzinfos=tzinfos)

        if dt.tzinfo is None:
            return tz.localize(dt).astimezone(tzi).isoformat()
        elif dt.tzinfo != tzi:
            return dt.astimezone(tzi).isoformat()
        else:
            return dt.isoformat()

    return None

def datetime_range(dt_start, dt_end, delta):
    if dt_start == dt_end:
        yield dt_start
    else:
        current = dt_start
        while current < dt_end:
            yield current
            current += delta

def datetime_encoder(obj):
    return json.loads(json.dumps(obj, cls=DatetimeStringEncoder))

class DatetimeStringEncoder(json.JSONEncoder):
    """use to convert any values in a dict stored as datetime objects
    into ISO-formatted datetime strings, for export to JSON
    """

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super(DatetimeStringEncoder, self).default(o)


def get_envvar_w_fallback(name, fallback=None):
    """check for and retrieve an environment variable.
    Optionally return a fallback value if either the key is not found
    or if it's found but has an empty value.
    
    :return: [description]
    :rtype: [type]
    """
    if name in environ.keys():
        if environ[name].strip():
            return environ[name]
    return fallback


def is_same_hour_of_same_day(dt0, dt1):
    return all([
        dt0.date() == dt1.date(),
        dt0.hour == dt1.hour
    ])

def is_same_time_of_same_day(dt0, dt1):
    dt0.replace(second=0, microsecond=0)
    dt1.replace(second=0, microsecond=0)
    return all([
        dt0.date() == dt1.date(),
        dt0.time() == dt1.time()
    ])

