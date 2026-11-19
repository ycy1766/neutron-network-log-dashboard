..
      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=============
Configuration
=============

Panel visibility
----------------

The Flow Logs panel is displayed when the Neutron server advertises the
``logging-output-type`` extension. It can be hidden regardless of the
server with the ``enable_flow_log`` key of ``OPENSTACK_NEUTRON_NETWORK``
in the horizon ``local_settings.py``:

.. code-block:: python

   OPENSTACK_NEUTRON_NETWORK['enable_flow_log'] = False

This is not a permission. What a user may do is decided by the policy.

Policy rules
------------

Horizon decides whether to show the panel and its buttons with its own copy
of the Neutron policy. The Neutron server always has the final say: every
request is checked again by the server policy.

The panel checks these rules:

==================== ==========================================
Action               Rules
==================== ==========================================
Panel, list, detail  ``get_log``
Create               ``create_log`` and ``create_log:output_type``
Enable               ``update_log`` and ``create_log:output_type``
Disable              ``update_log``
Delete               ``delete_log``
==================== ==========================================

``create_log:output_type`` belongs to the ``logging-output-type``
extension. Horizon does not know it, so in Horizon it falls back to the
``default`` rule, which a member of the project passes. For that reason
the panel never decides with this rule alone: it is always checked together
with ``create_log`` or ``update_log``. This only limits what Horizon shows.

Without further configuration Horizon uses its own default policy for the
five existing log rules, and that differs by release:

* Horizon 2025.1: administrator only. Only an administrator gets the
  panel.
* Horizon 27.0.0: administrator or project manager. A project manager gets
  the panel. Because ``create_log:output_type`` falls back to the default
  rule, the manager is also shown the create and enable buttons, and the
  server refuses those requests. Load the example below, or your own
  rules, to avoid that.

The plugin ships an optional example,
``neutron_network_log_dashboard/conf/neutron_policy.d/log.yaml``. It is not
loaded automatically. Its check strings were copied from the server implementation
the plugin was written against; they are not a general Neutron default. If
your server policy differs, use your own strings.

.. literalinclude:: ../../../neutron_network_log_dashboard/conf/neutron_policy.d/log.yaml
   :language: yaml
   :start-after: # here. The server always has the final say.

With the example a project manager gets the panel and can disable and
delete the flow logs of the project; creating and enabling stays with the
administrator.

To load it, add the directory to the list of the ``network`` service in
``POLICY_DIRS``. Add to the list; do not assign a new dictionary, which
would drop the directories of Horizon and of other plugins:

.. code-block:: python

   POLICY_DIRS.setdefault('network', []).append(
       '/usr/lib/python3/dist-packages/neutron_network_log_dashboard/conf/'
       'neutron_policy.d')

Use the absolute path of the installed package. A relative path is joined
to ``POLICY_FILES_PATH``. Rules read from a policy directory replace
rules of the same name from the policy file and from the Horizon defaults.
Rules of other names, for example of another plugin in another directory,
are kept.

For more configurations, see
`Configuration Guide
<https://docs.openstack.org/horizon/latest/configuration/index.html>`__
in the Horizon documentation.
