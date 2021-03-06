#!/usr/bin/python3
# Developed by Alexander Bersenev from Hackerdom team, bay@hackerdom.ru

"""Cloud state checker.

Checks if the vm state in db consistent with an actual state

Recomended to be used by cloud administrators only
"""

import sys
import os
import traceback
import time
import glob
import re
import subprocess
from multiprocessing import Pool

from cloud_common import (get_cloud_ip, log_progress,
                          call_unitl_zero_exit, SSH_CLOUD_OPTS, get_available_vms)

CLOUD_VBOXNAME_RE = r"(\d+)_(.*?)_team([0-9]+)"
THREAD_POOL_SIZE = 64


def log_stderr(*params):
    print(*params, file=sys.stderr)


def log_team(team, *params):
    log_stderr("team %d:" % team, *params)


def get_image_states():
    image_states = {}

    for filename in os.listdir("db"):
        m = re.fullmatch(r"team([0-9]+)", filename)
        if not m:
            continue
        team = int(m.group(1))
        try:
            for vm, vmnum in get_available_vms().items():
                image_state = open("db/%s/serv%d_image_deploy_state" %
                                   (filename, vmnum)).read().strip()
                if team not in image_states:
                    image_states[team] = {}
                image_states[team][vmnum] = image_state
        except FileNotFoundError:
            log_team(team, "failed to load states")
    return image_states


def get_cloud_ips():
    cloud_ips = {}

    for filename in os.listdir("db"):
        m = re.fullmatch(r"team([0-9]+)", filename)
        if not m:
            continue
        team = int(m.group(1))

        try:
            cloud_ip = open("db/%s/cloud_ip" % (filename)).read().strip()
            cloud_ips[team] = cloud_ip

        except FileNotFoundError:
            # it is ok, for undeployed VMs
            pass
    return cloud_ips


def get_vms_on_cloud_ip(cloud_ip):
    try:
        cmd = ["sudo", "/cloud/scripts/list_vms.sh"]
        output = subprocess.check_output(["ssh"] + SSH_CLOUD_OPTS +
                                         [cloud_ip] + cmd).decode("utf-8")

        teams = [[int(team), int(serv_num), serv_name]
                 for serv_num, serv_name, team in re.findall(CLOUD_VBOXNAME_RE, output)]
    except subprocess.CalledProcessError:
        teams = []

    return teams


def get_running_vms_on_cloud_ip(cloud_ip):
    try:
        cmd = ["sudo", "/cloud/scripts/list_vms.sh running"]
        output = subprocess.check_output(["ssh"] + SSH_CLOUD_OPTS +
                                         [cloud_ip] + cmd).decode("utf-8")

        teams = [[int(team), int(serv_num), serv_name]
                 for serv_num, serv_name, team in re.findall(CLOUD_VBOXNAME_RE, output)]
    except subprocess.CalledProcessError:
        teams = []

    return teams


def main():
    image_states = get_image_states()
    cloud_ips = get_cloud_ips()
    print(cloud_ips)
    # cloud_ips = {"cld1": "10.60.1.253"}

    teams = list(image_states.keys())

    p = Pool(THREAD_POOL_SIZE)

    cloud_ip_to_vms = dict(zip(cloud_ips.values(),
                           p.map(get_vms_on_cloud_ip, cloud_ips.values())))

    cloud_ip_to_running_vms = dict(zip(cloud_ips.values(),
                                   p.map(get_running_vms_on_cloud_ip, cloud_ips.values())))

    for team in teams:
        if team not in cloud_ips:
            log_team(team, "vm has no cloud_ip")

        for vm, vmnum in get_available_vms().items():
            if image_states[team][vmnum] == "NOT_STARTED":
                for cloud_ip in set(cloud_ips.values()):
                    if [team, vmnum, vm] in cloud_ip_to_running_vms[cloud_ip]:
                        log_team(team, "image state is NOT_STARTED but there is a running vm on " +
                                       "%s for service %d %s " % (cloud_ip, vmnum, vm))
                    elif [team, vmnum, vm] in cloud_ip_to_vms[cloud_ip]:
                        log_team(team, "image state is NOT_STARTED but there is a vm on " +
                                       "%s for service %d %s" % (cloud_ip, vmnum, vm))

            if image_states[team][vmnum] == "RUNNING":
                cloud_ip = None
                if team not in cloud_ips:
                    log_team(team, "image state is RUNNING, but vm has no cloud_ip")
                else:
                    cloud_ip = cloud_ips[team]
                    if [team, vmnum, vm] not in cloud_ip_to_running_vms[cloud_ip]:
                        log_team(team, "image state is RUNNING but there is no running vm on " +
                                       "%s for service %d %s" % (cloud_ip, vmnum, vm))
                    elif [team, vmnum, vm] not in cloud_ip_to_vms[cloud_ip]:
                        log_team(team, "image state is RUNNING but there is no vm on " +
                                       "%s for service %d %s" % (cloud_ip, vmnum, vm))

                for check_cloud_ip in set(cloud_ips.values()):
                    if check_cloud_ip == cloud_ip:
                        continue

                    if [team, vmnum, vm] in cloud_ip_to_vms[check_cloud_ip]:
                        log_team(team, "image state is RUNNING but there another vm on " +
                                       "%s for service %d %s" % (check_cloud_ip, vmnum, vm))
                    elif [team, vmnum, vm] in cloud_ip_to_running_vms[check_cloud_ip]:
                        log_team(team, "image state is RUNNING but there another running vm on " +
                                       "%s for service %d %s" % (check_cloud_ip, vmnum, vm))

    for ip, desc in cloud_ip_to_running_vms.items():
        for team, vmnum, vm in desc:
            if team not in teams:
                log_team(team, "lost running vm, no such team for service %d %s" % (vmnum, vm))
            if vm not in get_available_vms() or get_available_vms()[vm] != vmnum:
                log_team(team, "lost running vm, no such service %d %s" % (vmnum, vm))

    for ip, desc in cloud_ip_to_vms.items():
        for team, vmnum, vm in desc:
            if team not in teams:
                log_team(team, "lost vm, no such team for service %d %s" % (vmnum, vm))
            if vm not in get_available_vms() or get_available_vms()[vm] != vmnum:
                log_team(team, "lost vm, no such service %d %s" % (vmnum, vm))

    return 0


if __name__ == "__main__":
    sys.stdout = os.fdopen(1, 'w', 1)
    print("started: %d" % time.time())
    exitcode = 1
    try:
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        exitcode = main()
    except Exception:
        traceback.print_exc()
    print("exit_code: %d" % exitcode)
    print("finished: %d" % time.time())
