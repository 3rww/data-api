"""selectors.py

Pure functions that only read from the database via the Django ORM and return 
Django Querysets

"""

from django.db.models import (
    ExpressionWrapper, 
    Value, 
    CharField,
    F,
    functions as fx
)
from .models import (
    RainfallEvent, 
    Pixel,
    Collection,
    Boundary,
    Resource
)

def select_pixel_ids_for_muni_boundaries(resource_slug="allegheny-county-municipalities"):
    return

def select_gauge_ids_for_muni_boundaries(resource_slug="allegheny-county-municipalities"):
    return

def select_pixel_ids_for_watershed_boundaries():
    return

def select_gauge_ids_for_watershed_boundaries():
    return


def select_all_radar_pixel_ids():
    return Pixel.objects.all().values_list('pixel_id', flat=True)

def select_annotated_rainfall_events(
    start_dt=None, 
    end_dt=None
    ):
    """returns rainfall events, optionally within a timeframe, and includes
    additional annotations fields: year, month, and an extended label.
    """
    
    dt_filters={}
    if start_dt:
        dt_filters["start_dt__gte"] = start_dt
    if end_dt:
        dt_filters["start_dt__gte"] = start_dt

    rain_events = RainfallEvent.objects\
        .annotate(
            event_label_ext=ExpressionWrapper(
                fx.Concat(
                    fx.ExtractYear("start_dt"),
                    Value("-"),
                    fx.ExtractMonth("start_dt"), 
                    Value(" | "), 
                    F("event_label")
                ),
                output_field=CharField()
            ),
            event_year=fx.ExtractYear("start_dt"),
            event_month=fx.ExtractMonth("start_dt")
        )\
        .order_by("-start_dt")

    if len(dt_filters.items()) > 0:
        rain_events = rain_events.filter(**dt_filters)

    return rain_events