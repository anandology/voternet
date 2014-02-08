"""Library to provide login using Google OAuth2 API.
"""
import web
import urllib, urllib2
import json

GOOGLE_OAUTH2_AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_OAUTH2_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
GOOGLE_OAUTH2_USERINFO_URL = 'https://www.googleapis.com/userinfo/v2/me'

class GoogleLoginError(Exception):
    pass

class GoogleLogin:
    def __init__(self):
        self.client_id = web.config.GOOGLELOGIN_CLIENT_ID
        self.client_secret = web.config.GOOGLELOGIN_CLIENT_SECRET
        self.scope = web.config.GOOGLELOGIN_SCOPE
        self.redirect_uri = web.config.GOOGLELOGIN_REDIRECT_URI

    def redirect(self):
        raise web.seeother(self.get_redirect_url())

    def get_redirect_url(self):
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope
        }
        return GOOGLE_OAUTH2_AUTH_URL + "?" + urllib.urlencode(params)

    def get_token(self, code):
        """Exchanges code for a token.

        The return value is a storage object with the following fields.

            * access_token
            * token_type (will be "Bearer")
            * expires_in (duration for which this access_token is valid)
            * refresh_token (token to refresh the access_token)
        """
        params = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }
        return self._jsonpost(GOOGLE_OAUTH2_TOKEN_URL, params)

    def _jsonget(self, url, params):
        url = url + "?" + urllib.urlencode(params)
        response = urllib2.urlopen(url).read()
        d = json.loads(response)
        return web.storage(d)

    def _jsonpost(self, url, params):
        response = urllib2.urlopen(url, urllib.urlencode(params)).read()
        d = json.loads(response)
        return web.storage(d)

    def oauth2callback(self):
        i = web.input(code=None, error=None, state=None)
        if i.code:
            return self.get_token(i.code)
            
    def get_userinfo(self, access_token):
        userinfo = self._jsonget(GOOGLE_OAUTH2_USERINFO_URL, params=dict(access_token=access_token))
        if not userinfo or userinfo.get('error'):
            raise GoogleLoginError(userinfo.get("error_description") or userinfo.get("error") or "Unknown error")
        return web.storage(userinfo)

