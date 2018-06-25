import os
import sys
import argparse
import json
import traceback
from socket import gethostname as hostname
import subprocess as cli
import datetime
import time
import filecmp
# from slackclient import SlackClient as slk
from shutil import copyfile as cpfile
import pwd
import grp
import logging
from logging.handlers import RotatingFileHandler

cwd = os.path.dirname(os.path.realpath(__file__))

full_hostname = hostname()
short_hostname = full_hostname.split('.')[0]

source_dir = cwd.strip('bin')
conf_dir = source_dir + 'conf/'
ignore_true = 'true'

global current_time

# calculate the offset taking into account daylight saving time
utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
current_time = datetime.datetime.now().replace(
    tzinfo=datetime.timezone(offset=utc_offset), microsecond=0).isoformat()

LOG_FILENAME = '/var/log/ycmt/application.log'

# set up logging to file basicConfig()
logging.basicConfig(level=logging.DEBUG,
                    datefmt=current_time,
                    filename=LOG_FILENAME,
                    format='%(asctime)s %(name)-8s %(levelname)-8s: %(message)s')

# Has to be enabled after addressing few issues with log handlers to avoid duplicate logging
# # Adding the log message handler to the logger for rotation of log
# rotate_file_handler = RotatingFileHandler(
#     LOG_FILENAME, maxBytes=100000000, backupCount=5)
# logging.addHandler(rotate_file_handler)

# defining couple of other loggers to ensure we log specific type of calls in the code
logger_app = logging.getLogger('ycmt')
logger_pkg = logging.getLogger('ycmt.pkg')
logger_svc = logging.getLogger('ycmt.svc')
logger_cfg = logging.getLogger('ycmt.cfg')

# Main Program
def main():
    global verbose, color, warnH, failH, fail, creset, header, add_time
    # Some color code reference to STDOUT console messages
    color = Colors()
    warnH = color.BOLD + color.WARNING
    failH = color.BOLD + color.FAIL
    fail = color.FAIL
    creset = color.reset_color
    header = color.BOLD + color.OKBLUE

    help_desc = header + color.OKGREEN + 'Yet(another)ConfigurationManagementTool ' + creset + '- ycmt to deploy and configure simple services'

    arg_parser = argparse.ArgumentParser(description=help_desc)
    arg_parser.add_argument(
        '--verbose', '-v', help='increase output verbosity, for more verbosity use -vv', action='count', default=0)
    arg_parser.add_argument('--conf', '-c', action="store", default=conf_dir + "default.json",
                            help="path to config file. Default: ./conf/default.json")

    args = arg_parser.parse_args()
    verbose = args.verbose

    add_time = color.UNDERLINE + color.purple + current_time + creset

    # Reading policy rules configs
    try:
        with open(args.conf, 'r') as conf_file:
            base_policy = json.load(conf_file)
            if verbose >= 3:
                print("default config file loaded: {}".format(base_policy))
        if os.path.isfile(conf_dir + short_hostname + '.json'):
            with open(conf_dir + short_hostname + '.json') as host_conf_file:
                host_policy = json.load(host_conf_file)
                if verbose >= 3:
                    print("config file updated to host spec:\n{}".format(host_policy))
    except IOError as err:
        print(err)

    # Appling default policy and then we will jump to individual host policies
    try:
        # Apply base policy first before applying host specfiic policies
        if base_policy:
            print(
                header + "## Applying Base Policies of Package Manager, Services, Configs ##" + creset)
            logger_app.info(
                'Applying Base Policies of Package Manager, Services, Configs')
            manage_packages('base', base_policy['packages'])
            manage_services('base', base_policy['services'])
            manage_configs('base', base_policy['configs'])

        # Apply HOST specific policies
        if host_policy:
            print(
                header + "## Applying Host Policies of Package Manager, Services, Conigs ##" + creset)
            logger_app.info(
                'Applying Host Policies of Package Manager, Services, Conigs')
            manage_packages('host', host_policy['packages'])
            manage_services('host', host_policy['services'])
            manage_configs('host', host_policy['configs'])
    except:
        exception()

