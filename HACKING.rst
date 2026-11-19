================================================
Neutron Network Log Dashboard Style Commandments
================================================

Read the OpenStack Style Commandments
https://docs.openstack.org/hacking/latest/user/hacking.html

Project Specific Commandments
-----------------------------

- Read the Horizon contributing documentation at
  https://docs.openstack.org/horizon/latest/contributor/contributing.html
- All calls to Neutron live in
  ``neutron_network_log_dashboard/api/network_log.py``. Views, forms and
  tables never build a client themselves.
- Text that comes from the server (error messages, names) is shown as plain
  text. Never mark it safe for HTML.
- [M322] Method's default argument shouldn't be mutable.
