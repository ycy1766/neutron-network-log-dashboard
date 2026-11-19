=====================
neutron-log-dashboard
=====================

Horizon panel for Neutron network logs with the ``flow_sample`` output
(flow logs). Work in progress; not released.

The Neutron server must have the ``logging-output-type`` API extension. It
is not part of upstream Neutron: its specification is still under review
and it only exists in servers that carry the implementation. Without the
extension the panel is hidden.

A flow log is a Neutron network log (``/v2.0/log/logs``) whose
``output_type`` is ``flow_sample``. It samples the traffic that one security
group accepts or drops. The panel only manages flow logs of the current
project. Packet logs are not managed here; they are only read to point out an
enabled packet log that is applied to the security group of a flow log.

Collected flow records are not shown. A successful API call does not prove
that records are collected.

Limits
------

* Only packet logs of the current project are read. A packet log of
  another project that selects no security group and no port is applied to
  every security group as well and is not seen. "No overlapping packet log
  found" therefore means none in this project.
* The overlap check tells where logs are applied. Whether a packet log and
  a flow log really interfere was not tested.

Status
------

* Neutron calls for both client paths, python-neutronclient and
  openstacksdk (which has no network log resource, so the requests go
  through its session).
* Panel (Project > Network > Flow Logs): list, create, detail, enable,
  disable, delete.
* Documentation under ``doc/source``, release notes, DevStack plugin and a
  GitHub Actions workflow. The DevStack plugin and the workflow were not
  run.

Testing
-------

Unit tests with a mocked Neutron, run in two environments:

* Horizon 25.3.2 with the 2025.1 constraints (python-neutronclient 11.4.1,
  openstacksdk 4.4.1): both client paths.
* Horizon 27.0.0 with the master constraints (openstacksdk 4.22.0): the
  openstacksdk path; the python-neutronclient tests are skipped because
  that Horizon does not build the client.

See ``doc/source/contributor/index.rst`` for the commands. ``tox`` uses the
master constraints by default and was not run.

Not tested: a Neutron server with the extension and its policy, real tokens
and role inheritance, the collection of flow records, a browser.

Policy
------

``neutron_log_dashboard/conf/neutron_policy.d/log.yaml`` is an optional
policy example for Horizon: the five network log rules Neutron already has
and ``create_log:output_type`` of the extension. It is not loaded
automatically; see the comment in the file.

With the example a project manager gets the panel and can disable and
delete flow logs; creating and enabling stays with the administrator.
Without it Horizon uses its own defaults, which differ by release; see
``doc/source/configuration/index.rst``.

Add the directory, with its absolute path, to the ``network`` list of
``POLICY_DIRS``. Add to the list instead of replacing the setting.