# Function to manage-packages
def manage_packages(policy, rules):
    policy_msg = color.UNDERLINE + color.BOLD + policy.upper() + creset
    if rules['install'] and len(rules['install']) != 0:
        msg = add_time + " checking compliance of package install rules of " + policy_msg + " on this host: " + \
            color.brown + color.BOLD + full_hostname + creset
        print(msg)
        logger_pkg.info('checking compliance of package install rules of ' +
                        policy.upper() + ' on this host: ' + full_hostname)
        for pkg in rules['install']:
            # for now we install latest availabe version in the apt repo
            # future release will support specific version of pkg that can be installed
            if not check_if_installed(pkg):
                msg = color.brown + color.UNDERLINE + pkg + creset
                print(add_time + " {} - package not found, so installing it".format(msg))
                apt_install(pkg)
                logger_pkg.info('installing ' + pkg +
                                ' package, as per rule in ' + policy.upper() + ' policy.')
            else:
                msg = add_time + color.OKGREEN + ' Skipping..' + pkg + \
                    creset + ' package install as its installed and in compliance with above policy rule.'
                print(msg)
                logger_pkg.info(
                    'Skipping..' + pkg + ' package install as its installed and in compliance with above policy rule.')
    if rules['remove'] and len(rules['remove']) != 0:
        for pkg in rules['remove']:
            if check_if_installed(pkg):
                print(
                    add_time + warnH + " removing {} package as per rule in {} policy".format(pkg, policy_msg))
                apt_remove(pkg)
                logger_pkg.warning('removing ' + pkg +
                                   ' package as per rule in ' + policy.upper() + ' policy')
            else:
                msg = add_time + failH + " {} cannot be removed as per rule in {} policy, " + \
                    color.OKGREEN + \
                    "Reason: package current \"Not Installed\"" + creset
                print(
                    msg.format(pkg, policy_msg))
                logger_pkg.info(
                    pkg + ' cannot be removed as per rule in ' + policy.upper() + ' policy, Reason: package current \"Not Installed\"')

# Function  to manage-services
def manage_services(policy, rules):
    policy_msg = color.UNDERLINE + color.BOLD + policy.upper() + creset
    msg = add_time + " checking compliance of manage_services rules of " + policy_msg + \
        " on this host: " + color.brown + color.BOLD + full_hostname + creset
    print(msg)
    logger_svc.info('checking compliance of manage_services rules of ' +
                    policy.upper() + ' on this host: ' + full_hostname)
    if rules and len(rules) != 0:
        # print(rules)
        for svc, state in rules.items():
            if state == 'started' or state == 'stopped':
                if not check_service_state(svc, state):
                    msg = add_time + ' ' + policy_msg + ' policy rule enforces service: ' + color.brown + svc + creset + \
                        ' state to be ' + header + state.upper() + creset + \
                        ' but it appears its not as per compliance so enforcing the policy rule'
                    print(msg)
                    enforce_service_state(svc, state)
                    logger_svc.info(policy.upper() + ' policy rule enforces service: ' + svc + ' state to be ' +
                                    state.upper() + ' but it appears its not as per compliance so enforcing the policy rule')
                else:
                    msg = add_time + color.OKGREEN + 'Skipping..' + creset + policy_msg + ' policy rule enforces service: ' + color.brown + svc + creset + ' state to be ' + \
                        header + state.upper() + creset + \
                        ' and it appears all compliance for the policy rule are met.'
                    print(msg)
                    logger_svc.info('Skipping..' + policy.upper() + ' policy rule enforces service: ' + svc +
                                    ' state to be ' + state.upper() + ' and it appears all compliance for the policy rule are met.')
            elif state is 'reloaded':
                enforce_service_state(svc, 'reload')
            else:
                msg = header + 'This state is not implemented, please check the release version in future' + creset
                print(msg)
                logger_svc.error(
                    'This state is not implemented, please check the release version in future')

