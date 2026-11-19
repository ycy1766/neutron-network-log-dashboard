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

from openstack_dashboard.test.test_data import utils

from neutron_log_dashboard.api import network_log


def data(TEST):
    # Wrapped objects as returned by neutron_log_dashboard.api.network_log.
    TEST.flow_logs = utils.TestDataContainer()
    # Raw dicts as returned by neutronclient.
    TEST.api_flow_logs = utils.TestDataContainer()
    TEST.api_packet_logs = utils.TestDataContainer()

    security_groups = TEST.security_groups.list()
    web_sg = security_groups[0]
    db_sg = security_groups[1]

    def log_dict(log_id, name, description, sg_id, event, enabled,
                 output_type, target_id=None):
        return {
            'id': log_id,
            'tenant_id': '1',
            'project_id': '1',
            'name': name,
            'description': description,
            'resource_type': 'security_group',
            'resource_id': sg_id,
            'target_id': target_id,
            'event': event,
            'enabled': enabled,
            'output_type': output_type,
        }

    for log in (
            log_dict('7c1d2b90-41f0-4a57-8e5f-0d7f5a2c0001', 'web-sg-flows',
                     'flow log for web', web_sg.id, 'ALL', True,
                     network_log.OUTPUT_FLOW_SAMPLE),
            log_dict('7c1d2b90-41f0-4a57-8e5f-0d7f5a2c0002', '', '',
                     db_sg.id, 'DROP', False,
                     network_log.OUTPUT_FLOW_SAMPLE)):
        TEST.api_flow_logs.add(log)
        TEST.flow_logs.add(network_log.NetworkLog(log))

    for log in (
            log_dict('7c1d2b90-41f0-4a57-8e5f-0d7f5a2c0011', 'web-packets',
                     '', web_sg.id, 'ALL', True,
                     network_log.OUTPUT_PACKET_LOG),
            log_dict('7c1d2b90-41f0-4a57-8e5f-0d7f5a2c0012', 'all-sg-drops',
                     '', None, 'DROP', True,
                     network_log.OUTPUT_PACKET_LOG),
            log_dict('7c1d2b90-41f0-4a57-8e5f-0d7f5a2c0013', 'db-packets',
                     '', db_sg.id, 'ALL', True,
                     network_log.OUTPUT_PACKET_LOG)):
        TEST.api_packet_logs.add(log)
