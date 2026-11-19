# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Tests of the Neutron calls through the real clients.

requests_mock replaces only the HTTP transport, so the URL, the query, the
request body and the exception mapping are the ones of the client. Every
test runs on the python-neutronclient path and on the openstacksdk path
and expects the same result.
"""

from horizon import exceptions as horizon_exceptions
from neutronclient.common import exceptions as neutron_exc
from openstack import exceptions as sdk_exc
from openstack_dashboard import api
from openstack_dashboard import exceptions as dashboard_exceptions
from openstack_dashboard.test import helpers
import requests_mock

from neutron_log_dashboard.api import network_log
from neutron_log_dashboard.test import helpers as test

SELECTOR_ERROR = ('A log with the flow_sample output must select a security '
                  'group with resource_id and must not set target_id.')


class _ClientPathTests(object):
    """The scenarios; the subclasses choose the client path."""

    use_neutronclient = None
    not_found = None
    bad_request = None
    forbidden = None

    def setUp(self):
        super().setUp()
        patcher = helpers.mock.patch.object(
            network_log, '_use_neutronclient',
            return_value=self.use_neutronclient)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.requests = requests_mock.Mocker()
        self.requests.start()
        self.addCleanup(self.requests.stop)
        # python-neutronclient appends to the catalog URL as it is,
        # openstacksdk joins the path.
        base = api.base.url_for(self.request, 'network')
        if not self.use_neutronclient:
            base = base.rstrip('/')
        self.url = base + '/v2.0'
        self.project_id = self.request.user.project_id

    def _own(self, log, **changes):
        return dict(dict(log, project_id=self.project_id), **changes)

    def _error(self, error_type, message):
        return {'NeutronError': {'type': error_type, 'message': message,
                                 'detail': ''}}

    def _assert_shown_as_an_error(self, exc):
        # Not "unauthorized": Horizon would show a 403 page instead of
        # the message. Either recoverable, or unknown to Horizon, which
        # is handled as recoverable when the view gives a message.
        self.assertNotIsInstance(exc, dashboard_exceptions.UNAUTHORIZED)
        if self.use_neutronclient:
            self.assertIsInstance(exc, dashboard_exceptions.RECOVERABLE)

    def test_flow_log_list(self):
        logs = [self._own(log) for log in self.api_flow_logs.list()]
        self.requests.get(self.url + '/log/logs', json={'logs': logs})

        ret = network_log.flow_log_list(self.request)

        self.assertEqual([log['id'] for log in logs],
                         [log.id for log in ret])
        for log in ret:
            self.assertIsInstance(log, network_log.NetworkLog)
        self.assertEqual(
            {'output_type': ['flow_sample'],
             'project_id': [self.project_id]},
            self.requests.last_request.qs)

    def test_flow_log_list_drops_packet_logs(self):
        # A server that ignores the filter must not leak packet logs.
        logs = [self._own(log) for log in
                self.api_flow_logs.list() + self.api_packet_logs.list()]
        no_attr = self._own(self.api_packet_logs.first(), id='old')
        del no_attr['output_type']
        self.requests.get(self.url + '/log/logs',
                          json={'logs': logs + [no_attr]})

        ret = network_log.flow_log_list(self.request)

        self.assertEqual([log['id'] for log in self.api_flow_logs.list()],
                         [log.id for log in ret])

    def test_flow_log_get(self):
        log = self._own(self.api_flow_logs.first())
        self.requests.get(self.url + '/log/logs/' + log['id'],
                          json={'log': log})

        ret = network_log.flow_log_get(self.request, log['id'])

        self.assertEqual(log['id'], ret.id)
        self.assertEqual(log['resource_id'], ret.resource_id)
        self.assertTrue(ret.is_flow_log)

    def test_flow_log_get_packet_log_is_not_found(self):
        log = self._own(self.api_packet_logs.first())
        self.requests.get(self.url + '/log/logs/' + log['id'],
                          json={'log': log})

        self.assertRaises(horizon_exceptions.NotFound,
                          network_log.flow_log_get, self.request, log['id'])

    def test_flow_log_get_other_project_is_not_found(self):
        log = self._own(self.api_flow_logs.first(), project_id='other')
        self.requests.get(self.url + '/log/logs/' + log['id'],
                          json={'log': log})

        self.assertRaises(horizon_exceptions.NotFound,
                          network_log.flow_log_get, self.request, log['id'])

    def test_flow_log_get_missing(self):
        self.requests.get(
            self.url + '/log/logs/x', status_code=404,
            json=self._error('LogResourceNotFound', 'Log x not found'))

        with self.assertRaises(self.not_found) as raised:
            network_log.flow_log_get(self.request, 'x')

        self.assertTrue(network_log.is_not_found(raised.exception))
        self.assertEqual('Log x not found',
                         network_log.error_message(raised.exception))

    def test_flow_log_create(self):
        log = self._own(self.api_flow_logs.first())
        self.requests.post(self.url + '/log/logs', status_code=201,
                           json={'log': log})

        ret = network_log.flow_log_create(
            self.request, name=log['name'], description=log['description'],
            security_group_id=log['resource_id'], event='ALL')

        self.assertEqual(log['id'], ret.id)
        self.assertEqual(
            {'log': {'name': log['name'],
                     'description': log['description'],
                     'resource_type': 'security_group',
                     'resource_id': log['resource_id'],
                     'event': 'ALL',
                     'enabled': True,
                     'output_type': 'flow_sample'}},
            self.requests.last_request.json())

    def test_flow_log_create_rejected(self):
        self.requests.post(
            self.url + '/log/logs', status_code=400,
            json=self._error('FlowSampleSelectorNotSupported',
                             SELECTOR_ERROR))

        with self.assertRaises(self.bad_request) as raised:
            network_log.flow_log_create(
                self.request, name='', description='',
                security_group_id='sg', event='ALL')

        self.assertEqual(SELECTOR_ERROR,
                         network_log.error_message(raised.exception))
        self.assertFalse(network_log.is_not_found(raised.exception))
        self._assert_shown_as_an_error(raised.exception)

    def test_flow_log_create_forbidden(self):
        self.requests.post(
            self.url + '/log/logs', status_code=403,
            json=self._error('PolicyNotAuthorized',
                             'rule:create_log:output_type is disallowed '
                             'by policy'))

        with self.assertRaises(self.forbidden) as raised:
            network_log.flow_log_create(
                self.request, name='', description='',
                security_group_id='sg', event='ALL')

        self.assertEqual('rule:create_log:output_type is disallowed by '
                         'policy',
                         network_log.error_message(raised.exception))
        self._assert_shown_as_an_error(raised.exception)

    def test_flow_log_enable_rejected(self):
        # The server validates again on enable; the message must survive.
        log = self._own(self.api_flow_logs.first(), enabled=False)
        url = self.url + '/log/logs/' + log['id']
        message = ('Log output type flow_sample is not supported for '
                   'security_group by the loaded logging drivers.')
        self.requests.get(url, json={'log': log})
        self.requests.put(
            url, status_code=400,
            json=self._error('LogOutputTypeNotSupported', message))

        with self.assertRaises(self.bad_request) as raised:
            network_log.flow_log_set_enabled(self.request, log['id'], True)

        self.assertEqual(message,
                         network_log.error_message(raised.exception))

    def _two_pages(self, next_href):
        first, second = [self._own(log)
                         for log in self.api_flow_logs.list()]
        self.requests.get(
            self.url + '/log/logs',
            [{'json': {'logs': [first],
                       'logs_links': [{'rel': 'next', 'href': next_href}]}},
             {'json': {'logs': [second]}}])
        return first, second

    def test_flow_log_list_follows_pagination(self):
        marker = self.api_flow_logs.first()['id']
        first, second = self._two_pages(
            self.url + '/log/logs?output_type=flow_sample&project_id=%s'
            '&limit=1&marker=%s' % (self.project_id, marker))

        ret = network_log.flow_log_list(self.request)

        self.assertEqual([first['id'], second['id']],
                         [log.id for log in ret])
        self.assertEqual(2, self.requests.call_count)
        # The second page keeps the project and output filters.
        self.assertEqual({'output_type': ['flow_sample'],
                          'project_id': [self.project_id],
                          'limit': ['1'],
                          'marker': [marker]},
                         self.requests.last_request.qs)

    def test_flow_log_list_drops_other_projects(self):
        # A server that ignores the project filter must not leak logs.
        own = self._own(self.api_flow_logs.first())
        other = self._own(self.api_flow_logs.first(), id='other',
                          project_id='other')
        self.requests.get(self.url + '/log/logs',
                          json={'logs': [own, other]})

        ret = network_log.flow_log_list(self.request)

        self.assertEqual([own['id']], [log.id for log in ret])

    def _set_enabled(self, enabled):
        log = self._own(self.api_flow_logs.first(), enabled=not enabled)
        url = self.url + '/log/logs/' + log['id']
        self.requests.get(url, json={'log': log})
        self.requests.put(url, json={'log': dict(log, enabled=enabled)})

        ret = network_log.flow_log_set_enabled(self.request, log['id'],
                                               enabled)

        self.assertEqual(enabled, ret.enabled)
        self.assertEqual('PUT', self.requests.last_request.method)
        self.assertEqual({'log': {'enabled': enabled}},
                         self.requests.last_request.json())

    def test_flow_log_enable(self):
        self._set_enabled(True)

    def test_flow_log_disable(self):
        self._set_enabled(False)

    def test_flow_log_delete(self):
        log = self._own(self.api_flow_logs.first())
        url = self.url + '/log/logs/' + log['id']
        self.requests.get(url, json={'log': log})
        self.requests.delete(url, status_code=204)

        network_log.flow_log_delete(self.request, log['id'])

        self.assertEqual('DELETE', self.requests.last_request.method)

    def test_packet_log_is_never_changed(self):
        log = self._own(self.api_packet_logs.first())
        url = self.url + '/log/logs/' + log['id']
        self.requests.get(url, json={'log': log})

        self.assertRaises(horizon_exceptions.NotFound,
                          network_log.flow_log_delete, self.request,
                          log['id'])
        self.assertRaises(horizon_exceptions.NotFound,
                          network_log.flow_log_set_enabled, self.request,
                          log['id'], False)

        self.assertEqual(['GET', 'GET'],
                         [r.method for r in self.requests.request_history])

    def test_flow_sample_available(self):
        self.requests.get(
            self.url + '/log/loggable-resources',
            json={'loggable_resources': [
                {'type': 'security_group',
                 'output_types': ['flow_sample', 'packet_log']}]})

        self.assertTrue(network_log.flow_sample_available(self.request))

    def test_flow_sample_not_available(self):
        # Extension loaded, but no driver supports the output; and a
        # server without the extension returns no output_types at all.
        for resources in ([{'type': 'security_group',
                            'output_types': ['packet_log']}],
                          [{'type': 'security_group'}],
                          []):
            self.requests.get(self.url + '/log/loggable-resources',
                              json={'loggable_resources': resources})
            self.assertFalse(
                network_log.flow_sample_available(self.request))

    def _overlaps(self, logs, port_groups=None):
        self.requests.get(self.url + '/log/logs', json={'logs': logs})
        with helpers.mock.patch.object(api.neutron, 'port_get') as port_get:
            if port_groups is None:
                port_get.side_effect = self.exceptions.neutron
            else:
                port_get.return_value = helpers.mock.Mock(
                    security_groups=port_groups)
            ret = network_log.overlapping_packet_logs(self.request, 'sg-web')
        return [(log.id, log.overlap) for log in ret]

    def _packet_log(self, log_id, sg_id=None, target_id=None, event='ALL'):
        return self._own(self.api_packet_logs.first(), id=log_id,
                         resource_id=sg_id, target_id=target_id,
                         event=event)

    def test_overlapping_packet_logs(self):
        logs = [
            self._packet_log('same-sg', sg_id='sg-web'),
            self._packet_log('other-sg', sg_id='sg-db'),
            self._packet_log('every-sg-all'),
            self._packet_log('every-sg-accept', event='ACCEPT'),
            self._packet_log('common-drop', event='DROP'),
            self._own(self.api_flow_logs.first(), resource_id='sg-web'),
        ]

        ret = self._overlaps(logs)

        self.assertEqual([('same-sg', 'overlap'),
                          ('every-sg-all', 'overlap'),
                          ('every-sg-accept', 'overlap'),
                          ('common-drop', 'possible')], ret)
        self.assertEqual({'enabled': ['true'],
                          'project_id': [self.project_id]},
                         self.requests.last_request.qs)

    def test_overlapping_packet_log_of_a_port(self):
        logs = [self._packet_log('port-log', target_id='port-1')]

        self.assertEqual([('port-log', 'overlap')],
                         self._overlaps(logs, port_groups=['sg-web']))
        self.assertEqual([], self._overlaps(logs, port_groups=['sg-db']))
        # The port can not be read: say so instead of guessing.
        self.assertEqual([('port-log', 'possible')], self._overlaps(logs))

    def test_only_the_marker_of_a_next_link_is_used(self):
        # Host, path and other query values of the link are ignored.
        first, second = self._two_pages(
            'http://other.example.com/v2.0/other?project_id=x&marker=m1')

        ret = network_log.flow_log_list(self.request)

        self.assertEqual([first['id'], second['id']],
                         [log.id for log in ret])
        for request in self.requests.request_history:
            self.assertTrue(request.url.startswith(self.url + '/log/logs'))
        self.assertEqual({'output_type': ['flow_sample'],
                          'project_id': [self.project_id],
                          'marker': ['m1']},
                         self.requests.last_request.qs)

    def test_repeated_next_link_is_stopped(self):
        log = self._own(self.api_flow_logs.first())
        self.requests.get(
            self.url + '/log/logs',
            json={'logs': [log],
                  'logs_links': [{'rel': 'next',
                                  'href': self.url + '/log/logs?marker=m1'}]})

        self.assertRaises(network_log.PaginationError,
                          network_log.flow_log_list, self.request)
        self.assertEqual(2, self.requests.call_count)

    def test_next_link_without_marker_is_stopped(self):
        self._two_pages(self.url + '/log/logs')

        self.assertRaises(network_log.PaginationError,
                          network_log.flow_log_list, self.request)
        self.assertEqual(1, self.requests.call_count)

    def test_unknown_output_is_not_a_packet_log(self):
        logs = [self._own(self.api_packet_logs.first(), id='new-output',
                          resource_id='sg-web', output_type='something')]

        self.assertEqual([], self._overlaps(logs))

    def test_packet_log_of_another_project_is_not_seen(self):
        # A packet log of another project without a security group is
        # applied to every security group, but it is outside the project
        # scope of the panel. An empty result is "none found here".
        other = self._packet_log('other-project-all')
        other['project_id'] = 'other'

        self.assertEqual([], self._overlaps([other]))
        self.assertEqual([self.project_id],
                         self.requests.last_request.qs['project_id'])


class NeutronclientPathTests(_ClientPathTests, test.APITestCase):
    use_neutronclient = True
    not_found = neutron_exc.NotFound
    bad_request = neutron_exc.BadRequest
    forbidden = neutron_exc.Forbidden

    def setUp(self):
        if not hasattr(api.neutron, 'neutronclient'):
            self.skipTest("This Horizon release does not build "
                          "python-neutronclient.")
        super().setUp()

    def test_not_found_is_classified_by_horizon(self):
        self.requests.get(self.url + '/log/logs/x', status_code=404,
                          json=self._error('LogResourceNotFound', 'gone'))
        with self.assertRaises(neutron_exc.NotFound) as raised:
            network_log.flow_log_get(self.request, 'x')
        self.assertIsInstance(raised.exception,
                              dashboard_exceptions.NOT_FOUND)


class SdkPathTests(_ClientPathTests, test.APITestCase):
    use_neutronclient = False
    not_found = network_log.NetworkLogError
    bad_request = network_log.NetworkLogError
    forbidden = network_log.NetworkLogError

    def test_every_other_error_keeps_status_and_message(self):
        log = self._own(self.api_flow_logs.first())
        url = self.url + '/log/logs/' + log['id']
        self.requests.get(url, json={'log': log})
        for status, error_type, message in (
                (403, 'PolicyNotAuthorized', 'not allowed'),
                (404, 'LogResourceNotFound', 'gone'),
                (409, 'Conflict', 'in use'),
                (500, 'HTTPInternalServerError', 'server broke'),
                (503, 'HTTPServiceUnavailable', 'try later')):
            self.requests.delete(url, status_code=status,
                                 json=self._error(error_type, message))

            with self.assertRaises(network_log.NetworkLogError) as raised:
                network_log.flow_log_delete(self.request, log['id'])

            self.assertEqual(status, raised.exception.status_code)
            self.assertEqual(message, raised.exception.message)
            self.assertEqual(message,
                             network_log.error_message(raised.exception))
            self._assert_shown_as_an_error(raised.exception)

    def test_error_without_a_neutron_body_keeps_the_status(self):
        self.requests.get(self.url + '/log/logs', status_code=502,
                          text='Bad Gateway')

        with self.assertRaises(network_log.NetworkLogError) as raised:
            network_log.flow_log_list(self.request)

        self.assertEqual(502, raised.exception.status_code)
        self.assertIn('Bad Gateway', raised.exception.message)

    def test_unauthorized_is_left_to_horizon(self):
        self.requests.get(self.url + '/log/logs', status_code=401,
                          json=self._error('Unauthorized', 'token expired'))

        with self.assertRaises(sdk_exc.HttpException) as raised:
            network_log.flow_log_list(self.request)

        self.assertEqual(401, raised.exception.status_code)

    def test_sdk_has_no_network_log_resource(self):
        # The reason for the session calls. If this fails, openstacksdk
        # gained the resource and the SDK path can use it.
        proxy = api.neutron.networkclient(self.request)
        self.assertFalse(hasattr(proxy, 'create_network_log'))
        self.assertFalse(hasattr(proxy, 'network_logs'))


class NetworkLogHelperTests(test.APITestCase):

    @helpers.create_mocks({api.neutron: ('is_service_enabled',)})
    def test_is_supported(self):
        self.mock_is_service_enabled.return_value = True
        self.assertTrue(network_log.is_supported(self.request))
        self.mock_is_service_enabled.assert_called_once_with(
            self.request, config_name='enable_flow_log',
            ext_name='logging-output-type')

    @helpers.create_mocks({api.neutron: ('is_service_enabled',)})
    def test_is_supported_on_error(self):
        self.mock_is_service_enabled.side_effect = self.exceptions.neutron
        self.assertFalse(network_log.is_supported(self.request))

    @helpers.create_mocks({api.neutron: ('security_group_list',)})
    def test_security_group_choices(self):
        groups = self.security_groups.list()
        self.mock_security_group_list.return_value = groups

        choices = network_log.security_group_choices(self.request)

        self.assertEqual(sorted(sg.id for sg in groups),
                         sorted(c[0] for c in choices))
        first = groups[0]
        self.assertIn((first.id, '%s (%s)' % (first.name, first.id[:8])),
                      choices)

    @helpers.create_mocks({api.neutron: ('security_group_list',)})
    def test_annotate_security_groups(self):
        self.mock_security_group_list.side_effect = self.exceptions.neutron
        logs = self.flow_logs.list()

        network_log.annotate_security_groups(self.request, logs)

        # Without the names the id is shown; nothing is hidden.
        self.assertEqual([log.resource_id for log in logs],
                         [log.security_group_display for log in logs])

    def test_wrapper(self):
        log = network_log.NetworkLog({'event': 'DROP'})
        self.assertFalse(log.is_flow_log)
        self.assertEqual(network_log.OUTPUT_PACKET_LOG, log.output)
        self.assertEqual(network_log.EVENT_LABELS['DROP'],
                         log.event_display)

    def test_is_supported_without_any_client(self):
        with helpers.mock.patch.object(network_log, 'neutron',
                                       spec=['is_service_enabled']):
            self.assertFalse(network_log.is_supported(self.request))

    def test_is_not_found_for_horizon_not_found(self):
        self.assertTrue(network_log.is_not_found(
            horizon_exceptions.NotFound('x')))
        self.assertEqual('x', network_log.error_message(ValueError('x')))