# Function to manage-configs
def manage_configs(policy, rules):
    policy_msg = color.UNDERLINE + color.BOLD + policy.upper() + creset
    msg = add_time + " checking compliance of manage_configs rules of " + policy_msg + \
        " on this host: " + color.brown + color.BOLD + full_hostname + creset
    print(msg)
    logger_cfg.info("checking compliance of manage_configs rules of " + policy.upper() +
                    " on this host: " + full_hostname)
    for file in rules['files']:
        try:
            if rules[file]['action'] == 'create':
                source = source_dir + rules[file]['source']
                if os.path.isfile(rules[file]['dest']):
                    if filecmp.cmp(source, rules[file]['dest']):
                        msg = add_time + color.OKGREEN + ' Skipping..' + \
                            rules[file]['dest'] + creset + \
                            ' content didn\'t change, so everything is in compliance with above policy rule.'
                        print(msg)
                        logger_cfg.info(
                            'Skipping..' + rules[file]['dest'] + ' content didn\'t change, so everything is in compliance with above policy rule.')
                        check_file_stat(
                            rules[file]['dest'], rules[file]['user'], rules[file]['group'], rules[file]['mode'])
                    else:
                        sync_notify(source, rules[file])
                        msg = add_time + color.OKGREEN + ' Copying..' + \
                            rules[file]['dest'] + creset + \
                            ' content changed in source ' + color.UNDERLINE + source + creset + \
                            ' change, so everything is in compliance with above policy rule.'
                        print(msg)
                        logger_cfg.info('Copying..' + rules[file]['dest'] + ' content changed in source ' +
                                        source + ' change, so everything is in compliance with above policy rule.')

                else:
                    msg = add_time + color.OKGREEN + ' Copying..' + \
                        rules[file]['dest'] + creset + \
                        ' file as its not found to meet compliance with above policy rule.'
                    print(msg)
                    logger_cfg.info(
                        'Copying..' + rules[file]['dest'] + ' file as its not found to meet compliance with above policy rule.')
                    sync_notify(source, rules[file])

            elif rules[file]['action'] == 'delete':
                if os.path.isfile(rules[file]['dest']):
                    os.remove(rules[file]['dest'])
                    msg = add_time + color.FAIL + ' Policy ENFORCED..' + rules[file]['dest'] + \
                        creset + ' file deleted as per compliance with above policy rule.'
                    print(msg)
                    logger_cfg.info(
                        'Policy ENFORCED..' + rules[file]['dest'] + ' file deleted as per compliance with above policy rule.')
                else:
                    msg = add_time + color.OKGREEN + ' Skipping..' + rules[file]['dest'] + \
                        creset + ' file deletion as everything is in compliance with above policy rule.'
                    print(msg)
                    logger_cfg.info(
                        'Skipping..' + rules[file]['dest'] + ' file deletion as everything is in compliance with above policy rule.')
        except:
            exception()

