"""Common data models and serializers
"""
from typing import List, Union
# import pint
from dataclasses import dataclass, field, asdict
from django.db.models.aggregates import Sum
from marshmallow import Schema, fields, EXCLUDE, pre_load
from marshmallow_dataclass import class_schema
from marshmallow_dataclass import dataclass as mdc

from django.db import models
from django.db.models import (
    CharField,
    URLField,
    TextField,
    DateTimeField,
    OneToOneField,
    ForeignKey,
    ManyToManyField,
    SlugField,
    JSONField
)
from django.template.defaultfilters import default, slugify
from django.contrib.gis.db.models import PolygonField, MultiPolygonField
from django.contrib.gis.db.models.functions import Envelope
from rest_framework import status as http_status

from taggit.managers import TaggableManager

from .mixins import TimestampedMixin

class Collection(TimestampedMixin):
    """A collection of external data resources
    """
    
    title = CharField(max_length=255, help_text="A human readable title describing the Collection.")
    description = TextField(blank=True, help_text="Detailed multi-line description to fully explain the Collection.")
    resources = ManyToManyField('Resource', blank=True)
    # tags = TaggableManager(blank=True)

    # @property
    # def extent_spatial(self):
    #     return self.resources.objects.all()
    #spatial_extent = PolygonField(blank=True)
    #start_datetime = DateTimeField(blank=True)
    #end_datetime = DateTimeField(blank=True)
    def __str__(self) -> str:
        return self.title

    class Meta:
        abstract = True        

class Resource(TimestampedMixin):
    """A single external data resource reference.

    These are fairly fast & loose; we just need a place to manage a handful of URLs that we need to recall in
    very specific ways for Rainways analysis.
    """

    def data_default():
        return {}

    def slug_default(name):
        return slugify(name)

    title = CharField(max_length=255, blank=True, help_text="Name of the resource")
    slug = SlugField(max_length=255, unique=True, null=True, blank=True, help_text="slug is used by selectors for querying by name")
    description = TextField(blank=True, help_text="Detailed description of the resource")
    datetime = DateTimeField(verbose_name="Resource publication Date/Time", blank=True)
    href = CharField(max_length=2048, blank=True, help_text="Resource location. May be a URL or cloud resource (e.g., S3://")
    meta = JSONField(default=data_default, blank=True, null=True)
    # tags = TaggableManager(blank=True)

    def __str__(self) -> str:
        return " | ".join([i for i in [self.title, self.slug] if i is not None])

    class Meta:
        abstract = True        


class Boundary(TimestampedMixin):

    def data_default():
        return {}

    uid = models.CharField(max_length=255, default=None, null=True, blank=True)
    label = models.CharField(max_length=255, default=None, null=True, blank=True)
    meta = JSONField(default=data_default, blank=True, null=True)
    layer = models.ForeignKey('Resource', on_delete=models.CASCADE, blank=True, null=True)
    geom = MultiPolygonField()

    def __str__(self) -> str:
        return " | ".join([str(i) for i in [self.uid, self.label] if i is not None])

    class Meta:
        abstract = True

@mdc
class TrwwApiResponseSchema:
    """Implements a consistent JSON response format. Inspired by AWS API Gateway 
    and [JSend](https://github.com/omniti-labs/jsend)).

    This uses marshmallow-dataclass to automatically get a schema for serialization.
    
    ```python
    >>> r = ResponseSchema(args={},meta={},data={}) # (with some actual parameters)
    >>> print(ResponseSchema.Schema().dump(r))
    >>> {args:{}, meta: {}, data: {}}
    ```

    When used with the Django Rest Framework, the dumped output is passed to the 'data' 
    argument of the Response object.
    """

    # request args **as parsed by the API**, defaults to {}
    args: dict = field(default_factory=dict)
    # TODO: add "datetime_encoder(args) if args"
    # contains job metadata and post-processing stats, including an auto-calc'd row count if response_data is parsed; defaults to None
    meta: dict = field(default_factory=dict)
    # any data returned by the API call. If the call returns no data, defaults to None
    data: Union[dict, list] = None
    # message, one of [queued, started, deferred, finished, failed, success]; defaults to success
    status: str = 'success'
    # http status code, defaults to 200
    status_code: int = http_status.HTTP_200_OK
    # list of messages
    messages: List[str] = field(default_factory=list)