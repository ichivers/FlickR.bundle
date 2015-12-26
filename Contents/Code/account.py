import re, cgi, urllib, httplib, sys, cookielib, pickle, urllib2, oauth, os

FLICKR_SERVER = 'www.flickr.com'
FLICKR_PORT   = 443

FLICKR_VERSION = "1.0"

REQUEST_TOKEN_URL = 'https://www.flickr.com/services/oauth/request_token'
ACCESS_TOKEN_URL  = 'https://www.flickr.com/services/oauth/access_token'
AUTHORIZATION_URL = 'https://www.flickr.com/services/oauth/authorize'
API_URL = 'https://api.flickr.com/services/rest'

CONSUMER_KEY    = 'a16a28656210dd119d61bb46b0c519da'
CONSUMER_SECRET = '262da3f39098bcd1'

###################################################################################################

class FlickRAuthToken(oauth.OAuthToken):  
  app_name = None
  user_id = None
  verifier = None

  def __init__(self, key, secret, app_name=None, user_id=None, verifier=None):
    self.app_name = 'Plex'
    self.user_id = user_id
    self.verifier = None
   
    oauth.OAuthToken.__init__(self, key, secret)

  def to_string(self):
    return oauth.OAuthToken.to_string(self)

  @staticmethod
  def from_string(s):
    params = cgi.parse_qs(s, keep_blank_values = False)
    
    key = params['oauth_token'][0]
    secret = params['oauth_token_secret'][0]    
    
    if 'application_name' in params:
      app_name = params['application_name'][0]
    else:
      app_name = None

    if 'user_id' in params:
      user_id = params['user_id'][0]
    else:
      user_id = None

    return FlickRAuthToken(key, secret, app_name, user_id)

  def __str__(self):
    return self.to_string()

class FlickRRequest(object):

  server = FLICKR_SERVER
  port = FLICKR_PORT
  request_token_url = REQUEST_TOKEN_URL
  access_token_url = ACCESS_TOKEN_URL
  authorization_url = AUTHORIZATION_URL
  api_url = API_URL
  signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()
  api_version = FLICKR_VERSION

  def __init__(self, consumer_key = CONSUMER_KEY, consumer_secret = CONSUMER_SECRET):
    self.consumer_key = consumer_key
    self.consumer_secret = consumer_secret

    self.connection = httplib.HTTPSConnection("%s:%d" % (self.server, self.port))
    self.consumer = oauth.OAuthConsumer(self.consumer_key, self.consumer_secret)

  def get_request_token(self):
    defaults = {
      'oauth_callback': "http://127.0.0.1/"
    }
    
    req = oauth.OAuthRequest.from_consumer_and_token(self.consumer, http_url = self.request_token_url, parameters = defaults)
    req.sign_request(self.signature_method, self.consumer, None)
    
    self.connection.request(req.http_method, req.to_url())
    response = self.connection.getresponse()
    token = FlickRAuthToken.from_string(response.read())

    self.connection.close()

    return token

  def get_access_token(self, req_token): 
    defaults = {
      'oauth_token': req_token.key,
      'oauth_verifier': req_token.verifier
    }    
    req = oauth.OAuthRequest.from_consumer_and_token(self.consumer, http_url = self.access_token_url, parameters = defaults)
    req.sign_request(self.signature_method, self.consumer, req_token)    
    self.connection.request(req.http_method, req.to_url())
    response = self.connection.getresponse()   
    token = FlickRAuthToken.from_string(response.read())

    self.connection.close()

    return token

  def generate_authorization_url(self, req_token):
    params = {'application_name': req_token.app_name, 'oauth_consumer_key': self.consumer_key}
    req = oauth.OAuthRequest.from_token_and_callback(token = req_token, http_url = self.authorization_url, parameters = params)
    return req.to_url()

  def make_query(self, access_token = None, method = "GET", query = "", params = None, returnURL = True):
    if params is None:
      params = {}

    if query.startswith('https://'):
      url = query
    else:
      url = self.api_url + query
    
    params['oauth_consumer_key'] = self.consumer_key

    req = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token = access_token, http_method = method, http_url = url, parameters = params)
    req.sign_request(self.signature_method, self.consumer, access_token)

    if method == 'GET' or method == 'PUT' or method == 'DELETE':
      if returnURL:
        return req.to_url()
      else:
        self.connection.request(method, req.to_url())        

    elif method == 'POST':
      headers = {'Content-Type': 'application/x-www-form-urlencoded'}
      self.connection.request(method, url, body = req.to_postdata(), headers = headers)
    else:
      return None

    return self.connection.getresponse()

class NoRedirection(urllib2.HTTPErrorProcessor):

    def http_response(self, request, response):
        return response

    https_response = http_response

