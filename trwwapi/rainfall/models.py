from dataclasses import dataclass
from django.contrib.gis.db import models
# from django.contrib.postgres.indexes import 
from django.db.models import JSONField
from django.db.models.constraints import UniqueConstraint

from taggit.managers import TaggableManager

from ..common.mixins import PandasModelMixin, TimestampedMixin
from ..common.models import Collection as mCollection, Resource as mResource, Boundary as mBoundary

# --------------------------------------------------------------
# Rainfall Record Models
# Each record is a single observation per timestamp per sensor; tables are long but not wide.
# All of these are unmanaged by Django. They use a composite primary key (ts+sid) and time-based 
# partitioning, neither of which can be managed by Django.

class RainfallRecordMixin(PandasModelMixin):

    # id = models.BigAutoField()
    ts = models.DateTimeField(db_index=True, verbose_name="Timestamp")
    sid = models.CharField(max_length=12, db_index=True, verbose_name="Sensor ID")
    val = models.FloatField(verbose_name="Rainfall (inches)", blank=True, null=True)
    src = models.CharField(max_length=4, verbose_name="Source", blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ['-ts']
        constraints = [
            UniqueConstraint(fields=['ts', 'sid'], name='%(class)s_uniq_record_constraint')
        ]
        #in_db = "rainfall_db"
        managed = False

    def __str__(self):
        return f"{self.src} {self.sid} | {self.ts.isoformat()} | {self.val}"
    

class GaugeRecord(RainfallRecordMixin):
    """Calibrated Rain Gauge data (historic)
    """
    pass


class GarrRecord(RainfallRecordMixin):
    """Gauge-Adjusted Radar Rainfall (historic)
    """
    pass


class RtrrRecord(RainfallRecordMixin):
    """Raw Radar data (real-time)
    """        
    pass


class RtrgRecord(RainfallRecordMixin):
    """Raw Rain Gauge data (real-time)
    """
    pass

class Rtrg5Record(RainfallRecordMixin):
    """Raw Rain Gauge data (real-time, 5-minute)
    """
    pass

class Garr5Record(RainfallRecordMixin):
    """Gauge-Adjusted Radar Rainfall (historic, 5-minute)
    """
    pass

# --------------------------------------------------------------
# Reports + Rainfall Events


class RainfallReport(TimestampedMixin):
    month_start = models.DateField()
    document = models.FileField()
    # events = models.ManyToManyField('RainfallEvent')


class RainfallEvent(PandasModelMixin, TimestampedMixin):

    report_label = models.CharField(max_length=255)
    event_label = models.CharField(max_length=255)
    start_dt = models.DateTimeField()
    end_dt = models.DateTimeField()
    # TODO: add a report_document relate field for access to a report model w/ the PDFs

    @property
    def duration(self):
        duration = self.end_dt - self.start_dt
        seconds = duration.total_seconds()
        hours = seconds // 3600
        # minutes = (seconds % 3600) // 60
        #seconds = seconds % 60
        return hours

    class Meta:
        ordering = ['-end_dt']

    def __str__(self):
        return self.event_label


# --------------------------------------------------------------
# Rainfall Sensor Geography

class Pixel(PandasModelMixin):
    pixel_id = models.CharField(max_length=12)
    geom = models.PolygonField()

    def __str__(self):
        return self.pixel_id


class Gauge(PandasModelMixin):

    web_id = models.CharField(max_length=10, null=True)
    ext_id = models.CharField(max_length=10, null=True)
    nws_des = models.CharField(max_length=255, null=True)
    name = models.CharField(max_length=255)
    address = models.TextField(null=True)
    ant_elev = models.FloatField(null=True)
    elev_ft = models.FloatField(null=True)
    geom = models.PointField(null=True)
    active = models.BooleanField(default=True, null=True)

    class Meta:
        ordering = ["ext_id"]

    def __str__(self):
        return "{0} - {1}".format(self.web_id, self.name)


# --------------------------------------------------------------
# Tables for reference data


class Collection(mCollection):
    tags = TaggableManager(blank=True, related_name="rainfall_collection")
    pass


class Resource(mResource):
    tags = TaggableManager(blank=True, related_name="rainfall_resource")
    pass


class Boundary(mBoundary):
    pass


# MODELNAME_TO_GEOMODEL_LOOKUP helps us dynamically select the correct geodata 
# for an observation model, since we don't enforce a relationship between the 
# observation models and sensor layer models
MODELNAME_TO_GEOMODEL_LOOKUP = {
    GarrRecord._meta.object_name: Pixel,
    RtrrRecord._meta.object_name: Pixel,
    GaugeRecord._meta.object_name: Gauge,
    RtrgRecord._meta.object_name: Gauge,
}

GEOMODEL_SID_FIELD_LOOKUP = {
    Pixel._meta.object_name: "pixel_id",
    Gauge._meta.object_name: "web_id",
}