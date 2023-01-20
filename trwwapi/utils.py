import datetime
from django.conf import settings
from django.db import models

class DebugMessages():

    def __init__(self, messages=[], debug=settings.DEBUG):
        self.messages = messages
        self.show = debug

    def add(self, msg):
        if self.show:
            print(msg)
        self.messages.append(msg)

def _parse_request(request):
    """parse the django request object
    """

    # **parse** the arguments from the query string or body, depending on request method
    if request.method == 'GET':
        raw_args = request.query_params.dict()
    else:
        raw_args = request.data

    return raw_args


class DateToChar(models.Func):
    """
    Custom Func expression to convert datetimes to str's in postgres database 
    query. https://stackoverflow.com/a/70176841

    Params for initializer
    ------
    expression_1
        expression resulting in a date: ex: F('date')
    expression_2
        Format string as an expression: Value('YYYY-MM-DD'). Note: Column aliases cannot contain whitespace characters, quotation marks
    """
    arity = 2
    function = 'to_char'
    output_field = models.CharField()

rounded_qtr_hour = lambda dt: datetime.datetime(dt.year, dt.month, dt.day, dt.hour,15*(dt.minute // 15), tzinfo=dt.tzinfo)