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

from taggit.managers import TaggableManager

from ..common.models import Collection as mCollection, Resource as mResource, Boundary as mBoundary


class Collection(mCollection):
    tags = TaggableManager(blank=True, related_name="rainways_collection")


class Resource(mResource):
    tags = TaggableManager(blank=True, related_name="rainways_resource")


class Boundary(mBoundary):
    pass