class Account(object):

  @staticmethod
  def save_cookies(requests_cookiejar, filename):
    with open(filename, 'wb') as f:
        pickle.dump(requests_cookiejar, f)

  def load_cookies(filename):
    with open(filename, 'rb') as f:
        return pickle.load(f)

  @staticmethod
  def LoggedIn():
    username = Prefs['username']
    password = Prefs['password']

    if not username or not password:
      return False

    if 'accesstoken' in Dict:
      access_token = FlickRAuthToken.from_string(Dict['accesstoken'])
      request = FlickRRequest()
      
      defaults = {
        'nojsoncallback': 1,
        'format': 'json',
        'method': 'flickr.test.login'
      }
      
      response = request.make_query(access_token = access_token, query = 'https://api.flickr.com/services/rest', params = defaults, returnURL = False)
      if response.status == 401:
        del Dict['accesstoken']
        Dict.Save()
        return False
      else:
        return True
    return False

  @staticmethod
  def TryLogIn():
    # If we're already logged in, no need to try again...
    if Account.LoggedIn():
      return True

    username = Prefs['username']
    password = Prefs['password']
    cookie_filename = "flickr.cookie"
    jar = cookielib.MozillaCookieJar(cookie_filename)
    if os.access(cookie_filename, os.F_OK):
            jar.load()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))
    opener.addheaders = [
            ('User-agent', ('Mozilla/4.0 (compatible; MSIE 6.0; '
                           'Windows NT 5.2; .NET CLR 1.1.4322)'))
    ]
    if not username or not password:
      return False

    try:
      # Get Request Token
      request = FlickRRequest()
      request_token = request.get_request_token()         
      # Get login page 
      urlrequest = urllib2.Request('https://login.yahoo.com')
      page = opener.open(urlrequest)            
      source = page.read()
      try:
        uuid = re.search('<input name="_uuid" type="hidden" value="(.+)">', source).group(1)
      except AttributeError:
        Log("Can't find uuid")
      try:
        crumb = re.search('<input name="_crumb" type="hidden" value="(.+)">', source).group(1)
      except AttributeError:
        Log("Can't find crumb")
      try:
        ts = re.search('<input name="_ts" type="hidden" value="(.+)">', source).group(1)
      except AttributeError:
        Log("Can't find ts")
      # Post login form      
      headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
      params = {
        'username': username,
        'passwd': password,
        'countrycode': 1,
        '.persistent': 'y',
        '_format': 'json',
        '_uuid' : uuid,
        '_ts': ts,
        '_crumb': crumb
      }      
      urlrequest = urllib2.Request('https://login.yahoo.com', urllib.urlencode(params), headers)     
      page = opener.open(urlrequest)  
      
      # Get authorization page
      urlrequest = urllib2.Request(AUTHORIZATION_URL + '?oauth_token=' + request_token.key)     
      page = opener.open(urlrequest)            
      source = page.read()
      try:
        magic_cookie = re.search('<input type="hidden" name="magic_cookie" value="(.+)" />', source).group(1)
      except AttributeError:
        Log("Can't find magic_cookie")
      
      # Post authorization form
      params = {
        'done_oauth': "1",
        'done_auth': "1",
        'perms': 'write',
        'oauth_token': request_token.key,
        'api_key': CONSUMER_KEY,
        'magic_cookie': magic_cookie}
      headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}                      
      urlrequest = urllib2.Request('https://www.flickr.com/services/oauth/authorize.gne', urllib.urlencode(params), headers)
      opener = urllib2.build_opener(NoRedirection, urllib2.HTTPCookieProcessor(jar))
      page = opener.open(urlrequest)      
      location = page.info().getheader('Location')
      try:
        oauth_verifier = re.search('verifier=(.+)', location).group(1)
      except AttributeError:
        Log("Can't find oauth_verifier")
      request_token.verifier = oauth_verifier    
      access_token = request.get_access_token(request_token)
      Dict['accesstoken'] = access_token.to_string()      
      Dict.Save()

      return Account.LoggedIn()

    except:
      Log.Exception("An error occurred while attempting to determine login status")
      return False

  @staticmethod
  def GetUserId():

    request = FlickRRequest()
    access_token = FlickRAuthToken.from_string(Dict['accesstoken'])
    url = request.make_query(access_token = access_token, method = 'GET', query = 'https://flickr.com/users/current', params = { 'v': '2' })

    details = XML.ElementFromURL(url)
    user_url = details.xpath('//resource/link')[0].get('href')

    return re.match('https://(.)+\.flickr.com/users/(?P<id>.+)', user_url).groupdict()['id']

  @staticmethod
  def GetAPIURL(url, params = {}):

    request = NetflixRequest()
    access_token = FlickRAuthToken.from_string(Dict['accesstoken'])
    return request.make_query(access_token = access_token, method = 'GET', query = url, params = params, returnURL = True)

  @staticmethod
  def IDFromURL(url):
    return re.match('https://(.)+\.flickr.com/.+/(?P<id>[0-9]+)', url).groupdict()['id']