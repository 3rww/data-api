from django.contrib import admin
# from django.contrib.admin import ModelAdmin
from leaflet.admin import LeafletGeoAdmin

from .models import (
    Resource,
    Collection,
    Boundary
)

# customize admin site info
admin.site.site_header = '3RWW API'
admin.site.site_title = '3RWW API'
admin.site.index_title = '3RWW API'

for i in [
    [Collection],
    [Resource],
    [Boundary, LeafletGeoAdmin]
]:
    admin.site.register(*i)