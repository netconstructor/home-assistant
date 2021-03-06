"""
test.test_component_switch
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests switch component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import os

import homeassistant as ha
import homeassistant.loader as loader
import homeassistant.util as util
import homeassistant.components as components
import homeassistant.components.light as light

import mock_toggledevice_platform

from helper import mock_service, get_test_home_assistant


class TestLight(unittest.TestCase):
    """ Test the switch module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()
        loader.prepare(self.hass)
        loader.set_component('light.test', mock_toggledevice_platform)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass._pool.stop()

        user_light_file = self.hass.get_config_path(light.LIGHT_PROFILES_FILE)

        if os.path.isfile(user_light_file):
            os.remove(user_light_file)

    def test_methods(self):
        """ Test if methods call the services as expected. """
        # Test is_on
        self.hass.states.set('light.test', components.STATE_ON)
        self.assertTrue(light.is_on(self.hass, 'light.test'))

        self.hass.states.set('light.test', components.STATE_OFF)
        self.assertFalse(light.is_on(self.hass, 'light.test'))

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, components.STATE_ON)
        self.assertTrue(light.is_on(self.hass))

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, components.STATE_OFF)
        self.assertFalse(light.is_on(self.hass))

        # Test turn_on
        turn_on_calls = mock_service(
            self.hass, light.DOMAIN, components.SERVICE_TURN_ON)

        light.turn_on(
            self.hass,
            entity_id='entity_id_val',
            transition='transition_val',
            brightness='brightness_val',
            rgb_color='rgb_color_val',
            xy_color='xy_color_val',
            profile='profile_val')

        self.hass._pool.block_till_done()

        self.assertEqual(1, len(turn_on_calls))
        call = turn_on_calls[-1]

        self.assertEqual(light.DOMAIN, call.domain)
        self.assertEqual(components.SERVICE_TURN_ON, call.service)
        self.assertEqual('entity_id_val', call.data[components.ATTR_ENTITY_ID])
        self.assertEqual('transition_val', call.data[light.ATTR_TRANSITION])
        self.assertEqual('brightness_val', call.data[light.ATTR_BRIGHTNESS])
        self.assertEqual('rgb_color_val', call.data[light.ATTR_RGB_COLOR])
        self.assertEqual('xy_color_val', call.data[light.ATTR_XY_COLOR])
        self.assertEqual('profile_val', call.data[light.ATTR_PROFILE])

        # Test turn_off
        turn_off_calls = mock_service(
            self.hass, light.DOMAIN, components.SERVICE_TURN_OFF)

        light.turn_off(
            self.hass, entity_id='entity_id_val', transition='transition_val')

        self.hass._pool.block_till_done()

        self.assertEqual(1, len(turn_off_calls))
        call = turn_off_calls[-1]

        self.assertEqual(light.DOMAIN, call.domain)
        self.assertEqual(components.SERVICE_TURN_OFF, call.service)
        self.assertEqual('entity_id_val', call.data[components.ATTR_ENTITY_ID])
        self.assertEqual('transition_val', call.data[light.ATTR_TRANSITION])

    def test_services(self):
        """ Test the provided services. """
        mock_toggledevice_platform.init()
        self.assertTrue(
            light.setup(self.hass, {light.DOMAIN: {ha.CONF_TYPE: 'test'}}))

        dev1, dev2, dev3 = mock_toggledevice_platform.get_lights(None, None)

        # Test init
        self.assertTrue(light.is_on(self.hass, dev1.entity_id))
        self.assertFalse(light.is_on(self.hass, dev2.entity_id))
        self.assertFalse(light.is_on(self.hass, dev3.entity_id))

        # Test basic turn_on, turn_off services
        light.turn_off(self.hass, entity_id=dev1.entity_id)
        light.turn_on(self.hass, entity_id=dev2.entity_id)

        self.hass._pool.block_till_done()

        self.assertFalse(light.is_on(self.hass, dev1.entity_id))
        self.assertTrue(light.is_on(self.hass, dev2.entity_id))

        # turn on all lights
        light.turn_on(self.hass)

        self.hass._pool.block_till_done()

        self.assertTrue(light.is_on(self.hass, dev1.entity_id))
        self.assertTrue(light.is_on(self.hass, dev2.entity_id))
        self.assertTrue(light.is_on(self.hass, dev3.entity_id))

        # turn off all lights
        light.turn_off(self.hass)

        self.hass._pool.block_till_done()

        self.assertFalse(light.is_on(self.hass, dev1.entity_id))
        self.assertFalse(light.is_on(self.hass, dev2.entity_id))
        self.assertFalse(light.is_on(self.hass, dev3.entity_id))

        # Ensure all attributes process correctly
        light.turn_on(self.hass, dev1.entity_id,
                      transition=10, brightness=20)
        light.turn_on(
            self.hass, dev2.entity_id, rgb_color=[255, 255, 255])
        light.turn_on(self.hass, dev3.entity_id, xy_color=[.4, .6])

        self.hass._pool.block_till_done()

        method, data = dev1.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_TRANSITION: 10,
             light.ATTR_BRIGHTNESS: 20},
            data)

        method, data = dev2.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_XY_COLOR: util.color_RGB_to_xy(255, 255, 255)},
            data)

        method, data = dev3.last_call('turn_on')
        self.assertEqual({light.ATTR_XY_COLOR: [.4, .6]}, data)

        # One of the light profiles
        prof_name, prof_x, prof_y, prof_bri = 'relax', 0.5119, 0.4147, 144

        # Test light profiles
        light.turn_on(self.hass, dev1.entity_id, profile=prof_name)
        # Specify a profile and attributes to overwrite it
        light.turn_on(
            self.hass, dev2.entity_id,
            profile=prof_name, brightness=100, xy_color=[.4, .6])

        self.hass._pool.block_till_done()

        method, data = dev1.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_BRIGHTNESS: prof_bri,
             light.ATTR_XY_COLOR: [prof_x, prof_y]},
            data)

        method, data = dev2.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_BRIGHTNESS: 100,
             light.ATTR_XY_COLOR: [.4, .6]},
            data)

        # Test shitty data
        light.turn_on(self.hass, dev1.entity_id, profile="nonexisting")
        light.turn_on(self.hass, dev2.entity_id, xy_color=["bla-di-bla", 5])
        light.turn_on(self.hass, dev3.entity_id, rgb_color=[255, None, 2])

        self.hass._pool.block_till_done()

        method, data = dev1.last_call('turn_on')
        self.assertEqual({}, data)

        method, data = dev2.last_call('turn_on')
        self.assertEqual({}, data)

        method, data = dev3.last_call('turn_on')
        self.assertEqual({}, data)

        # faulty attributes should not overwrite profile data
        light.turn_on(
            self.hass, dev1.entity_id,
            profile=prof_name, brightness='bright', rgb_color='yellowish')

        self.hass._pool.block_till_done()

        method, data = dev1.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_BRIGHTNESS: prof_bri,
             light.ATTR_XY_COLOR: [prof_x, prof_y]},
            data)

    def test_setup(self):
        """ Test the setup method. """
        # Bogus config
        self.assertFalse(light.setup(self.hass, {}))

        self.assertFalse(light.setup(self.hass, {light.DOMAIN: {}}))

        # Test with non-existing component
        self.assertFalse(light.setup(
            self.hass, {light.DOMAIN: {ha.CONF_TYPE: 'nonexisting'}}
        ))

        # Test if light component returns 0 lightes
        mock_toggledevice_platform.init(True)

        self.assertEqual(
            [], mock_toggledevice_platform.get_lights(None, None))

        self.assertFalse(light.setup(
            self.hass, {light.DOMAIN: {ha.CONF_TYPE: 'test'}}
        ))

    def test_light_profiles(self):
        """ Test light profiles. """
        mock_toggledevice_platform.init()

        user_light_file = self.hass.get_config_path(light.LIGHT_PROFILES_FILE)

        # Setup a wrong light file
        with open(user_light_file, 'w') as user_file:
            user_file.write('id,x,y,brightness\n')
            user_file.write('I,WILL,NOT,WORK\n')

        self.assertFalse(light.setup(
            self.hass, {light.DOMAIN: {ha.CONF_TYPE: 'test'}}
        ))

        # Clean up broken file
        os.remove(user_light_file)

        with open(user_light_file, 'w') as user_file:
            user_file.write('id,x,y,brightness\n')
            user_file.write('test,.4,.6,100\n')

        self.assertTrue(light.setup(
            self.hass, {light.DOMAIN: {ha.CONF_TYPE: 'test'}}
        ))

        dev1, dev2, dev3 = mock_toggledevice_platform.get_lights(None, None)

        light.turn_on(self.hass, dev1.entity_id, profile='test')

        self.hass._pool.block_till_done()

        method, data = dev1.last_call('turn_on')

        self.assertEqual(
            {light.ATTR_XY_COLOR: [.4, .6], light.ATTR_BRIGHTNESS: 100},
            data)
