from dataclasses import dataclass, asdict
from typing import Optional, Union, Literal
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.conf import settings
from rest_framework import routers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import api_view
import requests
import xmltodict

from .services import authenticate_mds_sso, get_ags_token

# -------------------------------------------------------------------
# API ROOT VIEW

class ApiRouterRootView(routers.APIRootView):

    def get_view_name(self):
        return "3RWW Sewer Atlas API"

    def get_view_description(self, html=True):
        text = """<p>The 3RWW Sewer Atlas API provides methods for tapping data and services related to 3 Rivers Wet Weather Sewer Atlas outside of the Esri ArcGIS ecosystem.</p>"""
        if html:
            return mark_safe(text)
        else:
            return text

class ApiDefaultRouter(routers.DefaultRouter):
    APIRootView = ApiRouterRootView



@dataclass
class AuthResponse: # https://github.com/omniti-labs/jsend
    status: Literal['success', 'fail', 'error']
    data: Optional[Union[dict, list]] = None


@api_view(["POST"])
def atlas_auth(request:Request):
    """authenticate via 3RWW MDS SSO and get a token for the 3RWW's ArcGIS Server.
    """
    # get the parameters from the body, falling back to the querystring
    src = request.data.get('src', request.POST.get('src'))
    idStr = request.data.get('idStr', request.POST.get('idStr'))
    
    # some defaults
    mds_message, mds_authenticated, esri_ags_token, esri_ags_message = None, None, None, None
    status = "fail"
    
    # authenticate with MDS SSO
    mds_message, mds_authenticated = authenticate_mds_sso(src, idStr)
    
    # get the AGS token
    if mds_authenticated:
        esri_ags_token, esri_ags_message = get_ags_token(token_name="3RWW Esri ArcGIS Server")
        # if we have a token, success
        if esri_ags_token:
            status = "success"

    response_data = AuthResponse(
        status=status,
        data=dict(
            mds=dict(
                message=mds_message, 
                token=idStr, 
                authenticated=mds_authenticated
            ),
            ags=dict(
                message=esri_ags_message, 
                token=esri_ags_token
            ),
            ago=dict(
                message="Not implemented yet.", 
                token=None
            )
        )
    )

    return Response(response_data)