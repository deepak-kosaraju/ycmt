#!/bin/sh

# This can be overriden on the command line by passing the env vars
# eg PT_HOSTNAME=foo.com PT_PORT=1234 sudo -E setup.sh
# If not overriden, it takes the defaults.
PT_HOSTNAME=${PT_HOSTNAME:-logs5.papertrailapp.com}
PT_PORT=${PT_PORT:-31881}

VERSION="20161005"

RSYSLOG_DIR=${RSYSLOG_DIR:-"/etc/rsyslog.d"}
RSYSLOG_CONF=${RSYSLOG_CONF:-"$RSYSLOG_DIR/95-papertrail.conf"}
SYSLOGNG_CONF=${SYSLOGNG_CONF:-"/etc/syslog-ng.conf"}
SYSLOGD_CONF=${SYSLOGD_CONF:-"/etc/syslogd.conf"}

detect_syslog_daemon() {
  if [ -d "$RSYSLOG_DIR" ]; then
    syslog_daemon="rsyslog"
    config_file=$RSYSLOG_CONF
  elif [ -f "$SYSLOGNG_CONF" ]; then
    syslog_daemon="syslog-ng"
    config_file=$SYSLOGNG_CONF
  elif [ -f "$SYSLOGD_CONF" ]; then
    syslog_daemon="syslogd"
    config_file=$SYSLOGD_CONF
  else
    echo "Could not detect syslog daemon in use."
	show_troubleshooting
    exit 2
  fi

  echo "    Detected syslog daemon: ${syslog_daemon}"
  echo "    Config file to be updated: ${config_file}"
}

detect_writable_config () {
  if [ $syslog_daemon = "rsyslog" ]; then
    if [ ! -w "$RSYSLOG_DIR" ]; then
      echo "$RSYSLOG_DIR is not writable. Please re-run this script as root or by using sudo."
      exit 2
    fi
  else
    if [ ! -w "$config_file" ]; then
      echo "$config_file is not writable. Please re-run this script as root or by using sudo."
      exit 2
    fi
  fi
}

detect_pt_config() {
  if [ -z "$PT_HOSTNAME" ] || [ -z "$PT_PORT" ]; then
    # Make sure the env vars are present. Saves us from a particular failure, albeit an unlikely one.
    echo "Could not auto-detect Papertrail configuration: PT_HOSTNAME and PT_PORT environment variables not set."
	show_troubleshooting
    exit 2
  fi

  echo "    Papertrail log destination: ${PT_HOSTNAME}:${PT_PORT}"
}

confirm_environment_detection() {
  echo "Auto-detected settings:"
  detect_syslog_daemon
  detect_writable_config
  detect_pt_config
  echo

  if [ -z $quiet_mode ]; then
    # shellcheck disable=SC2039
    # Not POSIX-compliant, `read -p` works in both bash and Ubuntu's dash
    read -r -p "Is this correct? (y/n) " answer
    echo
    case $answer in
      [Yy]* ) return;;
      [Nn]* ) exit;;
      * ) echo "Please answer y or n.";;
    esac
  fi
}

write_rsyslog_config () {
  if [ -f "$RSYSLOG_CONF" ]; then
    echo
    echo "Detected an existing Papertrail config. Backing it up to ${RSYSLOG_CONF}.bak"
    echo
    mv "$RSYSLOG_CONF" "$RSYSLOG_CONF.bak"
  fi

  if [ $PT_PORT = "514" ]; then
    echo "*.*          @${PT_HOSTNAME}" > "$RSYSLOG_CONF"
  else
    echo "*.*          @${PT_HOSTNAME}:${PT_PORT}" > "$RSYSLOG_CONF"
  fi
}

write_syslogng_config () {
  cp "$SYSLOGNG_CONF" "$SYSLOGNG_CONF.bak"

  if grep -Fq "destination d_papertrail" "$SYSLOGNG_CONF"; then
    echo "Error: Found an existing Papertrail log destination in $SYSLOGNG_CONF. Logging seems to have already been configured."
    show_troubleshooting
    exit 2
  fi

  tee -a "$SYSLOGNG_CONF" 1> /dev/null 2> /dev/null <<- EOT
destination d_papertrail {
  udp("${PT_HOSTNAME}" port(${PT_PORT}));
};
log { source(s_sys); destination(d_papertrail); };
EOT
}

write_syslogd_config () {
  cp "$SYSLOGD_CONF" "$SYSLOGD_CONF.bak"

  if grep -Fq "papertrail" "$SYSLOGD_CONF"; then
    echo "Error: Found an existing Papertrail log destination in $SYSLOGD_CONF. Logging seems to already be configured."
    show_troubleshooting
    exit 2
  fi

  echo "*.*            @${PT_HOSTNAME}" >> "$SYSLOGD_CONF"
}

restart_daemon() {
  svc=$(which service)
  if [ ! -f "$svc" ]; then
    echo
    echo "Cannot find service binary to restart ${syslog_daemon}. Restart service manually."
    echo
  else
    service $syslog_daemon restart
  fi
}

show_troubleshooting() {
  cat << EOF
This seems like a job for a human! Please either:
  • Let us make quick work of it. Copy and paste this output into an email
    to support@papertrailapp.com.
  or
  • Perform the steps on https://papertrailapp.com/systems/setup manually.

EOF
}

show_help() {
  cat << EOF

Usage: ${0##*/} [-hvq]
  Setup system syslog daemon to log to Papertrail.
  Supported syslog daemons: rsyslog

  More: https://help.papertrailapp.com/

  Optional arguments:
      -h          display this help and exit
      -q          quiet/unattended mode; do not prompt for confirmation
      -V          display version and exit
EOF
}

main() {
  confirm_environment_detection

  echo "Applying config and restarting ${syslog_daemon}..."
  if [ $syslog_daemon = "rsyslog" ]; then
    write_rsyslog_config
    restart_daemon
  elif [ $syslog_daemon = "syslog-ng" ]; then
    write_syslogng_config
    restart_daemon
  elif [ $syslog_daemon = "syslogd" ]; then
    write_syslogd_config
    restart_daemon
  fi
}

while getopts ":hVq" opt; do
  case "$opt" in
  h)
    show_help >&2
    exit 1
    ;;
  q)
    quiet_mode=1
    ;;
  V)
    printf "$VERSION\n"
    exit 1
    ;;
  esac
done

main

echo
echo "Papertrail setup complete!"
logger "Papertrail setup complete for $(hostname)"