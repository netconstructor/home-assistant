"""
test.test_component_http
~~~~~~~~~~~~~~~~~~~~~~~~

Tests Home Assistant HTTP component does what it should do.
"""
# pylint: disable=protected-access,too-many-public-methods
import re
import unittest
import json

import requests

import homeassistant as ha
import homeassistant.remote as remote
import homeassistant.components.http as http

API_PASSWORD = "test1234"

# Somehow the socket that holds the default port does not get released
# when we close down HA in a different test case. Until I have figured
# out what is going on, let's run this test on a different port.
SERVER_PORT = 8120

HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)

HA_HEADERS = {remote.AUTH_HEADER: API_PASSWORD}

hass = None


def _url(path=""):
    """ Helper method to generate urls. """
    return HTTP_BASE_URL + path


def setUpModule():   # pylint: disable=invalid-name
    """ Initalizes a Home Assistant server. """
    global hass

    hass = ha.HomeAssistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    http.setup(hass,
               {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                              http.CONF_SERVER_PORT: SERVER_PORT}})

    hass.start()


def tearDownModule():   # pylint: disable=invalid-name
    """ Stops the Home Assistant server. """
    global hass

    hass.stop()


class TestHTTP(unittest.TestCase):
    """ Test the HTTP debug interface and API. """

    def test_get_frontend(self):
        """ Tests if we can get the frontend. """
        req = requests.get(_url(""))

        self.assertEqual(200, req.status_code)

        frontendjs = re.search(
            r'(?P<app>\/static\/frontend-[A-Za-z0-9]{32}.html)',
            req.text).groups(0)[0]

        self.assertIsNotNone(frontendjs)

        req = requests.get(_url(frontendjs))

        self.assertEqual(200, req.status_code)

    def test_api_password(self):
        """ Test if we get access denied if we omit or provide
            a wrong api password. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")))

        self.assertEqual(401, req.status_code)

        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")),
            headers={remote.AUTH_HEADER: 'wrongpassword'})

        self.assertEqual(401, req.status_code)

    def test_api_list_state_entities(self):
        """ Test if the debug interface allows us to list state entities. """
        req = requests.get(_url(remote.URL_API_STATES),
                           headers=HA_HEADERS)

        remote_data = [ha.State.from_dict(item) for item in req.json()]

        self.assertEqual(hass.states.all(), remote_data)

    def test_api_get_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test.test")),
            headers=HA_HEADERS)

        data = ha.State.from_dict(req.json())

        state = hass.states.get("test.test")

        self.assertEqual(state.state, data.state)
        self.assertEqual(state.last_changed, data.last_changed)
        self.assertEqual(state.attributes, data.attributes)

    def test_api_get_non_existing_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("does_not_exist")),
            headers=HA_HEADERS)

        self.assertEqual(404, req.status_code)

    def test_api_state_change(self):
        """ Test if we can change the state of an entity that exists. """

        hass.states.set("test.test", "not_to_be_set")

        requests.post(_url(remote.URL_API_STATES_ENTITY.format("test.test")),
                      data=json.dumps({"state": "debug_state_change2",
                                       "api_password": API_PASSWORD}))

        self.assertEqual("debug_state_change2",
                         hass.states.get("test.test").state)

    # pylint: disable=invalid-name
    def test_api_state_change_of_non_existing_entity(self):
        """ Test if the API allows us to change a state of
            a non existing entity. """

        new_state = "debug_state_change"

        req = requests.post(
            _url(remote.URL_API_STATES_ENTITY.format(
                "test_entity.that_does_not_exist")),
            data=json.dumps({"state": new_state,
                             "api_password": API_PASSWORD}))

        cur_state = (hass.states.
                     get("test_entity.that_does_not_exist").state)

        self.assertEqual(201, req.status_code)
        self.assertEqual(cur_state, new_state)

    # pylint: disable=invalid-name
    def test_api_fire_event_with_no_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        hass.listen_once_event("test.event_no_data", listener)

        requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test.event_no_data")),
            headers=HA_HEADERS)

        hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        hass.listen_once_event("test_event_with_data", listener)

        requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event_with_data")),
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_invalid_json(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):    # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        hass.listen_once_event("test_event_bad_data", listener)

        req = requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event_bad_data")),
            data=json.dumps('not an object'),
            headers=HA_HEADERS)

        hass._pool.block_till_done()

        self.assertEqual(422, req.status_code)
        self.assertEqual(0, len(test_value))

    def test_api_get_event_listeners(self):
        """ Test if we can get the list of events being listened for. """
        req = requests.get(_url(remote.URL_API_EVENTS),
                           headers=HA_HEADERS)

        local = hass.bus.listeners

        for event in req.json():
            self.assertEqual(event["listener_count"],
                             local.pop(event["event"]))

        self.assertEqual(0, len(local))

    def test_api_get_services(self):
        """ Test if we can get a dict describing current services. """
        req = requests.get(_url(remote.URL_API_SERVICES),
                           headers=HA_HEADERS)

        local_services = hass.services.services

        for serv_domain in req.json():
            local = local_services.pop(serv_domain["domain"])

            self.assertEqual(local, serv_domain["services"])

    def test_api_call_service_no_data(self):
        """ Test if the API allows us to call a service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify that our service got called. """
            test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(remote.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            headers=HA_HEADERS)

        hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))

    def test_api_call_service_with_data(self):
        """ Test if the API allows us to call a service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify that our service got called and
                that test if our data came through. """
            if "test" in service_call.data:
                test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(remote.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))
