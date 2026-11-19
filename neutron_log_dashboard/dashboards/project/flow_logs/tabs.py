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

from django.utils.translation import gettext_lazy as _
from horizon import tabs


class OverviewTab(tabs.Tab):
    name = _("Overview")
    slug = "overview"
    template_name = "project/flow_logs/_detail_overview.html"

    def get_context_data(self, request):
        kwargs = self.tab_group.kwargs
        return {'flow_log': kwargs['flow_log'],
                'overlaps': kwargs['overlaps'],
                'overlaps_checked': kwargs['overlaps_checked']}


class FlowLogDetailTabs(tabs.TabGroup):
    slug = "flow_log_details"
    tabs = (OverviewTab,)
