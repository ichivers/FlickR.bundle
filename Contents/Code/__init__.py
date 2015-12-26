import cgi, urllib, string
import webbrowser
import xml.etree.ElementTree as ET
from account import Account
from account import FlickRAuthToken
from account import FlickRRequest
####################################################################################################
PREFIX = "/photos/flickr"
TITLE = "FlickR Channel"
ART = 'art-flickr.jpg'
ICON = 'icon-flickr.png'
FLICKR_KEY = 'a16a28656210dd119d61bb46b0c519da'
####################################################################################################

# This function is initially called by the PMS framework to initialize the plugin. This includes
# setting up the Plugin static instance along with the displayed artwork.
def Start():
  Plugin.AddViewGroup("Pictures", viewMode="Pictures", mediaType="photos")
  # Set the default cache time
  HTTP.CacheTime = CACHE_1HOUR
  HTTP.Headers['User-Agent'] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:20.0) Gecko/20100101 Firefox/20.0"

# Setup the default breadcrumb title for the plugin
ObjectContainer.title1 = TITLE
ObjectContainer.art = R(ART)

# This main function will setup the displayed items.
# Initialize the plugin
@handler(PREFIX, TITLE, art=ART, thumb=ICON)
def MainMenu():   
  oc = ObjectContainer(no_cache = True)
  oc.add(PrefsObject(title = "Preferences"))
  # Attempt to log in
  logged_in = Account.LoggedIn()
  if not logged_in:    
    logged_in = Account.TryLogIn()
  if logged_in:
    access_token = FlickRAuthToken.from_string(Dict['accesstoken'])
    request = FlickRRequest()      
    defaults = {      
      'api_key': FLICKR_KEY,
      'format': 'rest',
      'method': 'flickr.photosets.getList',
      'primary_photo_extras': 'url_m'
    }      
    response = request.make_query(access_token = access_token, query = 'https://api.flickr.com/services/rest', params = defaults, returnURL = False)    
    photosets = ET.fromstring(response.read())
    for item in photosets.findall('.//photoset'):    
      title = item.find('./title').text     
      thumb = item.find('./primary_photo_extras').attrib['url_m']      
      photosetid = item.find('.').attrib['id']
      oc.add(DirectoryObject(key = Callback(PhotoSet, id = photosetid), title = title, thumb  = thumb))
  return oc

@route(PREFIX + '/PhotoSet', id = int)
def PhotoSet(id):  
  oc = ObjectContainer(view_group='Pictures')
  access_token = FlickRAuthToken.from_string(Dict['accesstoken'])
  request = FlickRRequest()      
  defaults = {      
    'api_key': FLICKR_KEY,
    'format': 'rest',
    'method': 'flickr.photosets.getPhotos',
    'extras': 'date_taken, url_q, url_o',
    'photoset_id': id
  }      
  response = request.make_query(access_token = access_token, query = 'https://api.flickr.com/services/rest', params = defaults, returnURL = False)
  data = response.read()    
  photos = ET.fromstring(data)
  for item in photos.findall('.//photo'):  
    thumb = item.find('.').attrib['url_q']
    id = item.find('.').attrib['id']
    date_taken = item.find('.').attrib['datetaken']
    date = Datetime.ParseDate(date_taken)
    url_o = item.find('.').attrib['url_o']
    oc.add(PhotoObject(          
      key = url_o,
      rating_key = id,
      title = date_taken,     
      thumb = thumb,
      summary = "",
      originally_available_at = date)
    )
  return oc  

def ValidatePrefs():
  Log("Flickr: ValidatePrefs")

#The End