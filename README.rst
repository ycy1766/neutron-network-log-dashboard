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

* Neutron calls: done for both client paths, python-neutronclient and
  openstacksdk (which has no network log resource, so the requests go
  through its session). Both paths pass the same tests.
* Panel (Project > Network > Flow Logs): list, create, detail, enable,
  disable, delete.
* Policy tests with the real Horizon policy engine and a mocked Neutron
  API: done. The server policy and real tokens are not exercised.
* Documentation, CI, browser checks: not done.

Testing
-------

The tests were run only with Horizon 25.3.2 (2025.1), python-neutronclient
11.4.1 and openstacksdk 4.4.1, in a Python 3.12 virtualenv::

    curl -sSL -o uc.txt https://releases.openstack.org/constraints/upper/2025.1
    pip install "setuptools<80" wheel
    pip install --no-build-isolation -c uc.txt pbr horizon \
        python-neutronclient requests-mock
    python manage.py test neutron_log_dashboard \
        --settings=neutron_log_dashboard.test.settings

``tox`` uses the master constraints by default and was not run. Later
Horizon releases, which have only the openstacksdk client, are not tested;
passing the openstacksdk path tests here does not confirm them.

Policy
------

``neutron_log_dashboard/conf/neutron_policy.d/log.yaml`` is an optional
policy example for Horizon: the five network log rules Neutron already has
and ``create_log:output_type`` of the extension. It is not loaded
automatically; see the comment in the file.

With the rules a project manager gets the panel and can disable and delete
flow logs; creating and enabling stays with the administrator. Without
them Horizon uses its own defaults, which are administrator only for the
five existing rules, so only an administrator gets the panel.

Use an absolute path in ``POLICY_DIRS``. A relative one is joined to
``POLICY_FILES_PATH``, which a deployment usually points at its
configuration directory. Rules read from a policy directory replace rules
of the same name from the policy file and from the defaults; rules of other
plugins in other directories are kept.
