from django.contrib import admin
# from django.contrib.admin import ModelAdmin
from leaflet.admin import LeafletGeoAdmin

from .models import (
    RainfallEvent,
    Pixel,
    Gauge
)

# customize admin site info
admin.site.site_header = '3RWW API'
admin.site.site_title = '3RWW API'
admin.site.index_title = '3RWW API'

class RainfallEventAdmin(admin.ModelAdmin):
    list_filter = ('start_dt', 'end_dt')
    search_fields = ['start_dt', 'end_dt', 'report_label', 'event_label']

for i in [
    [RainfallEvent, RainfallEventAdmin],
    [Pixel, LeafletGeoAdmin],
    [Gauge, LeafletGeoAdmin]
]:
    admin.site.register(*i)