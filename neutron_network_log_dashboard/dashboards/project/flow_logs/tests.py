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

from django.urls import reverse
from django.utils import safestring
from horizon import exceptions as horizon_exceptions
from openstack_dashboard.test import helpers

from neutron_network_log_dashboard.api import network_log
from neutron_network_log_dashboard.test import helpers as test


INDEX_URL = reverse('horizon:project:flow_logs:index')
CREATE_URL = reverse('horizon:project:flow_logs:create')

LIST_MOCKS = ('flow_log_list', 'security_group_labels',
              'flow_sample_available')


class _ServerError(Exception):
    """An API error with the message attribute of python-neutronclient."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class FlowLogViewTests(test.TestCase):

    def _labels(self):
        return {sg.id: 'label of %s' % sg.id
                for sg in self.security_groups.list()}

    def _mock_list(self, available=True):
        self.mock_flow_log_list.return_value = self.flow_logs.list()
        self.mock_security_group_labels.return_value = self._labels()
        self.mock_flow_sample_available.return_value = available

    def _messages(self, res, level):
        return [m for m in res.context['messages'] if m.level_tag == level]

    def _overlap(self, name, overlap):
        log = network_log.NetworkLog({'id': name, 'name': name})
        log.overlap = overlap
        return log

    @helpers.create_mocks({network_log: LIST_MOCKS})
    def test_index(self):
        self._mock_list()

        res = self.client.get(INDEX_URL)

        self.assertTemplateUsed(res, 'project/flow_logs/index.html')
        rows = res.context['table'].data
        self.assertEqual(len(self.flow_logs.list()), len(rows))
        first = self.flow_logs.first()
        self.assertEqual('label of %s' % first.resource_id,
                         rows[0].security_group_display)
        self.assertContains(res, 'flow_logs__action_create')
        self.mock_flow_log_list.assert_called_once_with(
            helpers.IsHttpRequest())

    @helpers.create_mocks({network_log: LIST_MOCKS})
    def test_index_row_actions_follow_the_state(self):
        self._mock_list()
        enabled, disabled = self.flow_logs.list()

        res = self.client.get(INDEX_URL)

        self.assertContains(res, 'flow_logs__disable__%s' % enabled.id)
        self.assertNotContains(res, 'flow_logs__enable__%s' % enabled.id)
        self.assertContains(res, 'flow_logs__enable__%s' % disabled.id)
        self.assertNotContains(res, 'flow_logs__disable__%s' % disabled.id)

    @helpers.create_mocks({network_log: LIST_MOCKS})
    def test_index_api_error(self):
        self._mock_list()
        self.mock_flow_log_list.side_effect = self.exceptions.neutron

        res = self.client.get(INDEX_URL)

        self.assertTemplateUsed(res, 'project/flow_logs/index.html')
        self.assertEqual(0, len(res.context['table'].data))
        self.assertMessageCount(res, error=1)

    @helpers.create_mocks({network_log: LIST_MOCKS})
    def test_create_is_hidden_when_the_server_has_no_flow_sample(self):
        self._mock_list(available=False)

        res = self.client.get(INDEX_URL)

        self.assertNotContains(res, 'flow_logs__action_create')

    @helpers.create_mocks({network_log: LIST_MOCKS})
    def test_create_stays_when_the_support_can_not_be_read(self):
        self._mock_list()
        self.mock_flow_sample_available.side_effect = self.exceptions.neutron

        res = self.client.get(INDEX_URL)

        self.assertContains(res, 'flow_logs__action_create')

    @helpers.create_mocks({network_log: ('security_group_choices',)})
    def test_create_get(self):
        self.mock_security_group_choices.return_value = [
            (sg.id, sg.name) for sg in self.security_groups.list()]

        res = self.client.get(CREATE_URL)

        self.assertTemplateUsed(res, 'project/flow_logs/create.html')
        self.assertNoFormErrors(res)

    def _form_data(self, log, **changes):
        data = {'name': log.name,
                'description': log.description,
                'security_group_id': log.resource_id,
                'event': log.event,
                'enabled': 'on'}
        data.update(changes)
        return data

    @helpers.create_mocks({network_log: ('security_group_choices',
                                         'flow_log_create',
                                         'overlapping_packet_logs')})
    def test_create_post(self):
        log = self.flow_logs.first()
        self.mock_security_group_choices.return_value = [
            (log.resource_id, 'web')]
        self.mock_flow_log_create.return_value = log
        self.mock_overlapping_packet_logs.return_value = []

        res = self.client.post(CREATE_URL, self._form_data(log))

        self.assertNoFormErrors(res)
        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.mock_flow_log_create.assert_called_once_with(
            helpers.IsHttpRequest(),
            name=log.name, description=log.description,
            security_group_id=log.resource_id, event='ALL', enabled=True)
        self.mock_overlapping_packet_logs.assert_called_once_with(
            helpers.IsHttpRequest(), log.resource_id)
        # No overlap found is not announced: it would not mean "none".
        self.assertMessageCount(success=1, warning=0)

    @helpers.create_mocks({network_log: ('security_group_choices',
                                         'flow_log_create',
                                         'overlapping_packet_logs')})
    def test_create_post_warns_about_packet_logs(self):
        log = self.flow_logs.first()
        self.mock_security_group_choices.return_value = [
            (log.resource_id, 'web')]
        self.mock_flow_log_create.return_value = log
        self.mock_overlapping_packet_logs.return_value = [
            self._overlap('same', network_log.OVERLAP_CONFIRMED),
            self._overlap('maybe', network_log.OVERLAP_POSSIBLE)]

        res = self.client.post(CREATE_URL, self._form_data(log))

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.assertMessageCount(success=1, warning=2)

    @helpers.create_mocks({network_log: ('security_group_choices',
                                         'flow_log_create',
                                         'overlapping_packet_logs')})
    def test_create_post_says_when_packet_logs_can_not_be_read(self):
        log = self.flow_logs.first()
        self.mock_security_group_choices.return_value = [
            (log.resource_id, 'web')]
        self.mock_flow_log_create.return_value = log
        self.mock_overlapping_packet_logs.side_effect = \
            self.exceptions.neutron

        self.client.post(CREATE_URL, self._form_data(log))

        self.assertMessageCount(success=1, warning=1)

    @helpers.create_mocks({network_log: ('security_group_choices',
                                         'flow_log_create',
                                         'overlapping_packet_logs')})
    def test_create_post_disabled_does_not_check_packet_logs(self):
        log = self.flow_logs.list()[1]
        self.mock_security_group_choices.return_value = [
            (log.resource_id, 'db')]
        self.mock_flow_log_create.return_value = log
        data = self._form_data(log)
        del data['enabled']

        self.client.post(CREATE_URL, data)

        self.mock_flow_log_create.assert_called_once_with(
            helpers.IsHttpRequest(),
            name=log.name, description=log.description,
            security_group_id=log.resource_id, event='DROP', enabled=False)
        self.mock_overlapping_packet_logs.assert_not_called()

    @helpers.create_mocks({network_log: ('security_group_choices',
                                         'flow_log_create')})
    def test_create_post_unknown_security_group_rejected(self):
        log = self.flow_logs.first()
        self.mock_security_group_choices.return_value = [
            (log.resource_id, 'web')]

        res = self.client.post(
            CREATE_URL, self._form_data(log, security_group_id='other'))

        self.assertFormErrors(res, 1)
        self.mock_flow_log_create.assert_not_called()

    @helpers.create_mocks({network_log: LIST_MOCKS + (
        'security_group_choices', 'flow_log_create')})
    def test_create_post_api_error_shows_the_server_message_as_text(self):
        self._mock_list()
        log = self.flow_logs.first()
        self.mock_security_group_choices.return_value = [
            (log.resource_id, 'web')]
        self.mock_flow_log_create.side_effect = _ServerError(
            'not supported <b>now</b>')

        res = self.client.post(CREATE_URL, self._form_data(log),
                               follow=True)

        self.assertRedirects(res, INDEX_URL)
        errors = self._messages(res, 'error')
        self.assertEqual(1, len(errors))
        self.assertIn('not supported <b>now</b>', errors[0].message)
        self.assertNotIsInstance(errors[0].message, safestring.SafeData)
        self.assertContains(res, 'not supported &lt;b&gt;now&lt;/b&gt;')
        self.assertNotContains(res, '<b>now</b>')

    @helpers.create_mocks({network_log: ('flow_log_get',
                                         'security_group_labels',
                                         'overlapping_packet_logs')})
    def test_detail(self):
        log = self.flow_logs.first()
        self.mock_flow_log_get.return_value = log
        self.mock_security_group_labels.return_value = self._labels()
        self.mock_overlapping_packet_logs.return_value = [
            self._overlap('pkt <i>x</i>', network_log.OVERLAP_POSSIBLE)]

        res = self.client.get(
            reverse('horizon:project:flow_logs:detail', args=[log.id]))

        self.assertTemplateUsed(res, 'horizon/common/_detail.html')
        self.assertTemplateUsed(res,
                                'project/flow_logs/_detail_overview.html')
        self.assertEqual(log.id, res.context['flow_log'].id)
        self.assertContains(res, 'label of %s' % log.resource_id)
        self.assertContains(res, 'flow_sample')
        self.assertContains(res, 'pkt &lt;i&gt;x&lt;/i&gt;')
        self.assertContains(res, 'may be applied to the same security group')
        self.mock_flow_log_get.assert_called_once_with(
            helpers.IsHttpRequest(), log.id)

    @helpers.create_mocks({network_log: ('flow_log_get',
                                         'security_group_labels',
                                         'overlapping_packet_logs')})
    def test_detail_does_not_claim_there_is_no_packet_log(self):
        log = self.flow_logs.first()
        self.mock_flow_log_get.return_value = log
        self.mock_security_group_labels.return_value = self._labels()
        self.mock_overlapping_packet_logs.return_value = []
        url = reverse('horizon:project:flow_logs:detail', args=[log.id])

        res = self.client.get(url)

        self.assertContains(res, 'None found among the packet logs of this '
                                 'project')
        self.assertContains(res, 'other projects are not checked')

        self.mock_overlapping_packet_logs.side_effect = \
            self.exceptions.neutron
        res = self.client.get(url)

        self.assertContains(res, 'The packet logs could not be read.')
        self.assertNotContains(res, 'None found')

    @helpers.create_mocks({network_log: ('flow_log_get',)})
    def test_detail_of_a_packet_log_is_refused(self):
        self.mock_flow_log_get.side_effect = horizon_exceptions.NotFound('x')

        res = self.client.get(
            reverse('horizon:project:flow_logs:detail', args=['packet']))

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.assertMessageCount(error=1)

    def _post_action(self, action, *logs):
        if len(logs) == 1:
            data = {'action': 'flow_logs__%s__%s' % (action, logs[0].id)}
        else:
            data = {'action': 'flow_logs__%s' % action,
                    'object_ids': [log.id for log in logs]}
        return self.client.post(INDEX_URL, data)

    @helpers.create_mocks({network_log: LIST_MOCKS + ('flow_log_delete',)})
    def test_delete(self):
        self._mock_list()
        log = self.flow_logs.first()
        self.mock_flow_log_delete.return_value = None

        res = self._post_action('delete', log)

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.mock_flow_log_delete.assert_called_once_with(
            helpers.IsHttpRequest(), log.id)
        self.assertMessageCount(success=1)

    @helpers.create_mocks({network_log: LIST_MOCKS + ('flow_log_delete',)})
    def test_delete_reports_each_failure(self):
        self._mock_list()
        first, second = self.flow_logs.list()
        self.mock_flow_log_delete.side_effect = [
            None, _ServerError('in use <b>x</b>')]

        res = self.client.post(
            INDEX_URL,
            {'action': 'flow_logs__delete',
             'object_ids': [first.id, second.id]},
            follow=True)

        self.assertEqual(2, self.mock_flow_log_delete.call_count)
        errors = [m.message for m in self._messages(res, 'error')]
        # The reason of the failed item, then the summary of Horizon.
        self.assertEqual(2, len(errors))
        self.assertEqual('%s: in use <b>x</b>' % second.name_or_id,
                         errors[0])
        self.assertNotIsInstance(errors[0], safestring.SafeData)
        self.assertIn(second.name_or_id, str(errors[1]))
        self.assertNotIn(first.name_or_id, str(errors[1]))
        # The deleted one is reported, not as a full success.
        self.assertEqual(0, len(self._messages(res, 'success')))
        self.assertEqual(1, len(self._messages(res, 'info')))
        self.assertNotContains(res, '<b>x</b>')

    @helpers.create_mocks({network_log: LIST_MOCKS + (
        'flow_log_set_enabled', 'overlapping_packet_logs')})
    def test_enable(self):
        self._mock_list()
        log = self.flow_logs.list()[1]
        self.mock_overlapping_packet_logs.return_value = [
            self._overlap('same', network_log.OVERLAP_CONFIRMED)]

        res = self._post_action('enable', log)

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.mock_flow_log_set_enabled.assert_called_once_with(
            helpers.IsHttpRequest(), log.id, True)
        self.mock_overlapping_packet_logs.assert_called_once_with(
            helpers.IsHttpRequest(), log.resource_id)
        self.assertMessageCount(success=1, warning=1)

    @helpers.create_mocks({network_log: LIST_MOCKS + (
        'flow_log_set_enabled', 'overlapping_packet_logs')})
    def test_enable_rejected_by_the_server(self):
        self._mock_list()
        log = self.flow_logs.list()[1]
        self.mock_flow_log_set_enabled.side_effect = _ServerError(
            'Log output type flow_sample is not supported')

        res = self.client.post(
            INDEX_URL, {'action': 'flow_logs__enable__%s' % log.id},
            follow=True)

        errors = [str(m.message) for m in self._messages(res, 'error')]
        self.assertEqual(2, len(errors))
        self.assertIn('Log output type flow_sample is not supported',
                      errors[0])
        self.assertEqual(0, len(self._messages(res, 'success')))
        self.mock_overlapping_packet_logs.assert_not_called()

    @helpers.create_mocks({network_log: LIST_MOCKS + (
        'flow_log_set_enabled',)})
    def test_enable_of_an_enabled_log_is_not_sent(self):
        self._mock_list()
        log = self.flow_logs.first()

        self._post_action('enable', log)

        self.mock_flow_log_set_enabled.assert_not_called()
        self.assertMessageCount(error=1)

    @helpers.create_mocks({network_log: LIST_MOCKS + (
        'flow_log_set_enabled', 'overlapping_packet_logs')})
    def test_disable(self):
        self._mock_list()
        log = self.flow_logs.first()

        res = self._post_action('disable', log)

        self.assertRedirectsNoFollow(res, INDEX_URL)
        self.mock_flow_log_set_enabled.assert_called_once_with(
            helpers.IsHttpRequest(), log.id, False)
        self.mock_overlapping_packet_logs.assert_not_called()
        self.assertMessageCount(success=1)
