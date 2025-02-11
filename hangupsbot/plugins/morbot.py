import asyncio, io, logging, os, re, time, tempfile

import traceback
import plugins

import requests

from random import choice
from textwrap import fill
from base64 import urlsafe_b64encode as b64encode

logger = logging.getLogger(__name__)


_externals = { "running": False }


SITE_URL = "https://morbotron.com"
API_URL = SITE_URL + "/api/search?q={query}"
CAPTION_URL = SITE_URL + "/api/caption?e={episode}&t={timestamp}"
MEME_URL = SITE_URL + "/meme/{episode}/{timestamp}.jpg?b64lines={caption}"
MAX_LINE = 23


# dcap = dict(DesiredCapabilities.PHANTOMJS)
# dcap["phantomjs.page.settings.userAgent"] = (
#     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.34  "
#     "(KHTML, like Gecko) PhantomJS/1.9.7 Safari/534.34"
# )


def _initialise(bot):
  plugins.register_handler(_watch_morbotron, type="message")


@asyncio.coroutine
def _watch_morbotron(bot, event, command):
    if event.user.is_self:
        return

    m = re.search("^morb(?:o|otron)?\s(.+)", event.text, re.IGNORECASE)  # look for keywords morb or morbo or morbotron
    if not m:
        return
    
    _externals["running"] = True

    # Search morbotron for scenes matching query
    search_terms = m.group(1)
    search_results = requests.get(API_URL.format(query=search_terms)).json() # consider % quoting string with urllib
    if len(search_results) == 0:
        yield from bot.coro_send_message(event.conv_id, "<i>Nothing found. Try again, for glayvin out loud!</i>")
        _externals["running"] = False
        return

    # Pick a random scene
    selection = choice(search_results)
    ep = selection['Episode']
    ts = selection['Timestamp']

    # Lookup caption associated with scene
    caption_detail = requests.get(CAPTION_URL.format(episode=ep, timestamp=ts)).json()
    cap = fill(' '.join([i['Content'] for i in caption_detail['Subtitles']]), MAX_LINE)

    # Encode caption
    url = MEME_URL.format(episode=ep, timestamp=ts, caption=b64encode(cap.encode()).decode())
    logger.debug("morbotron meme url: {}".format(url))

    # Download meme
    image_data = requests.get(url).content
    filename = event.conv_id + "." + str(time.time()) +".jpg"
    filepath = tempfile.NamedTemporaryFile(prefix=event.conv_id, suffix=".jpg", delete=False).name
    logger.debug("temporary morbotron meme file: {}".format(filepath))

    with open(filepath, 'wb') as fh:
        fh.write(image_data)

    image_data = io.BytesIO(image_data)
    
    # Upload meme to conversation
    try:
        try:
            image_id = yield from bot.call_shared('image_upload_raw', image_data, filename=filename)
        except KeyError:
            logger.warning('image plugin not loaded - using legacy code')
            image_id = yield from bot._client.upload_image(image_data, filename=filename)
        #yield from bot._client.sendchatmessage(event.conv.id_, None, image_id=image_id)
        yield from bot.coro_send_message(event.conv.id_, "", image_id=image_id)
    except Exception as e:
        yield from bot.coro_send_message(event.conv_id, "<i>error uploading meme</i>")
        logger.exception("upload failed".format(url))
    finally:
        _externals["running"] = False


"""
QU0gSSBTTyBPVVQgT0YgVE9VQ0g/Ck5PLiBJVCdTIFRIRSBDSElMRFJFTiBXSE8gQVJFIFdST05HLg==
QU0gSSBTTyBPVVQgT0YgVE9VQ0g_Ck5PLiBJVCdTIFRIRSBDSElMRFJFTiBXSE8gQVJFIFdST05HLg==
"""