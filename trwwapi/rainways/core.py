"""Rainways core logic
"""

from typing import List, Tuple
from dataclasses import field
from datetime import datetime

from marshmallow_dataclass import dataclass as mdc
import requests
import rasterio
from rasterio import mask as rasterio_mask
import geopandas as gpd
import numpy as np
import petl as etl
from codetiming import Timer
from dateutil.relativedelta import relativedelta
import ray

from ..rainfall.api_v2.core import query_one_sensor_rollup_monthly
from ..rainfall.models import (
    RtrrObservation, 
    Pixel
)
from ..common.config import (
    RAINWAYS_DEFAULT_CRS, 
    RAINWAYS_RESOURCES # TODO: replace with database query
)


@mdc
class VectorSummaryStat:
    desc: str = None
    val: float = None
    unit: str = None


@mdc
class RasterSummaryStat:
    min: float = None
    max: float = None
    avg: float = None
    std: float = None


@mdc
class RwPublicResult:
    """data returned for the AOI-based analysis for the general-public app
    """
    
    soils: List[dict] = field(default_factory=list)
    sustain: List[dict] = field(default_factory=list)
    slope: List[RasterSummaryStat] = field(default_factory=list)
    elev: List[RasterSummaryStat] = field(default_factory=list)
    rainfall: List[dict] = field(default_factory=list)


class RwCore():
    
    def __init__(self) -> None:
        self.status = 'success'
        self.messages = []
        ray.init()

    def clip_cog(
        self, 
        cog_on_s3:str, 
        clipping_mask_gdf:gpd.GeoDataFrame, 
        reproj_mask_to:int=3857
    ) -> Tuple[bool, np.ma.MaskedArray]:
        """Clip a Cloud-Optimized GeoTiff (COG) using a geodataframe containing
        polygon.

        Args:
            cog_on_s3 (str): path to the raster on AWS S3. Can be s3:// or https:// depending on permission
            clipping_mask_gdf (gpd.GeoDataFrame): GeoDataframe containing clipping geometries
            reproj_mask_to (int, optional): projection of the raster, to which the clipping geometry will be reprojected if it doesn't match. Defaults to EPSG 3857.

        Returns:
            np.ma.MaskedArray: [description]
        """

        try:
            # reproject the clipping mask if it's not already what it needs to be
            if not clipping_mask_gdf.crs.is_exact_same(reproj_mask_to):
                clipping_mask_gdf = clipping_mask_gdf.to_crs(epsg=reproj_mask_to)

            # open the COG (see https://rasterio.readthedocs.io/en/latest/topics/vsi.html#aws-s3)
            # (note that internally rasterio uses boto3, which expects AWS access credentials
            # to be available in the environment if the object or bucket is not public.)
            with rasterio.open(cog_on_s3) as src:
                # read just the geometry of the input geojson features
                # shapes = [f["geometry"] for f in geojson_dict['features']]
                shapes = list(clipping_mask_gdf.geometry)
                # read the raster data in using rasterio's mask function
                arr, out_transform = rasterio_mask.mask(src, shapes, crop=True, filled=False)

            return True, arr
        except Exception as e:
            return False, str(e)
            
    def clip_and_dissolve_esri_feature_layer(
        self,
        feature_layer_query_url: str,
        feature_layer_fields: list,
        clipping_mask_gdf: gpd.GeoDataFrame,
        clipping_mask_bbox: list,
        in_epsg_code: int = 4326,
        out_epsg_code: int = RAINWAYS_DEFAULT_CRS,
        geometry_field: str = "geometry"
        ) -> Tuple[bool, gpd.GeoDataFrame]:
        """[summary]

        Args:

            feature_layer_query_url
            geojson_dict (dict):

        Args:
            feature_layer_query_url (str): URL to the Esri feature layer query endpoint, e.g., ending with .../FeatureServer/0/query
            clipping_mask_gdf (dict): clipping geometry as a geodataframe
            clipping_mask_bbox (list): bounding box coordinates of the clipping geometry
            in_epsg_code (int, optional): [description]. Defaults to RAINWAYS_DEFAULT_CRS.
            out_epsg_code (int, optional): [description]. Defaults to RAINWAYS_DEFAULT_CRS.
            feature_layer_fields (list): list of fields to return from the feature layer and use for the. Defaults to "*" (all field).
        """

        # First, filter: use the bounding box to find features in the service 
        # that overlap our geojson. This speeds things up by limiting the 
        # number of features we have to request over the wire for the 
        # intersect / clipping.


        overlapping_target_features = requests.get(
            feature_layer_query_url,
            params=dict(
                where="1=1",
                outFields=",".join([str(f) for f in feature_layer_fields]),
                returnGeometry='true',
                geometry=','.join([str(x) for x in clipping_mask_bbox]),
                inSR=in_epsg_code,
                geometryType='esriGeometryEnvelope',
                spatialRel='esriSpatialRelIntersects',
                outSR=out_epsg_code,
                f='geojson'
            )
        ) # this returns a requests.Response object
        # print(overlapping_target_features.json())
        if 'error' in overlapping_target_features.json().keys():
            return False, overlapping_target_features.json()

        # load the geojson into a geodataframe
        # with fiona.BytesCollection(bytes(overlapping_target_features.content)) as f:
        #     overlapping_target_features_gdf = gpd.GeoDataFrame\
        #         .from_features(f, crs=f.crs)\
        #         .set_geometry('geometry', inplace=True)

        overlapping_target_features_gdf = gpd.GeoDataFrame\
            .from_features(
                overlapping_target_features.json(), 
                crs=out_epsg_code
            )
        # print(overlapping_target_features_gdf)
            #.set_geometry('geometry', inplace=True)

        # reproject the clipping mask if it's not already what it needs to be
        if not clipping_mask_gdf.crs.is_exact_same(out_epsg_code):
            clipping_mask_gdf.to_crs(epsg=out_epsg_code, inplace=True)
        # print(clipping_mask_gdf)

        # Overlay the two dataframes and dissolve on the fields specified
        dissolved = gpd\
            .overlay(clipping_mask_gdf[[geometry_field]], overlapping_target_features_gdf, how='intersection')\
            .dissolve(by=feature_layer_fields, aggfunc='sum')\
            .reset_index()
        # calculate the area of the resulting geometries (uses units of CRS)
        dissolved['area'] = dissolved.area
        # then calculate the percent of total for each area
        total_area = dissolved['area'].sum()
        dissolved['area_pct'] = dissolved['area'] / total_area
        
        return True, dissolved

    def shutdown(self):
        ray.shutdown()

