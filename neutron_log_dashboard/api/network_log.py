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

"""All Neutron (network log) calls of the plugin.

This is the only module that talks to Neutron. A flow log is a Neutron
network log (``/v2.0/log/logs``) whose ``output_type`` is ``flow_sample``;
there is no separate resource. Everything here is limited to the flow logs
of the current project. Packet logs are only read, to point out a packet
log that is applied to the security group of a flow log.

Horizon up to 2025.1 builds a ``python-neutronclient`` client
(``api.neutron.neutronclient``), which has dedicated network log methods.
Later releases only have the openstacksdk based ``api.neutron.networkclient``.
openstacksdk has no network log resource, so that path sends the requests
through the proxy session. Both paths return the same wrappers and page
through lists the same way. Their
exceptions differ by class; use ``error_message`` and ``is_not_found`` to
read them.
"""

import logging
from urllib import parse

from django.utils.translation import gettext_lazy as _
from horizon import exceptions
from openstack import exceptions as sdk_exceptions
from openstack_dashboard.api import neutron

LOG = logging.getLogger(__name__)

# Neutron extension that adds ``output_type`` to the log resource.
EXTENSION_ALIAS = 'logging-output-type'
# ``OPENSTACK_NEUTRON_NETWORK`` key that can hide the panel.
CONFIG_NAME = 'enable_flow_log'

OUTPUT_PACKET_LOG = 'packet_log'
OUTPUT_FLOW_SAMPLE = 'flow_sample'

LOGS_PATH = '/log/logs'
LOG_PATH = LOGS_PATH + '/%s'
LOGGABLE_RESOURCES_PATH = '/log/loggable-resources'

# The server accepts a flow_sample log only for one security group.
RESOURCE_SECURITY_GROUP = 'security_group'

EVENT_ALL = 'ALL'
EVENT_ACCEPT = 'ACCEPT'
EVENT_DROP = 'DROP'

EVENT_CHOICES = (
    (EVENT_ALL, _("All (accepted and dropped traffic)")),
    (EVENT_ACCEPT, _("Accept (accepted traffic only)")),
    (EVENT_DROP, _("Drop (dropped traffic only)")),
)
EVENT_LABELS = dict(EVENT_CHOICES)

# Whether an enabled packet log is applied to the security group of a flow
# log. This is about where the logs are applied, not a tested interference.
OVERLAP_CONFIRMED = 'overlap'
OVERLAP_POSSIBLE = 'possible'


class NetworkLog(neutron.NeutronAPIDictWrapper):
    """Wrapper for a ``log`` resource."""

    @property
    def output(self):
        # A server without the extension does not return the attribute;
        # such a log is a packet log.
        return self._apidict.get('output_type') or OUTPUT_PACKET_LOG

    @property
    def is_flow_log(self):
        return self.output == OUTPUT_FLOW_SAMPLE

    @property
    def event_display(self):
        event = self._apidict.get('event')
        return EVENT_LABELS.get(event, event or '-')


def is_supported(request):
    """True when the panel can be shown for this request.

    This only checks the extension advertisement and the dashboard setting.
    It says nothing about what the user is allowed to do: that is decided
    by the Neutron policy when a call is made.
    """
    if not (_use_neutronclient() or hasattr(neutron, 'networkclient')):
        LOG.error("This Horizon release has no Neutron client the Flow "
                  "Logs panel can use; it will not be displayed.")
        return False
    try:
        return neutron.is_service_enabled(request,
                                          config_name=CONFIG_NAME,
                                          ext_name=EXTENSION_ALIAS)
    except Exception:
        LOG.exception("Unable to list Neutron extensions; the Flow Logs "
                      "panel will not be displayed.")
        return False


def _use_neutronclient():
    """True on Horizon releases that still build python-neutronclient."""
    return hasattr(neutron, 'neutronclient')


def _sdk_request(request, method, path, **kwargs):
    proxy = neutron.networkclient(request)
    response = getattr(proxy, method)(path, **kwargs)
    sdk_exceptions.raise_from_response(response)
    return response


class PaginationError(Exception):
    """The server sent a next link that can not be followed safely."""