# Check various file stats to ensure file metadata like owner,group and permission mode are as per compliance
def check_file_stat(file, user, group, mode):
    file_stat_info = os.stat(file)
    # Consider only last 5 digits for file permissions
    cmode = oct(file_stat_info[0])[-5:]
    uuid = file_stat_info[4]
    guid = file_stat_info[5]
    # get valid user name who owns the file from /etc/passwd db
    cuser = pwd.getpwuid(uuid)[0]
    # get valid group name who owns the file from /etc/group db
    cgroup = grp.getgrgid(guid)[0]
    if verbose >= 2:
        print(file_stat_info)

    if cuser != user or cgroup != group:
        cmd = 'chown ' + user + ':' + \
            group + ' ' + file

        msg = add_time + ' current file ' + color.OKBLUE + color.BOLD + file + creset + ' ownership, user: ' + failH + cuser + creset + ', group: ' + failH + group + creset + \
            ', excpected ownership user: ' + color.OKGREEN + user + \
            creset + ', group: ' + color.OKGREEN + group + \
            creset + ' ,so applied changes as per compliance with above policy rule'
        print(msg)
        if run_shell_commands('change_ownership', cmd):
            msg = add_time + ' Ownership Update is: ' + color.OKGREEN + 'SUCCESS' + \
                creset + ' for file: ' + color.OKBLUE + color.BOLD + file + creset
            print(msg)
            logger_cfg.info('Ownership Update is: SUCCESS for file: ' + file)
        else:
            msg = add_time + ' Ownership Update is: ' + failH + 'UNSUCCESS' + \
                creset + ' for file: ' + color.OKBLUE + color.BOLD + file + creset
            print(msg)
            logger_cfg.info('Ownership Update is: UNSUCCESS for file: ' + file)

    else:
        msg = add_time + color.OKGREEN + ' Skipping..' + \
            file + creset + \
            ' Ownership as it is as per compliance with above policy rule.'
        print(msg)
        logger_cfg.info('Skipping..' + file +
                        ' Ownership as it is as per compliance with above policy rule.')
        if verbose >= 3:
            print("current mode:{}, policy mode:{}".format(cmode, mode))
    if cmode != mode:
        msg = add_time + ' current file permission mode: ' + failH + mode + creset + ', excpected file permission mode: ' + color.OKGREEN + mode + \
            creset + creset + ' ,so applied changes as per compliance with above policy rule'
        cmd = 'chmod ' + mode + ' ' + file
        if run_shell_commands('change_file_permissions', cmd):
            msg = add_time + ' Permission Mode Update is: ' + color.OKGREEN + 'SUCCESS' + \
                creset + ' for file: ' + color.OKBLUE + color.BOLD + file + creset
            print(msg)
            logger_cfg.info(
                'Permission Mode Update is: SUCCESS for file: ' + file)
        else:
            msg = add_time + ' Permission Mode Update is: ' + failH + 'UNSUCCESS' + \
                creset + ' for file: ' + color.OKBLUE + color.BOLD + file + creset
            print(msg)
            logger_cfg.info(
                'Permission Mode Update is: UNSUCCESS for file: ' + file)

    else:
        msg = add_time + color.OKGREEN + ' Skipping..' + \
            file + creset + \
            ' Permissions as it is as per compliance with above policy rule.'
        print(msg)

# To sync configs and notify the service either to reload (or) restart based on policy
def sync_notify(src, file):
    dst = file['dest']
    notify = file['notify']
    cpfile(src, dst)
    check_file_stat(
        file['dest'], file['user'], file['group'], file['mode'])
    if notify:
        svc, action = notify.split(':')
        msg = add_time + color.UNDERLINE + color.purple + \
            ' Making Notify Call to a service: ' + creset
        print(msg + '{}, action: {}'.format(svc, action))
        notify_service(svc, action)

# To notify service either to reload (or) restart based on rule in the policy definition
def notify_service(svc, action):
    cmd = 'service ' + svc + ' ' + action
    if run_shell_commands('notify_service', cmd):
        msg = add_time + ' Service: ' + svc + ', action:' + \
            action + ' is' + color.OKGREEN + ' SUCCESS' + creset
        print(msg)
    else:
        msg = add_time + 'Service: ' + svc + ', action:' + action + ' is' + \
            failH + ' UNSUCCESS' + creset + ', run using -vvv to verify details'
        print(msg)

        # Check if package is already installe

# validate if pkg is installed, this is to ensure we don't run unecessary system calls to install/remove packages
def check_if_installed(package):
    dpkg_list = 'dpkg -l ' + package
    return run_shell_commands('check_if_installed', dpkg_list)

# Install requied packag
def apt_install(package):
    apt_install = 'apt-get install -y ' + package
    run_shell_commands('apt_install', apt_install)

# Remove package defined in policy files
def apt_remove(package):
    apt_remove = 'apt-get remove -y ' + package
    run_shell_commands('apt_remove', apt_remove)

# Check current state of a service
def check_service_state(svc, state):
    if verbose >= 1:
        msg = add_time + color.brown + \
            ' checking service state: {} to ensure its state is: {}' + creset
        print(msg.format(svc, state))
    service_status = 'service ' + svc + ' status'
    if state == 'stopped':
        return run_shell_commands('is_service_down', service_status)
    elif state == 'started':
        return run_shell_commands('is_service_up', service_status)

