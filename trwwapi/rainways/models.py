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
from django.contrib.gis.db.models import PolygonField
from django.contrib.gis.db.models.functions import Envelope

from taggit.managers import TaggableManager

from ..common.mixins import TimestampedMixin


class Collection(TimestampedMixin):
    """A collection of external data resources
    """
    
    title = CharField(max_length=255, help_text="A human readable title describing the Collection.")
    description = TextField(blank=True, help_text="Detailed multi-line description to fully explain the Collection.")
    resources = ManyToManyField('Resource', blank=True)
    tags = TaggableManager(blank=True)

    # @property
    # def extent_spatial(self):
    #     return self.resources.objects.all()
    #spatial_extent = PolygonField(blank=True)
    #start_datetime = DateTimeField(blank=True)
    #end_datetime = DateTimeField(blank=True)
    def __str__(self) -> str:
        return self.title


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
    slug = SlugField(max_length=255, unique=True, default=slug_default, null=True, blank=True)
    description = TextField(blank=True, help_text="Detailed description of the resource")
    datetime = DateTimeField(verbose_name="Resource publication Date/Time", blank=True)
    href = CharField(max_length=2048, blank=True, help_text="Resource location. May be a URL or cloud resource (e.g., S3://")
    meta = JSONField(default=data_default, blank=True, null=True)
    tags = TaggableManager(blank=True)

    def __str__(self) -> str:
        return " | ".join([i for i in [self.title, self.href] if i is not None])


class Boundary(TimestampedMixin):

    def data_default():
        return {}

    uid = models.CharField(max_length=255, default=None, null=True, blank=True)
    label = models.CharField(max_length=255, default=None, null=True, blank=True)
    meta = JSONField(default=data_default, blank=True, null=True)
    layer = models.ForeignKey('Resource', on_delete=models.CASCADE, blank=True, null=True)
    geom = PolygonField()