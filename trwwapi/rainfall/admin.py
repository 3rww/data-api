from django.contrib import admin
# from django.contrib.admin import ModelAdmin
from leaflet.admin import LeafletGeoAdmin

from .models import (
    RainfallEvent,
    Pixel,
    Gauge,
    Collection,
    Resource,
    Boundary
)

# customize admin site info
admin.site.site_header = '3RWW API'
admin.site.site_title = '3RWW API'
admin.site.index_title = '3RWW API'

class RainfallEventAdmin(admin.ModelAdmin):
    list_filter = ('start_dt', 'end_dt')
    search_fields = ['start_dt', 'end_dt', 'report_label', 'event_label']

class GaugeAdmin(LeafletGeoAdmin):
    list_filter = ['active']
    search_fields = ['web_id', 'ext_id', 'nws_des', 'name', 'address']

for i in [
    [RainfallEvent, RainfallEventAdmin],
    [Pixel, LeafletGeoAdmin],
    [Gauge, GaugeAdmin],
    [Collection],
    [Resource],
    [Boundary, LeafletGeoAdmin]
]:
    admin.site.register(*i)