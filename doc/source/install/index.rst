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

============
Installation
============

Requirements
------------

* Horizon, in the same Python environment as the plugin. The plugin was
  tested with Horizon 25.3.2 (2025.1) and Horizon 27.0.0; see
  :doc:`../contributor/index` for what was tested.
* A Neutron server with the ``logging`` service plugin and the
  ``logging-output-type`` API extension. The extension is not part of
  upstream Neutron: its specification is under review and only servers that
  carry the implementation have it. Without the extension the panel is
  hidden.
* For flow logs to be created, a logging driver of the server must support
  the ``flow_sample`` output for security groups. If none does, the panel
  is shown without the create button.

Manual Installation
-------------------

Before installing neutron-log-dashboard,
you first need to install horizon in your environment.

Fetch the source code from git and run pip install.
Make sure to install neutron-log-dashboard into the same python environment
where horizon is installed.

.. code-block:: console

   $ git clone https://github.com/ycy1766/neutron-log-dashboard
   $ cd neutron-log-dashboard
   $ sudo pip install .

Enable the horizon plugin.

.. code-block:: console

   $ cp neutron_log_dashboard/enabled/_7210_project_flow_logs_panel.py \
         /opt/stack/horizon/openstack_dashboard/local/enabled/_7210_project_flow_logs_panel.py

.. note::

   The directory ``local/enabled`` may be different depending on your
   environment or distribution used. For example, for Ubuntu, this is
   ``/usr/share/openstack-dashboard/openstack_dashboard/local/enabled``.
   The openstack-helm Horizon chart links the file when
   ``neutron_log_dashboard`` is added to the list
   ``conf.horizon.extra_panels``. Add it to the list; the modules already
   there keep their panels.

.. note::

   The number of the plugin enabled file determines the order of panels.
   If you would like to configure the place of the Flow Logs panel,
   change the number of the file.

.. note::

   For more detail of the horizon plugin settings,
   see `Pluggable Settings
   <https://docs.openstack.org/horizon/latest/configuration/pluggable_panels.html>`__
   in the horizon documentation.

Configure the policy Horizon uses for the network log rules so that it
matches your Neutron server, see :doc:`../configuration/index`. The plugin
only ships an optional example. With the Horizon defaults alone the buttons
can differ from what the server allows: on Horizon 27.0.0 a project manager
is shown create and enable buttons that the server refuses. This does not
bypass the server policy, but the panel is then misleading.

Run the Django update commands (if you use).

.. code-block:: console

   $ DJANGO_SETTINGS_MODULE=openstack_dashboard.settings python manage.py collectstatic --noinput
   $ DJANGO_SETTINGS_MODULE=openstack_dashboard.settings python manage.py compress --force

Restart Apache:

.. code-block:: console

   $ sudo service apache2 restart