def _next_page(body, key, seen):
    """The ``marker`` / ``limit`` of the next link, or None on the last page.

    Only these two values are taken from the link. The request is sent
    again to the same path with the original filters, so a link can not
    drop a filter or change the request in another way.
    """
    for link in body.get(key + '_links') or []:
        if link.get('rel') != 'next':
            continue
        query = parse.parse_qs(parse.urlsplit(link.get('href') or '').query)
        marker = (query.get('marker') or [None])[0]
        if not marker or marker in seen:
            raise PaginationError(
                "Neutron returned a next link without a new marker.")
        seen.add(marker)
        page = {'marker': marker}
        if query.get('limit'):
            page['limit'] = query['limit'][0]
        return page
    return None


def _get(request, path, **params):
    """GET one page of a collection and return the decoded body."""
    if _use_neutronclient():
        return neutron.neutronclient(request).get(path, params=params)
    return _sdk_request(request, 'get', path, params=params).json()


def _list(request, path, key, **params):
    # Neither client is left to follow the pagination links: the proxy
    # session does not do it, and python-neutronclient replaces the query
    # with the one of the link and never stops on a repeated marker.
    items = []
    seen = set()
    page = {}
    while page is not None:
        body = _get(request, path, **dict(params, **page))
        items.extend(body.get(key, []))
        page = _next_page(body, key, seen)
    return items


def _logs(request, **params):
    return _list(request, LOGS_PATH, 'logs', **params)


def _loggable_resources(request):
    return _list(request, LOGGABLE_RESOURCES_PATH, 'loggable_resources')


def _log_show(request, log_id):
    if _use_neutronclient():
        return neutron.neutronclient(request).show_network_log(log_id)['log']
    return _sdk_request(request, 'get', LOG_PATH % log_id).json()['log']


def _log_create(request, body):
    if _use_neutronclient():
        return neutron.neutronclient(request).create_network_log(body)['log']
    return _sdk_request(request, 'post', LOGS_PATH, json=body).json()['log']


def _log_update(request, log_id, body):
    if _use_neutronclient():
        return neutron.neutronclient(request).update_network_log(
            log_id, body)['log']
    return _sdk_request(request, 'put', LOG_PATH % log_id,
                        json=body).json()['log']


def _log_delete(request, log_id):
    if _use_neutronclient():
        neutron.neutronclient(request).delete_network_log(log_id)
        return
    _sdk_request(request, 'delete', LOG_PATH % log_id)


def error_message(exc):
    """The message the server sent with an error, or ``str(exc)``.

    python-neutronclient keeps it in ``message``, openstacksdk in
    ``details``. The text comes from the server: show it as plain text and
    never mark it safe for HTML.
    """
    if isinstance(exc, sdk_exceptions.HttpException):
        # ``details`` is the raw body when openstacksdk could not read it.
        try:
            return exc.response.json()['NeutronError']['message']
        except Exception:
            return exc.details or str(exc)
    return getattr(exc, 'message', None) or str(exc)


def is_not_found(exc):
    """True for a 404 of either client and for ``horizon`` NotFound."""
    if isinstance(exc, exceptions.NotFound):
        return True
    return getattr(exc, 'status_code', None) == 404


def _project_id(request):
    return request.user.project_id


def _log_list(request, **params):
    project_id = _project_id(request)
    params['project_id'] = project_id
    logs = [NetworkLog(log) for log in _logs(request, **params)]
    # The server filters; this also holds if a server ignores the filter.
    return [log for log in logs if log.project_id == project_id]


def flow_sample_available(request):
    """True when the server can create a flow log for a security group.

    The extension can be loaded while no logging driver supports the
    output, for example when sampling is not configured.
    """
    for resource in _loggable_resources(request):
        if (resource.get('type') == RESOURCE_SECURITY_GROUP and
                OUTPUT_FLOW_SAMPLE in (resource.get('output_types') or [])):
            return True
    return False


def flow_log_list(request, **params):
    """The flow logs of the current project."""
    logs = _log_list(request, output_type=OUTPUT_FLOW_SAMPLE, **params)
    return [log for log in logs if log.is_flow_log]


