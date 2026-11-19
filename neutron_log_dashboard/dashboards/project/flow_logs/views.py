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

from django import shortcuts
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from horizon import exceptions
from horizon import forms as horizon_forms
from horizon import messages
from horizon import tables as horizon_tables
from horizon import tabs as horizon_tabs
from horizon.utils import memoized
from openstack_dashboard import policy

from neutron_log_dashboard.api import network_log
from neutron_log_dashboard.dashboards.project.flow_logs import forms
from neutron_log_dashboard.dashboards.project.flow_logs import tables
from neutron_log_dashboard.dashboards.project.flow_logs import tabs


class IndexView(horizon_tables.DataTableView):
    table_class = tables.FlowLogsTable
    template_name = 'project/flow_logs/index.html'
    page_title = _("Flow Logs")

    def get_data(self):
        try:
            logs = network_log.flow_log_list(self.request)
        except Exception:
            logs = []
            exceptions.handle(self.request,
                              _('Unable to retrieve flow logs.'))
        return network_log.annotate_security_groups(self.request, logs)


class CreateView(horizon_forms.ModalFormView):
    form_class = forms.CreateFlowLog
    form_id = "create_flow_log_form"
    template_name = 'project/flow_logs/create.html'
    submit_label = _("Create Flow Log")
    submit_url = reverse_lazy("horizon:project:flow_logs:create")
    success_url = reverse_lazy("horizon:project:flow_logs:index")
    page_title = _("Create Flow Log")
    policy_rules = tables.CREATE_RULES

    def dispatch(self, request, *args, **kwargs):
        # The table only hides the button; check the same rules here so a
        # direct GET/POST of this URL is refused with a message as well.
        # The Neutron policy on the server remains the authority.
        target = {'project_id': request.user.project_id}
        if not policy.check(self.policy_rules, request, target):
            messages.error(request,
                           _('You are not allowed to create flow logs.'))
            return shortcuts.redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)


class DetailView(horizon_tabs.TabView):
    tab_group_class = tabs.FlowLogDetailTabs
    template_name = 'horizon/common/_detail.html'
    page_title = "{{ flow_log.name_or_id }}"

    @memoized.memoized_method
    def get_data(self):
        try:
            log = network_log.flow_log_get(self.request,
                                           self.kwargs['flow_log_id'])
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve flow log details.'),
                              redirect=self.get_redirect_url())
        network_log.annotate_security_groups(self.request, [log])
        return log

    @memoized.memoized_method
    def get_overlaps(self):
        return tables.packet_log_overlaps(self.request,
                                          self.get_data().resource_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = self.get_data()
        table = tables.FlowLogsTable(self.request)
        context["flow_log"] = log
        context["url"] = self.get_redirect_url()
        context["actions"] = table.render_row_actions(log)
        return context

    def get_tabs(self, request, *args, **kwargs):
        overlaps, checked = self.get_overlaps()
        return self.tab_group_class(request, flow_log=self.get_data(),
                                    overlaps=overlaps,
                                    overlaps_checked=checked, **kwargs)

    @staticmethod
    def get_redirect_url():
        return reverse('horizon:project:flow_logs:index')
