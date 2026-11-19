# plugin.sh - DevStack plugin.sh dispatch script neutron-log-dashboard

LOG_DASHBOARD_DIR=$(cd $(dirname $BASH_SOURCE)/.. && pwd)
LOG_ENABLED_DIR=$LOG_DASHBOARD_DIR/neutron_log_dashboard/enabled
HORIZON_ENABLED_DIR=$DEST/horizon/openstack_dashboard/local/enabled

function install_neutron_log_dashboard {
    setup_develop $LOG_DASHBOARD_DIR
}

function configure_neutron_log_dashboard {
    cp -a $LOG_ENABLED_DIR/_[0-9]*.py $HORIZON_ENABLED_DIR
    # NOTE: If locale directory does not exist, compilemessages will fail,
    # so check for an existence of locale directory is required.
    if [ -d $LOG_DASHBOARD_DIR/neutron_log_dashboard/locale ]; then
        (cd $LOG_DASHBOARD_DIR/neutron_log_dashboard; \
         DJANGO_SETTINGS_MODULE=openstack_dashboard.settings $PYTHON ../manage.py compilemessages)
    fi
}

# check for service enabled
if is_service_enabled neutron-log-dashboard; then

    if [[ "$1" == "stack" && "$2" == "pre-install"  ]]; then
        # Set up system services
        # no-op
        :

    elif [[ "$1" == "stack" && "$2" == "install"  ]]; then
        # Perform installation of service source
        echo_summary "Installing Neutron Log Dashboard"
        install_neutron_log_dashboard

    elif [[ "$1" == "stack" && "$2" == "post-config"  ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring Neutron Log Dashboard"
        configure_neutron_log_dashboard

    elif [[ "$1" == "stack" && "$2" == "extra"  ]]; then
        # no-op
        :
    fi

    if [[ "$1" == "unstack"  ]]; then
        # Remove enabled file(s)
        for _enabled_file in $LOG_ENABLED_DIR/_[0-9]*.py; do
            _enabled_basename=$(basename $_enabled_file .py)
            rm -f $HORIZON_ENABLED_DIR/${_enabled_basename}.py*
            rm -f $HORIZON_ENABLED_DIR/__pycache__/${_enabled_basename}.*pyc
        done
    fi

    if [[ "$1" == "clean"  ]]; then
        # Remove state and transient data
        # Remember clean.sh first calls unstack.sh
        # no-op
        :
    fi
fi
