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

"""Policy checks of the panel with the real openstack_auth engine.

The Horizon test settings disable the policy check (``POLICY_CHECK_FUNCTION
= None``), so the view tests run without it. These tests turn it on and
load the example rules of ``neutron_log_dashboard/conf/neutron_policy.d``.
The Neutron API is mocked: what is proved is what Horizon shows and that a
refused request never reaches a changing API call. The server policy is
not exercised.
"""

import os
import shutil
import tempfile

from django.test.utils import override_settings
from django.urls import reverse
from openstack_auth import policy as policy_backend
from openstack_dashboard import policy
from openstack_dashboard.test import helpers

import neutron_log_dashboard
from neutron_log_dashboard.api import network_log
from neutron_log_dashboard.dashboards.project.flow_logs import panel
from neutron_log_dashboard.test import helpers as test

INDEX_URL = reverse('horizon:project:flow_logs:index')
CREATE_URL = reverse('horizon:project:flow_logs:create')

POLICY_DIR = os.path.join(os.path.dirname(neutron_log_dashboard.__file__),
                          'conf', 'neutron_policy.d')
POLICY_FILES = {'identity': 'keystone_policy.yaml',
                'compute': 'nova_policy.yaml',
                'network': 'neutron_policy.yaml'}
RULES = ('get_loggable_resource', 'create_log', 'create_log:output_type',
         'get_log', 'update_log', 'delete_log')

NOTHING = dict.fromkeys(RULES, False)
EVERYTHING = dict.fromkeys(RULES, True)
MANAGER = dict(EVERYTHING, **{'create_log:output_type': False})

# The rules of neutron-taas-dashboard, to prove they survive next to ours.
TAAS_RULES = """
"create_tap_mirror": "role:member and project_id:%(project_id)s"
"get_tap_mirror": "role:reader and project_id:%(project_id)s"
"""

MUTATIONS = ('flow_log_create', 'flow_log_set_enabled', 'flow_log_delete')
LIST_MOCKS = ('flow_log_list', 'security_group_labels',
              'flow_sample_available', 'security_group_choices',
              'overlapping_packet_logs')


class _PolicyTestCase(test.TestCase):

    def setUp(self):
        super().setUp()
        policy_backend.reset()
        self.addCleanup(policy_backend.reset)

    def _login(self, roles):
        self.setActiveUser(id=self.user.id, token=self.token,
                           username=self.user.name,
                           tenant_id=self.tenant.id,
                           service_catalog=self.service_catalog,
                           roles=[{'name': r} for r in roles])

    def _check(self, roles, target_project=None, rules=RULES):
        self._login(roles)
        target = {'project_id': target_project or self.tenant.id}
        return {rule: policy.check((('network', rule),), self.request,
                                   target=target)
                for rule in rules}


@override_settings(POLICY_CHECK_FUNCTION='openstack_auth.policy.check',
                   POLICY_FILES=POLICY_FILES,
                   POLICY_DIRS={'network': [POLICY_DIR]})
class RuleTests(_PolicyTestCase):
    """What the example rules allow for each role."""

    def test_rules_are_loaded(self):
        enforcer = policy_backend._get_enforcer()
        for rule in RULES:
            self.assertIn(rule, enforcer['network'].rules)

    def test_no_roles(self):
        self.assertEqual(NOTHING, self._check([]))

    def test_reader(self):
        self.assertEqual(NOTHING, self._check(['reader']))

    def test_member(self):
        self.assertEqual(NOTHING, self._check(['member', 'reader']))

    def test_manager_own_project(self):
        self.assertEqual(MANAGER,
                         self._check(['manager', 'member', 'reader']))

    def test_manager_other_project(self):
        self.assertEqual(NOTHING,
                         self._check(['manager', 'member', 'reader'],
                                     target_project='other'))

    def test_admin(self):
        self.assertEqual(EVERYTHING, self._check(['admin']))
        self.assertEqual(EVERYTHING,
                         self._check(['admin'], target_project='other'))

    def test_panel_access_follows_get_log(self):
        flow_logs = panel.FlowLogs()
        for roles, expected in (([], False),
                                (['member', 'reader'], False),
                                (['manager', 'member'], True),
                                (['admin'], True)):
            self._login(roles)
            self.assertEqual(expected, flow_logs._can_access(self.request),
                             roles)


@override_settings(POLICY_CHECK_FUNCTION='openstack_auth.policy.check',
                   POLICY_FILES=POLICY_FILES)
