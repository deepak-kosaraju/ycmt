import os
import sys
import argparse
import json
import re
import traceback
from time import sleep
from socket import gethostname as hostname
# import slackclient as slk
import subprocess as cli
from pprint import pprint as pp
import datetime
import time

cwd = os.path.dirname(os.path.realpath(__file__))

# script_name = os.path.basename(__file__)
# file_name = script_name.split('.')[0]

packages = {}
services = {}
conf_files = {}
full_hostname = hostname()
short_hostname = full_hostname.split('.')[0]

conf_dir = cwd.strip('bin') + 'conf/'


def main():
    global verbose, dryrun, pkg, color, warnH, failH, fail, creset, header, add_time
    arg_parser = argparse.ArgumentParser(description='Yet(another)ConfigurationManagementTool - ycmt to deploy and configure simple services \
                                     and if deployment is success send message to SLACK channel')
    arg_parser.add_argument('--verbose', '-v',
                            help='increase output verbosity, for more verbosity use -vv', action='count')
    arg_parser.add_argument('--conf', '-c', action="store",  default=conf_dir + "default.json",
                            help="path to config file. Default: ./conf/default.json")
    # parser.add_argument('--dryrun',
    #                     help='for dry-run only', action='store_true')

    args = arg_parser.parse_args()
    verbose = args.verbose
    color = Colors()
    warnH = color.HEADER + color.WARNING
    failH = color.HEADER + color.FAIL
    fail = color.FAIL
    creset = color.reset_color
    header = color.HEADER + color.OKBLUE

    # calculate the offset taking into account daylight saving time
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
    current_time = datetime.datetime.now().replace(
        tzinfo=datetime.timezone(offset=utc_offset)).isoformat()

    add_time = color.UNDERLINE + color.purple + current_time + creset
# print(warnH + "WARNING:" + creset)
# read the config files for this script
    try:
        with open(args.conf, 'r') as conf_file:
            base_policy = json.load(conf_file)
            # if verbose >= 3:
            # print("default config file loaded: {}".format(base_policy))
        if os.path.isfile(conf_dir + short_hostname + '.json'):
            with open(conf_dir + short_hostname + '.json') as host_conf_file:
                host_policy = json.load(host_conf_file)
                # if verbose >= 2:
                #     print("config file updated to host spec:\n{}".format(host_policy))
    except IOError as err:
        print(err)

    # Appling default policy and then we will jump to individual host policies
    if base_policy:
        print(header+"Applying Base Policies of Package Manager, Services, Configs"+creset)
        manage_packages('base', base_policy['packages'])
        manage_services('base', base_policy['services'])
        # manage_configs('base', base_policy['configs'])
    if host_policy:
        print(header+"Applying Host Policies of Package Manager, Services, Conigs"+creset)
        manage_packages('host', host_policy['packages'])
        manage_services('host', host_policy['services'])
        # manage_configs('host', host_policy['configs'])


def manage_packages(policy, rules):
    policy_msg = color.UNDERLINE + color.HEADER + policy.upper() + creset
    if rules['install'] and len(rules['install']) != 0:
        msg = "Applying package install rules of " + color.purple + policy + creset + " on this host: " + \
            color.brown + color.HEADER + full_hostname + creset
        print(msg)
        for pkg, version in rules['install'].items():
            # for now we install latest availabe version in the apt repo
            # future release will support specific version of pkg that can be installed
            if not check_if_installed(pkg):
                msg = color.brown + color.UNDERLINE + pkg + creset
                print(add_time + " {} - package not found, so installing it".format(msg))
                apt_install(pkg)
            else:
                msg = color.OKGREEN + pkg + creset
                print(add_time +
                      " {} package was already installed as per policy, so nothing to apply ".format(msg))
    if rules['remove'] and len(rules['remove']) != 0:
        for pkg in rules['remove']:
            if check_if_installed(pkg):
                print(
                    add_time + warnH + " removing {} package as per rule in {} policy".format(pkg, policy_msg))
                apt_remove(pkg)
            else:
                msg = add_time + failH + " {} cannot be removed as per rule in {} policy, " + \
                    color.OKGREEN + \
                    "Reason: package current \"Not Installed\"" + creset
                print(
                    msg.format(pkg, policy_msg))


def manage_services(policy, rules):
    if rules and len(rules) != 0:
        for svc, state in rules.items():
            if state is 'started' or state is 'stopped':
                if not current_service_state(svc):
                    enforce_service_state(svc, state)
            elif state is 'reloaded':
                enforce_service_state(svc, state)
            else:
                msg = "service state is as defined in the rule"


def manage_configs(policy, rules):
    print('manage_config')

# Check if package is already installed


def check_if_installed(package):
    dpkg_list = 'dpkg -l ' + package
    return run_commands('check_if_installed', dpkg_list)

# Install requied package


def apt_install(package):
    msg = color.cyan + package + creset
    apt_install = 'apt-get install -y ' + package
    run_commands('apt_install', apt_install)

# Remove package defined in policy files


def apt_remove(package):
    apt_remove = 'apt-get remove -y ' + package
    run_commands('apt_remove', apt_remove)
    # copy config files


def copy_files(files):
    print("Files to Copy are:{}".format(files))

# Ensure necessary services are started


def current_service_state(svc):
    print("checking service state")


def enforce_service_state(svc, state):
    print("managing service: {}, state:{}".format(svc, state))

# Function to any system comamnd


def run_commands(call_type, cmd):
    global testing
    try:
        cmd = list(cmd.split())
        if verbose >= 3:
            print(cmd)
        proc = cli.Popen(
            cmd, stdout=cli.PIPE, stderr=cli.PIPE)
        if call_type is 'check_if_installed':
            is_installed = cli.Popen(
                ["grep", "^ii"], stdin=proc.stdout, stdout=cli.PIPE, stderr=cli.PIPE)
            proc.stdout.close()
            std_out, std_error = is_installed.communicate()
            # print("InInstalled: OUT{}".format(std_out))
            ret_code = is_installed.returncode
        else:
            # print("in else")
            std_out, std_error = proc.communicate()
            # print("std_out:{}, STDERROR: {}".format(std_out, std_error))
            ret_code = proc.returncode
            # print("ret_code:{}".format(ret_code))
        # print(ret_code)
        # std_out = std_out.replace('\n', '|n').replace('\r', '|r')
        # print("STDOUT: {}, STDERR: {}".format(std_out, std_error))
        # if dryrun:
        #     ret_code = 0  # For Testing Purpose only..
        if ret_code == 0:
            return True
        elif ret_code < 0 or ret_code > 0:
            msg = 'Calltype=' + call_type + ' action failed with Exit code=' + \
                str(ret_code) + '; stdout=' + str(std_out) + \
                '; stderr=' + str(std_error)
            # print_logger(msg, 'error')
            # sys.exit(ret_code)
    except OSError as e:
        print("Execution failed:{}".format(e))

# Print and log


def print_logger(msg):
    print(msg)


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[1;33m'
    FAIL = '\033[91m'
    UNDERLINE = '\033[4m'
    cyan = "\033[0;36m"
    purple = "\033[0;35m"
    brown = "\033[0;33m"
    reset_color = "\033[0m"


def exception():
    print(traceback.format_exc())


if __name__ == "__main__":
    main()
