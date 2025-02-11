import asyncio, io, logging, os, re, time, tempfile

import traceback

import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

import plugins


logger = logging.getLogger(__name__)


_externals = { "running": False }


# dcap = dict(DesiredCapabilities.PHANTOMJS)
# dcap["phantomjs.page.settings.userAgent"] = (
#     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.34  "
#     "(KHTML, like Gecko) PhantomJS/1.9.7 Safari/534.34"
# )


def _initialise(bot):
  plugins.register_admin_command(["twitterkey", "twittersecret", 'twitterconfig'])
  plugins.register_handler(_watch_twitter_link, type="message")


@asyncio.coroutine
def _open_file(name):
    logger.debug("opening screenshot file: {}".format(name))
    return open(name, 'rb')


@asyncio.coroutine
def _screencap(browser, url, filename):
    logger.info("screencapping {} and saving as {}".format(url, filename))
    browser.get(url)
    yield from asyncio.sleep(5)
    for i in range(10):
        try:
            # tweet = browser.find_element_by_class_name('twitter-tweet-rendered')
            tweet = browser.find_element_by_id('tweetgohere')
            loop = asyncio.get_event_loop()
            yield from loop.run_in_executor(None, tweet.screenshot, filename)
        except:
            yield from asyncio.sleep(1)
            continue
        break


    # read the resulting file into a byte array
    file_resource = yield from _open_file(filename)
    file_data = yield from loop.run_in_executor(None, file_resource.read)
    file_resource.close()
    image_data = yield from loop.run_in_executor(None, io.BytesIO, file_data)
    # yield from loop.run_in_executor(None, os.remove, filename)

    return image_data


@asyncio.coroutine
def _watch_twitter_link(bot, event, command):
    if event.user.is_self:
        return

    m = re.search("https?://(?:www\.)?twitter.com/([a-zA-Z0-9_]{1,15})/status/([0-9]+)(?=\D)?", event.text, re.IGNORECASE)
    # m = re.search("https?://(?:www\.)?twitter.com/([a-zA-Z0-9_]{1,15})/status/([0-9]+\b", event.text, re.IGNORECASE)
    if not m:
        return

    # try:
    # key = bot.memory.get_by_path(['twitter', 'key'])
    # secret = bot.memory.get_by_path(['twitter', 'secret'])
    user_id = m.group(1)
    tweet_id = m.group(2)
    url = f"file://localhost/opt/hangoutsbot/twtr.html?usr={user_id}&tid={tweet_id}"
    """get a screenshot of a user provided URL or the default URL of the hangout.
    """
    print("this is running")
    _externals["running"] = True

    if not re.match(r'^[a-zA-Z]+://', url):
        url = 'http://' + url
    filename = event.conv_id + "." + str(time.time()) +".png"
    filepath = tempfile.NamedTemporaryFile(prefix=event.conv_id, suffix=".png", delete=False).name
    logger.debug("temporary screenshot file: {}".format(filepath))

    try:
        options = Options()
        options.add_argument('--headless')
        # options.add_argument('--useragent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.34  (KHTML, like Gecko) PhantomJS/1.9.7 Safari/534.34')
        browser = webdriver.Chrome(chrome_options=options,service_log_path=os.path.devnull)
        browser.set_window_size(500,2000)
        browser.maximize_window()
    except selenium.common.exceptions.WebDriverException as e:
        yield from bot.coro_send_message(event.conv, "<i>phantomjs could not be started - is it installed?</i>".format(e))
        _externals["running"] = False
        with open(tempfile.NamedTemporaryFile(prefix=event.conv_id, suffix=".exception", delete=False).name, 'w') as fh:
            traceback.print_exc(file=fh)
        return

    try:
        loop = asyncio.get_event_loop()
        image_data = yield from _screencap(browser, url, filepath)
    except Exception as e:
        yield from bot.coro_send_message(event.conv_id, "<i>error getting screenshot</i>")
        logger.exception("screencap failed".format(url))
        _externals["running"] = False
        return
    finally:
        browser.quit()

    try:
        try:
            image_id = yield from bot.call_shared('image_upload_raw', image_data, filename=filename)
        except KeyError:
            logger.warning('image plugin not loaded - using legacy code')
            image_id = yield from bot._client.upload_image(image_data, filename=filename)
        #yield from bot._client.sendchatmessage(event.conv.id_, None, image_id=image_id)
        yield from bot.coro_send_message(event.conv.id_, "", image_id=image_id)
    except Exception as e:
        yield from bot.coro_send_message(event.conv_id, "<i>error uploading screenshot</i>")
        logger.exception("upload failed".format(url))
    finally:
        _externals["running"] = False