def flow_log_get(request, log_id):
    """Get one flow log of the current project.

    A packet log or a log of another project is reported as not found, so
    that the panel can never act on it.
    """
    log = NetworkLog(_log_show(request, log_id))
    if not log.is_flow_log or log.project_id != _project_id(request):
        raise exceptions.NotFound(
            _("Flow log %s could not be found.") % log_id)
    return log


def flow_log_create(request, name, description, security_group_id, event,
                    enabled=True):
    body = {'log': {'name': name,
                    'description': description,
                    'resource_type': RESOURCE_SECURITY_GROUP,
                    'resource_id': security_group_id,
                    'event': event,
                    'enabled': enabled,
                    'output_type': OUTPUT_FLOW_SAMPLE}}
    return NetworkLog(_log_create(request, body))


def flow_log_set_enabled(request, log_id, enabled):
    """Enable or disable a flow log.

    The server checks the permission and the output support again on every
    enable request, so enabling can fail where disabling works.
    """
    flow_log_get(request, log_id)
    body = {'log': {'enabled': enabled}}
    return NetworkLog(_log_update(request, log_id, body))


def flow_log_delete(request, log_id):
    flow_log_get(request, log_id)
    _log_delete(request, log_id)


def _port_security_groups(request, port_id):
    try:
        return neutron.port_get(request, port_id).security_groups or []
    except Exception:
        LOG.exception("Unable to get port %s of a packet log.", port_id)
        return None


def overlapping_packet_logs(request, security_group_id):
    """Enabled packet logs applied, or maybe applied, to the security group.

    A packet log and a flow log enabled on the same security group are not
    supported together. The server does not reject the combination and has
    no check to copy, so this follows how the OVN driver picks the Port
    Groups of a packet log. It tells where the logs are applied; whether
    they really interfere was not tested.

    Only the packet logs of the current project are read. A packet log of
    another project without a security group and a port is applied to
    every security group too, and is not seen here. An empty result means
    "none found in this project", not "none".

    * the same security group, or no security group and no port with the
      ``ALL`` or ``ACCEPT`` event (every security group): overlap;
    * only a port: overlap when the port uses the security group, not
      reported when it does not, possible when the port can not be read;
    * no security group and no port with the ``DROP`` event: possible. It
      is applied to the common drop Port Group only.

    Each returned log has ``overlap`` set to ``OVERLAP_CONFIRMED`` or
    ``OVERLAP_POSSIBLE``.
    """
    overlaps = []
    for log in _log_list(request, enabled=True):
        # Only packet logs; an output this plugin does not know is skipped.
        if log.output != OUTPUT_PACKET_LOG:
            continue
        if log.resource_id:
            if log.resource_id != security_group_id:
                continue
            log.overlap = OVERLAP_CONFIRMED
        elif log.target_id:
            groups = _port_security_groups(request, log.target_id)
            if groups is None:
                log.overlap = OVERLAP_POSSIBLE
            elif security_group_id in groups:
                log.overlap = OVERLAP_CONFIRMED
            else:
                continue
        elif log.event == EVENT_DROP:
            log.overlap = OVERLAP_POSSIBLE
        else:
            log.overlap = OVERLAP_CONFIRMED
        overlaps.append(log)
    return overlaps


def security_group_label(security_group):
    name = security_group.name or '-'
    return '%s (%s)' % (name, security_group.id[:8])


def security_group_labels(request):
    """The security groups of the project as ``{id: label}``."""
    return {sg.id: security_group_label(sg)
            for sg in neutron.security_group_list(request)}


def security_group_choices(request):
    """``(id, label)`` choices of the security groups of the project."""
    return sorted(security_group_labels(request).items(),
                  key=lambda choice: choice[1])


def annotate_security_groups(request, logs):
    """Attach ``security_group_display`` to the wrappers."""
    if not logs:
        return logs
    try:
        labels = security_group_labels(request)
    except Exception:
        LOG.exception("Unable to list security groups; they are shown "
                      "by id.")
        labels = {}
    for log in logs:
        log.security_group_display = labels.get(log.resource_id,
                                                log.resource_id or '-')
    return logs
