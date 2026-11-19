=========================================
DevStack plugin for neutron-log-dashboard
=========================================

This is setup as a DevStack plugin.
For more information on DevStack plugins,
see the `DevStack Plugins documentation
<https://docs.openstack.org/devstack/latest/plugins.html>`__.

How to enable the log dashboard
-------------------------------

Add the following to the localrc section of your local.conf. When the
DevStack plugin is configured, the ``neutron-log-dashboard`` service is
automatically enabled.

.. code-block:: none

   [[local|localrc]]
   enable_plugin neutron-log-dashboard https://github.com/ycy1766/neutron-log-dashboard main

The panel is only shown when Neutron advertises the ``logging-output-type``
extension. That extension is not part of upstream Neutron, so a DevStack
built from upstream Neutron installs the plugin but does not show the
panel. The DevStack plugin was not run.
