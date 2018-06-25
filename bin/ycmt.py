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
from slackclient import SlackClient as slk
from shutil import copyfile as cpfile
import pwd
import grp

cwd = os.path.dirname(os.path.realpath(__file__))

full_hostname = hostname()
short_hostname = full_hostname.split('.')[0]

source_dir = cwd.strip('bin')
conf_dir = source_dir + 'conf/'
ignore_true = 'true'

# Main Program


def main():
    global verbose, color, warnH, failH, fail, creset, header, add_time
    arg_parser = argparse.ArgumentParser(description='Yet(another)ConfigurationManagementTool - ycmt to deploy and configure simple services \
                                     and if deployment is success send message to SLACK channel')
    arg_parser.add_argument(
        '--verbose', '-v', help='increase output verbosity, for more verbosity use -vv', action='count', default=0)
    arg_parser.add_argument('--conf', '-c', action="store", default=conf_dir + "default.json",
                            help="path to config file. Default: ./conf/default.json")

    args = arg_parser.parse_args()
    verbose = args.verbose
    color = Colors()
    warnH = color.BOLD + color.WARNING
    failH = color.BOLD + color.FAIL
    fail = color.FAIL
    creset = color.reset_color
    header = color.BOLD + color.OKBLUE

    # calculate the offset taking into account daylight saving time
    utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
    utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
    current_time = datetime.datetime.now().replace(
        tzinfo=datetime.timezone(offset=utc_offset), microsecond=0).isoformat()

    add_time = color.UNDERLINE + color.purple + current_time + creset
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
        if base_policy:
            print(
                header + "## Applying Base Policies of Package Manager, Services, Configs ##"+creset)
            manage_packages('base', base_policy['packages'])
            manage_services('base', base_policy['services'])
            manage_configs('base', base_policy['configs'])
        if host_policy:
            print(
                header+"## Applying Host Policies of Package Manager, Services, Conigs ##"+creset)
            manage_packages('host', host_policy['packages'])
            manage_services('host', host_policy['services'])
            manage_configs('host', host_policy['configs'])
    except:
        exception()


def manage_packages(policy, rules):
    policy_msg = color.UNDERLINE + color.BOLD + policy.upper() + creset
    if rules['install'] and len(rules['install']) != 0:
        msg = add_time + " checking compliance of package install rules of " + policy_msg + " on this host: " + \
            color.brown + color.BOLD + full_hostname + creset
        print(msg)
        for pkg in rules['install']:
            # for now we install latest availabe version in the apt repo
            # future release will support specific version of pkg that can be installed
            if not check_if_installed(pkg):
                msg = color.brown + color.UNDERLINE + pkg + creset
                print(add_time + " {} - package not found, so installing it".format(msg))
                apt_install(pkg)
            else:
                msg = add_time + color.OKGREEN + ' Skipping..' + pkg + \
                    creset + ' package install as its installed and in compliance with above policy rule.'
                print(msg)
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
    policy_msg = color.UNDERLINE + color.BOLD + policy.upper() + creset
    msg = add_time + " checking compliance of manage_services rules of " + policy_msg + \
        " on this host: " + color.brown + color.BOLD + full_hostname + creset
    print(msg)
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
                else:
                    msg = add_time + color.OKGREEN + ' Skipping..' + creset + policy_msg + ' policy rule enforces service: ' + color.brown + svc + creset + ' state to be ' + \
                        header + state.upper() + creset + \
                        ' and it appears all compliance for the policy rule are met.'
                    print(msg)

            elif state is 'reloaded':
                enforce_service_state(svc, 'reload')
            else:
                msg = header + 'This state is not implemented, please check the release version in future' + creset
                print(msg)


def manage_configs(policy, rules):
    policy_msg = color.UNDERLINE + color.BOLD + policy.upper() + creset
    msg = add_time + " checking compliance of manage_configs rules of " + policy_msg + \
        " on this host: " + color.brown + color.BOLD + full_hostname + creset
    print(msg)
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
                        check_file_stat(
                            rules[file]['dest'], rules[file]['user'], rules[file]['group'], rules[file]['mode'])
                    else:
                        sync_notify(source, rules[file])
                        msg = add_time + color.OKGREEN + ' Copying..' + \
                            rules[file]['dest'] + creset + \
                            ' content changed in source ' + color.UNDERLINE + source + creset + \
                            ' change, so everything is in compliance with above policy rule.'
                        print(msg)

                else:
                    sync_notify(source, rules[file])
                    msg = add_time + color.OKGREEN + ' Copying..' + \
                        rules[file]['dest'] + creset + \
                        ' file as its not found to meet compliance with above policy rule.'
                    print(msg)

            elif rules[file]['action'] == 'delete':
                if os.path.isfile(rules[file]['dest']):
                    os.remove(rules[file]['dest'])
                    msg = add_time + color.FAIL + ' Policy ENFORCED..' + rules[file]['dest'] + \
                        creset + ' file deleted as per compliance with above policy rule.'
                    print(msg)
                else:
                    msg = add_time + color.OKGREEN + ' Skipping..' + rules[file]['dest'] + \
                        creset + ' file deletion as everything is in compliance with above policy rule.'
                    print(msg)
        except:
            exception()


def check_file_stat(file, user, group, mode):
    file_stat_info = os.stat(file)
    cmode = oct(file_stat_info[0])[-5:]
    uuid = file_stat_info[4]
    guid = file_stat_info[5]
    cuser = pwd.getpwuid(uuid)[0]
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
                creset
            print(msg)
        else:
            msg = add_time + ' Ownership Update is: ' + failH + 'UNSUCCESS' + \
                creset
            print(msg)

    else:
        msg = add_time + color.OKGREEN + ' Skipping..' + \
            file + creset + \
            ' Ownership as it is as per compliance with above policy rule.'
        print(msg)
        if verbose >= 3:
            print("current mode:{}, policy mode:{}".format(cmode, mode))
    if cmode != mode:
        msg = add_time + ' current file permission mode: ' + failH + mode + creset + ', excpected file permission mode: ' + color.OKGREEN + mode + \
            creset + creset + ' ,so applied changes as per compliance with above policy rule'
        cmd = 'chmod ' + mode + ' ' + file
        if run_shell_commands('change_file_permissions', cmd):
            msg = add_time + ' Permission Mode Update is: ' + color.OKGREEN + 'SUCCESS' + \
                creset
            print(msg)
        else:
            msg = add_time + ' Permission Mode Update is: ' + failH + 'UNSUCCESS' + \
                creset
            print(msg)

    else:
        msg = add_time + color.OKGREEN + ' Skipping..' + \
            file + creset + \
            ' Permissions as it is as per compliance with above policy rule.'
        print(msg)


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
        print(msg+'{}, action: {}'.format(svc, action))
        notify_service(svc, action)


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


# Function to any system comamnd


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
                print_logger(msg)
                sys.exit(ret_code)
    except OSError as e:
        print("Execution failed:{}".format(e))

# Print and log


def print_logger(msg):
    print(msg)


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


def exception():
    print(traceback.format_exc())


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
