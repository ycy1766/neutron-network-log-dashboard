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

from django.template import defaultfilters as filters
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from horizon import messages
from horizon import tables
from openstack_dashboard import policy

from neutron_log_dashboard.api import network_log

LOG = logging.getLogger(__name__)

# The server asks for this rule on create and on every enable request.
CREATE_RULES = (("network", "create_log"),
                ("network", "create_log:output_type"))
ENABLE_RULES = (("network", "update_log"),
                ("network", "create_log:output_type"))


class CreateFlowLog(tables.LinkAction):
    name = "create"
    verbose_name = _("Create Flow Log")
    url = "horizon:project:flow_logs:create"
    classes = ("ajax-modal",)
    icon = "plus"
    policy_rules = CREATE_RULES

    def allowed(self, request, datum=None):
        # Hidden only when the server says it can not create flow logs.
        # If that can not be read, the button stays and the server decides.
        try:
            return network_log.flow_sample_available(request)
        except Exception:
            LOG.exception("Unable to list the loggable resources.")
            return True


class _FlowLogAction(policy.PolicyTargetMixin):
    """Batch action that reports the reason of every failed item.

    BatchAction checks the policy again for every item when the action is
    posted, and shows one message with the names of the failed items. The
    reason of each failure is added here; the exception is raised again so
    that the item is never counted as done.
    """

    policy_target_attrs = (("project_id", "project_id"),)

    def _run(self, request, obj_id, call):
        try:
            call()
        except Exception as exc:
            datum = self.table.get_object_by_id(obj_id)
            # Plain text from the server; never marked safe.
            messages.error(request, '%s: %s' % (
                self.table.get_object_display(datum) or obj_id,
                network_log.error_message(exc)))
            raise


class DeleteFlowLog(_FlowLogAction, tables.DeleteAction):
    name = "delete"
    policy_rules = (("network", "delete_log"),)

    @staticmethod
    def action_present(count):
        return ngettext_lazy("Delete Flow Log", "Delete Flow Logs", count)

    @staticmethod
    def action_past(count):
        return ngettext_lazy("Deleted Flow Log", "Deleted Flow Logs", count)

    def delete(self, request, obj_id):
        self._run(request, obj_id,
                  lambda: network_log.flow_log_delete(request, obj_id))


class EnableFlowLog(_FlowLogAction, tables.BatchAction):
    name = "enable"
    policy_rules = ENABLE_RULES
    # The default of BatchAction says the action can not be undone.
    help_text = _("Enable this flow log.")

    @staticmethod
    def action_present(count):
        return ngettext_lazy("Enable Flow Log", "Enable Flow Logs", count)

    @staticmethod
    def action_past(count):
        return ngettext_lazy("Enabled Flow Log", "Enabled Flow Logs", count)

    def allowed(self, request, datum=None):
        return datum is None or not datum.enabled

    def action(self, request, obj_id):
        self._run(request, obj_id, lambda: network_log.flow_log_set_enabled(
            request, obj_id, True))
        datum = self.table.get_object_by_id(obj_id)
        report_overlaps(request, datum.resource_id)


class DisableFlowLog(_FlowLogAction, tables.BatchAction):
    name = "disable"
    policy_rules = (("network", "update_log"),)
    help_text = _("Disable this flow log.")

    @staticmethod
    def action_present(count):
        return ngettext_lazy("Disable Flow Log", "Disable Flow Logs", count)

    @staticmethod
    def action_past(count):
        return ngettext_lazy("Disabled Flow Log", "Disabled Flow Logs",
                             count)

    def allowed(self, request, datum=None):
        return datum is None or datum.enabled

    def action(self, request, obj_id):
        self._run(request, obj_id, lambda: network_log.flow_log_set_enabled(
            request, obj_id, False))


OVERLAP_LABELS = {
    network_log.OVERLAP_CONFIRMED: _("applied to the same security group"),
    network_log.OVERLAP_POSSIBLE: _("may be applied to the same security "
                                    "group; check it"),
}


def packet_log_overlaps(request, security_group_id):
    """(overlaps, checked); checked is False when the lookup failed.

    Each overlap gets overlap_display.
    """
    try:
        overlaps = network_log.overlapping_packet_logs(request,
                                                       security_group_id)
    except Exception:
        LOG.exception("Unable to list the packet logs.")
        return [], False
    for log in overlaps:
        log.overlap_display = OVERLAP_LABELS[log.overlap]
    return overlaps, True


def report_overlaps(request, security_group_id):
    """Warn about enabled packet logs on the security group of a flow log.

    Nothing is said when none is found: only the packet logs of this
    project can be read, so that would not mean there is none.
    """
    overlaps, checked = packet_log_overlaps(request, security_group_id)
    if not checked:
        messages.warning(request, _(
            "The packet logs could not be read. Check that no packet log "
            "is enabled on the same security group."))
    for log in overlaps:
        messages.warning(request, _(
            "Enabled packet log %(name)s: %(overlap)s. A packet log and a "
            "flow log enabled on one security group are not supported "
            "together; the server does not reject it.") % {
                'name': log.name_or_id, 'overlap': log.overlap_display})


def _security_group_url(log):
    if not log.resource_id:
        return None
    return reverse('horizon:project:security_groups:detail',
                   args=[log.resource_id])


class FlowLogsTable(tables.DataTable):
    name = tables.WrappingColumn(
        "name_or_id",
        verbose_name=_("Name"),
        link="horizon:project:flow_logs:detail")
    security_group = tables.Column(
        "security_group_display",
        verbose_name=_("Security Group"),
        link=_security_group_url)
    event = tables.Column(
        "event_display",
        verbose_name=_("Event"))
    enabled = tables.Column(
        "enabled",
        verbose_name=_("Enabled"),
        filters=(filters.yesno, filters.capfirst))
    description = tables.WrappingColumn(
        "description",
        verbose_name=_("Description"))

    def get_object_display(self, datum):
        return datum.name_or_id

    class Meta(object):
        name = "flow_logs"
        verbose_name = _("Flow Logs")
        table_actions = (CreateFlowLog, EnableFlowLog, DisableFlowLog,
                         DeleteFlowLog)
        row_actions = (EnableFlowLog, DisableFlowLog, DeleteFlowLog)
