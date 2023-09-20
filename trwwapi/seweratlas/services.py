from django.conf import settings
import requests
import xmltodict

def authenticate_mds_sso(
        src:str=None, 
        idStr:str=None
    ):
    """Given a src and idStr parameter returned by the authenticate a user with the MDS SSO 
    server. 

    Args:
        src (str, optional): source string. Defaults to None.
        idStr (str, optional): ID String (MDS token). Defaults to None.

    Returns:
        _type_: _description_
    """
    if src and idStr:
        # print("User has logged in with MDS.")
        # try to talk with the SSO server
        # print("Authenticating user with SSO server...")
        response = requests.post(
            settings.MDS_SSO_REST,
            params= {
                "idStr": idStr,
                "org": settings.MDS_ORG_KEY,
                #"cmd": "VerifySSOIDStr" # not sure what this does; used by the orig Rainways
            }
        )
        # response.content returns a bytes literal; utf-8 with a BOM.
        # b = response.content
        #  Need to remove BOM in order to parse to XML to JSON
        r = response.content.decode('utf-8-sig')
        # parse to json
        j = xmltodict.parse(r)
        # print("SSO confirmation", j)
        # if the response contains this:
        if j['RESPONSE']['@MESSAGE'] == 'Authentication Successful':
            return j['RESPONSE'], True
        else:
            # otherwise, login was not successful. add this:
            # session["logged_in"] = False
            # #redirect to the login page.
            # print("SSO confirmation failed.")
            # return redirect(url_for('login'))
            return j['RESPONSE'], False
    else:
        return "No parameters supplied", False

def get_ags_token(
        url=settings.ROK_AUTH_URL,
        username=settings.ROK_USER,
        password=settings.ROK_PW,
        client=settings.ROK_CLIENT_TYPE,
        referer=settings.ROK_REFERER_URL,
        token_name='rsi_token',
        expiration=settings.ESRI_APP_TOKEN_EXPIRATION
    ):
    """Requests an ArcGIS Server Token from the ROK server.
    """
    #if token_name not in session:
    try:
        params = {
            'username': username,
            'password': password,
            'client': client,
            'referer': referer,
            'expiration': int(expiration),
            'f': 'json',
        }
        response = requests.post(url, data=params)
        token = response.json()
        message = f"{token_name} token acquired"
        # print(message, token)
        return token, message
    except:
        return None, "Failed to acquire token."

def get_agol_token():
    """requests and returns an ArcGIS Token for the pre-registered application.
    Client id and secrets are managed through the ArcGIS Developer's console.
    """
    params = {
        'client_id': settings.ESRI_APP_CLIENT_ID,
        'client_secret': settings.ESRI_APP_CLIENT_SECRET,
        'grant_type': "client_credentials"
    }
    request = requests.get(
        'https://www.arcgis.com/sharing/oauth2/token',
        params=params
    )
    token = request.json()
    # print("AGOL token acquired: {0}".format(token))
    return token