class PolicyMergeTests(_PolicyTestCase):
    """How the example rules combine with the other policy sources."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def _files_path(self):
        # openstack_auth reads POLICY_FILES_PATH once, when it is imported.
        return helpers.mock.patch.object(policy_backend, '_BASE_PATH',
                                         self.tmp)

    def _write(self, *path, content):
        name = os.path.join(self.tmp, *path)
        os.makedirs(os.path.dirname(name), exist_ok=True)
        with open(name, 'w') as f:
            f.write(content)
        return name

    @override_settings(POLICY_DIRS={})
    def test_without_the_example_rules(self):
        """Why a deployment has to wire the rules.

        The log rules of Horizon are admin only, so a manager gets no
        panel. ``create_log:output_type`` is unknown to Horizon and falls
        back to its default rule, which a member of the project passes.
        """
        policy_backend.reset()
        manager = self._check(['manager', 'member', 'reader'])
        self.assertEqual(
            dict(NOTHING, **{'create_log:output_type': True}), manager)
        self.assertEqual(
            dict(NOTHING, **{'create_log:output_type': True}),
            self._check(['member', 'reader']))

    def test_taas_rules_are_kept(self):
        taas_dir = os.path.dirname(
            self._write('taas.d', 'taas.yaml', content=TAAS_RULES))
        taas_rules = ('create_tap_mirror', 'get_tap_mirror')

        with override_settings(POLICY_DIRS={'network': [taas_dir]}):
            policy_backend.reset()
            before = self._check(['member', 'reader'], rules=taas_rules)
        with override_settings(
                POLICY_DIRS={'network': [taas_dir, POLICY_DIR]}):
            policy_backend.reset()
            after = self._check(['member', 'reader'], rules=taas_rules)
            logs = self._check(['manager', 'member', 'reader'])

        self.assertEqual({'create_tap_mirror': True, 'get_tap_mirror': True},
                         before)
        self.assertEqual(before, after)
        self.assertEqual(MANAGER, logs)

    def test_a_policy_dir_overrides_the_policy_file(self):
        # The default file says admin only, the policy file of the
        # deployment "nobody", the directory "manager": the directory is
        # read last and wins.
        self._write('neutron_policy.yaml', content='"get_log": "!"\n')
        with self._files_path(), override_settings(
                POLICY_DIRS={'network': [POLICY_DIR]}):
            policy_backend.reset()
            self.assertTrue(
                self._check(['manager'], rules=('get_log',))['get_log'])
        with self._files_path(), override_settings(POLICY_DIRS={}):
            policy_backend.reset()
            self.assertFalse(
                self._check(['admin'], rules=('get_log',))['get_log'])

    def test_a_relative_policy_dir_is_joined_to_the_files_path(self):
        self._write('log.d', 'log.yaml',
                    content='"get_log": "role:manager"\n')
        with self._files_path(), override_settings(
                POLICY_DIRS={'network': ['log.d']}):
            policy_backend.reset()
            self.assertTrue(
                self._check(['manager'], rules=('get_log',))['get_log'])


@override_settings(POLICY_CHECK_FUNCTION='openstack_auth.policy.check',
                   POLICY_FILES=POLICY_FILES,
                   POLICY_DIRS={'network': [POLICY_DIR]})
class RequestTests(_PolicyTestCase):
    """A refused request must not reach a changing API call."""

    MEMBER = ['member', 'reader']
    PROJECT_MANAGER = ['manager', 'member', 'reader']
    ADMIN = ['admin', 'member', 'reader']

    def _logs(self):
        # The test user works in self.tenant; make the logs its own.
        return [network_log.NetworkLog(
            dict(log, project_id=self.tenant.id, tenant_id=self.tenant.id))
            for log in self.api_flow_logs.list()]

    def _mock(self, logs=None):
        logs = self._logs() if logs is None else logs
        self.mock_flow_log_list.return_value = logs
        self.mock_security_group_labels.return_value = {}
        self.mock_flow_sample_available.return_value = True
        self.mock_security_group_choices.return_value = [
            (log.resource_id, 'sg') for log in logs]
        self.mock_overlapping_packet_logs.return_value = []
        self.mock_flow_log_create.return_value = logs[0] if logs else None
        return logs

    def _form_data(self, log):
        return {'name': 'x', 'description': '',
                'security_group_id': log.resource_id, 'event': 'ALL',
                'enabled': 'on'}

    def _post_action(self, action, *log_ids):
        if len(log_ids) == 1:
            data = {'action': 'flow_logs__%s__%s' % (action, log_ids[0])}
        else:
            data = {'action': 'flow_logs__%s' % action,
                    'object_ids': list(log_ids)}
        return self.client.post(INDEX_URL, data)

    def _assert_no_mutation(self):
        for name in MUTATIONS:
            getattr(self, 'mock_' + name).assert_not_called()

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_member_can_change_nothing(self):
        enabled, disabled = self._mock()
        self._login(self.MEMBER)

        res = self.client.get(CREATE_URL)
        self.assertRedirectsNoFollow(res, INDEX_URL)
        res = self.client.post(CREATE_URL, self._form_data(enabled))
        self.assertRedirectsNoFollow(res, INDEX_URL)
        self._post_action('enable', disabled.id)
        self._post_action('disable', enabled.id)
        self._post_action('delete', enabled.id)
        self._post_action('delete', enabled.id, disabled.id)

        self._assert_no_mutation()
        self.mock_security_group_choices.assert_not_called()

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_member_sees_no_buttons(self):
        self._mock()
        self._login(self.MEMBER)

        res = self.client.get(INDEX_URL)

        for action in ('action_create', 'enable', 'disable', 'delete'):
            self.assertNotContains(res, 'flow_logs__%s' % action)

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_manager_buttons(self):
        enabled, disabled = self._mock()
        self._login(self.PROJECT_MANAGER)

        res = self.client.get(INDEX_URL)

        self.assertEqual(2, len(res.context['table'].data))
        self.assertContains(res, 'flow_logs__disable__%s' % enabled.id)
        self.assertContains(res, 'flow_logs__delete__%s' % enabled.id)
        self.assertContains(res, 'flow_logs__delete__%s' % disabled.id)
        self.assertNotContains(res, 'flow_logs__action_create')
        self.assertNotContains(res, 'flow_logs__enable')

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_manager_can_not_create_or_enable(self):
        enabled, disabled = self._mock()
        self._login(self.PROJECT_MANAGER)

        res = self.client.get(CREATE_URL)
        self.assertRedirectsNoFollow(res, INDEX_URL)
        res = self.client.post(CREATE_URL, self._form_data(enabled))
        self.assertRedirectsNoFollow(res, INDEX_URL)
        self._post_action('enable', disabled.id)

        self._assert_no_mutation()

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_manager_can_disable_and_delete(self):
        enabled, disabled = self._mock()
        self._login(self.PROJECT_MANAGER)

        self._post_action('disable', enabled.id)
        self._post_action('delete', disabled.id)

        self.mock_flow_log_set_enabled.assert_called_once_with(
            helpers.IsHttpRequest(), enabled.id, False)
        self.mock_flow_log_delete.assert_called_once_with(
            helpers.IsHttpRequest(), disabled.id)
        self.mock_flow_log_create.assert_not_called()

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_admin_can_create_and_enable(self):
        enabled, disabled = self._mock()
        self._login(self.ADMIN)

        res = self.client.post(CREATE_URL, self._form_data(enabled))
        self.assertNoFormErrors(res)
        self._post_action('enable', disabled.id)

        self.mock_flow_log_create.assert_called_once()
        self.mock_flow_log_set_enabled.assert_called_once_with(
            helpers.IsHttpRequest(), disabled.id, True)

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_ids_outside_the_table_are_not_acted_on(self):
        # The id of a packet log or of a log of another project is not in
        # the list of the panel, whatever the role.
        self._mock()
        self._login(self.ADMIN)

        for action in ('enable', 'disable', 'delete'):
            self._post_action(action, 'id-of-a-packet-log')
            self._post_action(action, 'id-of-a-packet-log', 'other-project')

        self._assert_no_mutation()

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_batch_is_decided_item_by_item(self):
        # If a log of another project got into the table, the policy
        # still refuses it for a manager while the own log is deleted.
        own, other = self._logs()
        other = network_log.NetworkLog(
            dict(other._apidict, project_id='other'))
        self._mock([own, other])
        self._login(self.PROJECT_MANAGER)

        self._post_action('delete', own.id, other.id)

        self.mock_flow_log_delete.assert_called_once_with(
            helpers.IsHttpRequest(), own.id)
        self.assertMessageCount(error=1)

    @helpers.create_mocks({network_log: LIST_MOCKS + MUTATIONS})
    def test_batch_enable_skips_enabled_logs(self):
        enabled, disabled = self._mock()
        self._login(self.ADMIN)

        self._post_action('enable', enabled.id, disabled.id)

        self.mock_flow_log_set_enabled.assert_called_once_with(
            helpers.IsHttpRequest(), disabled.id, True)
