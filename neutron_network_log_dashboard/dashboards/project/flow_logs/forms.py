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

import logging

from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from horizon import exceptions
from horizon import forms
from horizon import messages

from neutron_network_log_dashboard.api import network_log
from neutron_network_log_dashboard.dashboards.project.flow_logs import tables

LOG = logging.getLogger(__name__)


class CreateFlowLog(forms.SelfHandlingForm):
    name = forms.CharField(max_length=255, label=_("Name"), required=False)
    description = forms.CharField(
        max_length=255, label=_("Description"), required=False,
        widget=forms.Textarea(attrs={'rows': 2}))
    security_group_id = forms.ThemableChoiceField(
        label=_("Security Group"),
        help_text=_("The security group whose traffic is sampled."))
    event = forms.ThemableChoiceField(
        label=_("Event"),
        choices=network_log.EVENT_CHOICES,
        initial=network_log.EVENT_ALL)
    enabled = forms.BooleanField(
        label=_("Enabled"), required=False, initial=True)

    failure_url = 'horizon:project:flow_logs:index'

    def __init__(self, request, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        try:
            choices = network_log.security_group_choices(request)
        except Exception:
            choices = []
            exceptions.handle(request,
                              _('Unable to retrieve security groups.'))
        if not choices:
            choices = [('', _("No security groups available"))]
        self.fields['security_group_id'].choices = choices

    def handle(self, request, data):
        try:
            log = network_log.flow_log_create(
                request,
                name=data['name'],
                description=data['description'],
                security_group_id=data['security_group_id'],
                event=data['event'],
                enabled=data['enabled'])
        except Exception as exc:
            LOG.info('Failed to create flow log: %s', exc)
            # The server message is plain text; it is never marked safe.
            msg = _('Unable to create flow log: %s') % (
                network_log.error_message(exc))
            exceptions.handle(request, msg,
                              redirect=reverse(self.failure_url))
        messages.success(
            request,
            _('Flow log %s was created. This does not confirm that flow '
              'records are being collected.') % log.name_or_id)
        if log.enabled:
            tables.report_overlaps(request, log.resource_id)
        return log