class RwPublicAnalysis(RwCore):

    def __init__(
        self, 
        aoi_geojson, 
        crs={'init': f'epsg:{RAINWAYS_DEFAULT_CRS}'}, 
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        
        # read in the AOI geojson to a geodataframe on init
        self.aoi_geojson = aoi_geojson

        # read it into a geodataframe, explicitly setting the CRS
        # so we can reproject as needed
        if 'crs' in self.aoi_geojson.keys():
            # get the CRS from the geojson (this is not spec)
            src_crs = self.aoi_geojson['crs']['properties']['name']
        else:
            # assume it is 4326 (this is spec)
            src_crs = "EPSG:4326"
        
        self.aoi_gdf = gpd.GeoDataFrame\
            .from_features(
                self.aoi_geojson, 
                crs=src_crs
            )\
            .set_geometry('geometry')
        
        # get the bounding box
        self.aoi_bbox = list(self.aoi_gdf.total_bounds)

        # derive the epsg code from the pyproj CRS object in the geodataframe
        self.aoi_gdf_epsg = int(self.aoi_gdf.crs.to_authority()[1])

        # print(self.aoi_gdf, self.aoi_bbox, self.aoi_gdf.crs)

        # instantiate a results dataclass
        self.results = RwPublicResult()

    
    # @Timer(name="rwpub__soil_summary", text="{name}: {:.4f}s")
    @ray.remote
    def soil_summary(self):

        success, result = self.clip_and_dissolve_esri_feature_layer(
            feature_layer_query_url=RAINWAYS_RESOURCES['soils'],
            feature_layer_fields=['SOIL_HYDRO'],
            clipping_mask_gdf=self.aoi_gdf,
            clipping_mask_bbox=self.aoi_bbox,
            in_epsg_code=self.aoi_gdf_epsg
        )
        if success:
            # post-process the dataframe; add additional field
            t = etl\
                .fromdataframe(result)\
                .cutout('geometry')\
                .addfield('area_acres', lambda r: r['area'] * 0.00002295682)

            # convert to list of dictionaries
            results = list(etl.dicts(t))
            
            self.results.soils.extend(results)

            return results

        else:
            
            self.status = 'failed'
            messages = result['error']['details'] + result['message']
            self.messages.extend(messages)

        return None

    # @Timer(name="rwpub__sustain_summary", text="{name}: {:.4f}s")
    @ray.remote
    def sustain_summary(self):
        success, result = self.clip_and_dissolve_esri_feature_layer(
            feature_layer_query_url=RAINWAYS_RESOURCES['sustain'],
            feature_layer_fields=['GI_Type'],
            clipping_mask_gdf=self.aoi_gdf,
            clipping_mask_bbox=self.aoi_bbox,
            in_epsg_code=self.aoi_gdf_epsg
        )
        if success:
            # post-process the dataframe; add additional field
            t = etl\
                .fromdataframe(result)\
                .cutout('geometry')\
                .addfield('area_acres', lambda r: r['area'] * 0.00002295682)

            # convert to list of dictionaries
            results = list(etl.dicts(t))
            
            self.results.sustain.extend(results)

            return results

        else:
            self.status = 'failed'
            messages = result['error']['details'] + result['message']
            self.messages.extend(messages)

        return None

    # @Timer(name="rwpub__slope_summary", text="{name}: {:.4f}s")
    @ray.remote
    def slope_summary(self):

        success, result = self.clip_cog(
            cog_on_s3=RAINWAYS_RESOURCES['slope'],
            clipping_mask_gdf=self.aoi_gdf,
            reproj_mask_to=3857
        )

        if success:

            results = RasterSummaryStat(
                avg=result.mean(),
                max=result.max(),
                min=result.min()
            )

            self.results.slope.append(results)

            return results

        else:
            self.status = 'failed'
            self.messages.append(result)
        
        return None


    # @Timer(name="rwpub__rainfall_summary", text="{name}: {:.4f}s")
    @ray.remote
    def rainfall_summary(self):

        # get the centroid of all provided geometry in the same coordinate system as the pixels
        pt = self.aoi_gdf.to_crs(epsg=Pixel.geom.field.srid).unary_union.centroid.wkt

        # use it to find the overlapping containing radar rainfall pixel
        try:
            sensor_id = Pixel.objects.get(geom__contains=pt).pixel_id
        except Pixel.DoesNotExist as e:
            self.status = 'failed'
            self.messages.extend([str(e), "Radar rainfall data is not available for for this location from 3RWW."])
            return None

        try:
            # get datetimes for the last six months
            end_dt = datetime.now().replace(day=1,hour=0,minute=0, second=0,microsecond=0)
            start_dt = end_dt + relativedelta(months=-6)
            # query the single sensor and get back a monthly rainfall totals
            results = query_one_sensor_rollup_monthly(
                RtrrObservation, 
                [start_dt, end_dt], 
                sensor_id
            )
            self.results.rainfall.extend(results)
            return results
        except RtrrObservation.DoesNotExist as e:
            self.status = 'failed'
            self.messages.extend([str(e), "Radar rainfall data is not available for for this location from 3RWW."])
            return None

        return None


    def run(self):

        slope_summary = RwPublicAnalysis.slope_summary.remote(self),
        soil_summary = RwPublicAnalysis.soil_summary.remote(self),
        sustain_summary = RwPublicAnalysis.sustain_summary.remote(self),
        rainfall_summary = RwPublicAnalysis.rainfall_summary.remote(self)

        slopes, soils, sustains, rainfalls = ray.get([
            slope_summary,
            soil_summary,
            sustain_summary,
            rainfall_summary
        ])