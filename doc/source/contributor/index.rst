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

=================
Contributor Guide
=================

See `Horizon Contributor Documents
<https://docs.openstack.org/horizon/latest/contributor/index.html>`__
for general topics on developing a dashboard plugin for horizon.

Project layout
--------------

``neutron_log_dashboard/api/network_log.py``
    The only module that talks to Neutron. It uses
    ``openstack_dashboard.api.neutron.neutronclient`` where horizon still
    provides it and the openstacksdk ``networkclient`` otherwise.
    openstacksdk has no network log resource, so that path sends the
    requests through the proxy session.

``neutron_log_dashboard/dashboards/project/flow_logs``
    Panel, table, form, views and templates.

``neutron_log_dashboard/conf/neutron_policy.d``
    Optional policy example for horizon, see :doc:`../configuration/index`.

``neutron_log_dashboard/test``
    Unit tests. The API tests run the real clients against a mocked HTTP
    transport, on both client paths. The policy tests run the real
    ``openstack_auth`` policy engine with a mocked Neutron API.

Running the tests
-----------------

.. code-block:: console

   $ curl -sSL -o uc.txt https://releases.openstack.org/constraints/upper/2025.1
   $ pip install "setuptools<80" wheel
   $ pip install --no-build-isolation -c uc.txt horizon \
         -r requirements.txt -r test-requirements.txt
   $ flake8
   $ python manage.py extract_messages --module neutron_log_dashboard \
         --verbosity 0 --check-only
   $ python manage.py test neutron_log_dashboard \
         --settings=neutron_log_dashboard.test.settings

``tox`` uses the master constraints by default.

What the tests cover
--------------------

The ``ci`` workflow runs the same tests in two environments and keeps
them apart:

* Horizon 25.3.2 with the 2025.1 constraints (python-neutronclient 11.4.1,
  openstacksdk 4.4.1). Horizon builds both clients here, so both client
  paths run.
* Horizon 27.0.0 with the master constraints. Horizon only builds the
  openstacksdk client; the python-neutronclient path tests are skipped.

Both are unit tests with a mocked Neutron. They do not need, and do not
prove anything about, a server with the ``logging-output-type``
extension. Not covered by any test: a real Neutron server and its policy,
real tokens and role inheritance, the collection of flow records.

----

.. toctree::
   :maxdepth: 1

   DevStack plugin <devstack-plugin>
