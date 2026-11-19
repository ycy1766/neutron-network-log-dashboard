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

==========
User Guide
==========

The **Project > Network > Flow Logs** panel manages the flow logs of the
current project. A flow log is a Neutron network log with the
``flow_sample`` output: the server samples the traffic that one security
group accepts or drops and exports it as flow records.

The panel does not show the collected flow records, and it does not show
whether records are being collected. A successful action means that Neutron
recorded the change.

Creating a flow log
-------------------

Click **Create Flow Log** and fill in:

Name, Description
    Optional.

Security Group
    The security group whose traffic is sampled. The choices show the name
    and the first characters of the id.

Event
    *All*, *Accept* (accepted traffic only) or *Drop* (dropped traffic
    only).

Enabled
    Whether sampling starts right away.

The security group and the event can not be changed after creation: delete
the flow log and create a new one.

Enabling and disabling
----------------------

A flow log can be disabled and enabled again from the table. The server
checks the permission and its configuration again on every enable request,
so enabling can be refused where disabling works. The message of the server
is shown.

When several flow logs are selected and some fail, each failed one is
listed with the message of the server, and the ones that were done are
listed separately.

Packet logs on the same security group
--------------------------------------

A packet log and a flow log enabled on the same security group are not
supported together. The server does not refuse this combination.

After a flow log is created enabled, or enabled, the panel warns when it
finds an enabled packet log that is applied to the same security group, or
that may be. The warning comes after the change; nothing is disabled or
deleted automatically. The detail page lists the same packet logs.

The check tells where the logs are applied. Whether they really interfere
was not tested. Only the packet logs of the current project are read: a
packet log of another project that selects no security group and no port is
applied to every security group as well and is not seen. When nothing is
found, the detail page says so in these words, and the create and enable
actions say nothing.

Limits of the current version
-----------------------------

* Only flow logs are listed and changed. Packet logs are not managed here,
  also not when opened by their URL.
* Only the flow logs of the current project are shown, also to an
  administrator.
* The output type of a log can not be changed; this is a rule of the API.
