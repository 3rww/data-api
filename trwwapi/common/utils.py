import json
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Model

def load_geojson_to_model(
    geojson_as_dict:dict, 
    model_class:Model, 
    field_mapping:dict,
    geometry_field:str="geom", 
    dump_extra_to_jsonfield:bool=False, 
    jsonfield:str="meta"
    ):
    """Load a GeoJSON dictionary to a table described by a Django model.

    Args:
        geojson_as_dict (dict): geojson to load
        model_class (Model): target model
        field_mapping (dict): source property name: target model field name
        geometry_field (str, optional): model geometry field name. Defaults to "geom".
        dump_extra_to_jsonfield (bool, optional): dump any properties not specified in field map to JSON field in the model. Defaults to False.
        jsonfield (str, optional): name of the JSON field that will be used if dump_extra_to_jsonfield is True. Defaults to "meta".
    """    

    for f in geojson_as_dict.get('features', []):

        props = f.get('properties', {})

        # properties specified in the field field_mapping
        model_kwargs = {
            target: props.get(source)
            for source, target in field_mapping.items()
        }

        # extra properties
        if dump_extra_to_jsonfield:
            model_kwargs[jsonfield] = {k: v for k, v in props.items() if k not in field_mapping.keys()}

        # geometry
        g = GEOSGeometry(json.dumps(f.get('geometry')))
        model_kwargs[geometry_field] = g

        m = model_class(**model_kwargs)
        print(m)
        m.save()