# enforce the state of the service in reference to policy rule
def enforce_service_state(svc, state):
    # print("managing service: {}, state:{}".format(svc, state))
    if state == 'started':
        state = 'start'
    elif state == 'stopped':
        state = 'stop'
    enforce_status = 'service ' + svc + ' ' + state
    run_shell_commands('enforce_service_state', enforce_status)


# Command function to any system comamnd
def run_shell_commands(call_type, cmd):
    try:
        cmd = list(cmd.split())
        if verbose >= 3:
            print(cmd)
        proc = cli.Popen(
            cmd, stdout=cli.PIPE, stderr=cli.PIPE)
        if call_type == 'check_if_installed':
            is_installed = cli.Popen(
                ["grep", "^ii"], stdin=proc.stdout, stdout=cli.PIPE, stderr=cli.PIPE)
            proc.stdout.close()
            std_out, std_err = is_installed.communicate()
            ret_code = is_installed.returncode
            if verbose >= 3:
                print("InInstalled: \n\tstd_out:{},\n\tstd_err: {},\n\tret_code: {}".format(
                    std_out, std_err, ret_code))
        elif call_type == 'is_service_down':
            not_running = cli.Popen(
                ["egrep", """not running|stop/waiting"""], stdin=proc.stdout, stdout=cli.PIPE, stderr=cli.PIPE)
            proc.stdout.close()
            std_out, std_err = not_running.communicate()
            ret_code = not_running.returncode
            if verbose >= 3:
                print("Is_Service_Down: \n\tstd_out:{},\n\tstd_err: {},\n\tret_code: {}".format(
                    std_out, std_err, ret_code))
        elif call_type == 'is_service_up':
            is_running = cli.Popen(
                ["egrep", """is running|start/running"""], stdin=proc.stdout, stdout=cli.PIPE, stderr=cli.PIPE)
            proc.stdout.close()
            std_out, std_err = is_running.communicate()
            ret_code = is_running.returncode
            if verbose >= 3:
                print("Is_Service_Up: \n\tstd_out:{},\n\tstd_err: {},\n\tret_code: {}".format(
                    std_out, std_err, ret_code))
        else:
            std_out, std_err = proc.communicate()
            ret_code = proc.returncode
            if verbose >= 3:
                print("Basic command without pipe, \n\tstd_out:{},\n\tstd_err: {},\n\tret_code: {}".format(
                    std_out, std_err, ret_code))

        if ret_code == 0:
            return True
        elif ret_code < 0 or ret_code > 0:
            if ignore_true == 'true':
                return False
            else:
                msg = 'Calltype=' + call_type + ' action failed with Exit code=' + \
                    str(ret_code) + '; stdout=' + str(std_out) + \
                    '; stderr=' + str(std_err)
                print(msg)
                sys.exit(ret_code)
    except OSError as e:
        print("Execution failed:{}".format(e))

# Class for ANSI color codes - mainly for beautificaton of print statements to console - STDOUT
class Colors:
    BOLD = '\033[1m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[1;33m'
    FAIL = '\033[91m'
    UNDERLINE = '\033[4m'
    cyan = '\033[0;36m'
    purple = '\033[0;35m'
    brown = '\033[0;33m'
    reset_color = '\033[0m'

# command exception function to tra
def exception():
    formatted_lines = traceback.format_exc().splitlines()
    print(formatted_lines[0])
    print(formatted_lines[-1])


if __name__ == "__main__":
    warnH = '\033[95m' + '\033[1;33m'
    warning = warnH + '## WARNING ##' + '\033[0m' + ' This program is ' + \
        '\033[91m' + 'BETA v0.1' + '\033[0m'\
        ', so please pay attention to your policy rules' + \
        warnH + ' ## WARNING ##' + '\033[0m'
    print(warning)
    answer = input("Do you want to continue [Y/n]: ")
    # answer = 'Y'
    if answer == 'Y':
        main()
    else:
        print("Sorry that you didn't feel comfortable in using this program, probably look at Ansiable (or) Salt (or) Chef (or) Puppet for your configuration management")
