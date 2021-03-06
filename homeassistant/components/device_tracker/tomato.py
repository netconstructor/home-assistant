""" Supports scanning a Tomato router. """
import logging
import json
from datetime import datetime, timedelta
import re
import threading

import requests

import homeassistant as ha
import homeassistant.util as util
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

CONF_HTTP_ID = "http_id"

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """ Validates config and returns a Tomato scanner. """
    if not util.validate_config(config,
                                {DOMAIN: [ha.CONF_HOST, ha.CONF_USERNAME,
                                          ha.CONF_PASSWORD, CONF_HTTP_ID]},
                                _LOGGER):
        return None

    return TomatoDeviceScanner(config[DOMAIN])


class TomatoDeviceScanner(object):
    """ This class queries a wireless router running Tomato firmware
    for connected devices.

    A description of the Tomato API can be found on
    http://paulusschoutsen.nl/blog/2013/10/tomato-api-documentation/
    """

    def __init__(self, config):
        host, http_id = config[ha.CONF_HOST], config[CONF_HTTP_ID]
        username, password = config[ha.CONF_USERNAME], config[ha.CONF_PASSWORD]

        self.req = requests.Request('POST',
                                    'http://{}/update.cgi'.format(host),
                                    data={'_http_id': http_id,
                                          'exec': 'devlist'},
                                    auth=requests.auth.HTTPBasicAuth(
                                        username, password)).prepare()

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")

        self.logger = logging.getLogger("{}.{}".format(__name__, "Tomato"))
        self.lock = threading.Lock()

        self.date_updated = None
        self.last_results = {"wldev": [], "dhcpd_lease": []}

        self.success_init = self._update_tomato_info()

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_tomato_info()

        return [item[1] for item in self.last_results['wldev']]

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """

        # Make sure there are results
        if not self.date_updated:
            self._update_tomato_info()

        filter_named = [item[0] for item in self.last_results['dhcpd_lease']
                        if item[2] == device]

        if not filter_named or not filter_named[0]:
            return None
        else:
            return filter_named[0]

    def _update_tomato_info(self):
        """ Ensures the information from the Tomato router is up to date.
            Returns boolean if scanning successful. """

        self.lock.acquire()

        # if date_updated is None or the date is too old we scan for new data
        if not self.date_updated or \
           datetime.now() - self.date_updated > MIN_TIME_BETWEEN_SCANS:

            self.logger.info("Scanning")

            try:
                response = requests.Session().send(self.req, timeout=3)

                # Calling and parsing the Tomato api here. We only need the
                # wldev and dhcpd_lease values. For API description see:
                # http://paulusschoutsen.nl/
                #   blog/2013/10/tomato-api-documentation/
                if response.status_code == 200:

                    for param, value in \
                            self.parse_api_pattern.findall(response.text):

                        if param == 'wldev' or param == 'dhcpd_lease':
                            self.last_results[param] = \
                                json.loads(value.replace("'", '"'))

                    self.date_updated = datetime.now()

                    return True

                elif response.status_code == 401:
                    # Authentication error
                    self.logger.exception((
                        "Failed to authenticate, "
                        "please check your username and password"))

                    return False

            except requests.exceptions.ConnectionError:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception((
                    "Failed to connect to the router"
                    " or invalid http_id supplied"))

                return False

            except requests.exceptions.Timeout:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception(
                    "Connection to the router timed out")

                return False

            except ValueError:
                # If json decoder could not parse the response
                self.logger.exception(
                    "Failed to parse response from router")

                return False

            finally:
                self.lock.release()

        else:
            # We acquired the lock before the IF check,
            # release it before we return True
            self.lock.release()

            return True
