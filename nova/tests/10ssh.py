# Copyright 2012-2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import logging
import subprocess as sp
import multiprocessing as mp
from time import sleep
from datetime import datetime
import csv

logger = logging.getLogger('nova_test.ssh')

queue = mp.Queue()
times = mp.Queue()

def ssh(user, host):
    tryLimit = 5
    count = 0
    result = {}
    result['host'] = host
    result[host] = {}
    result[host]['ssh_open'] = datetime.now()
    backoff = 1
    factor = 2
    while count < tryLimit:
        try:
            proc = sp.Popen(['ssh',
                             '-o StrictHostKeyChecking=no',
                             '-o UserKnownHostsFile=/dev/null',
                             '{0}@{1}'.format(user,host),
                             '/bin/true'],
                             stdout=sp.PIPE,
                             stderr=sp.PIPE)
            (out, err) = proc.communicate()
            if proc.returncode is 0:
                result[host]['ssh_close'] = datetime.now()
                result[host]['ssh_total'] = result[host]['ssh_close'] - result[host]['ssh_open']
                times.put(result)
                if out not in [None, ""]:
                    logger.debug(out.strip())
                logger.info("Successful ssh to {0}".format(host))
                break
            else:
                logger.info("Unsuccessful ssh to {0}".format(host))
                if out not in [None, ""]:
                    logger.info(out.strip())
                if err not in [None, ""]:
                    logger.warn(err.strip())
        except Exception as e:
            queue.put(e)
        logger.debug("Sleeping for {0}".format(factor ** backoff))
        sleep(factor ** backoff)
        backoff += 1
        count += 1

    if 'ssh_total' not in result[host]:
        msg = 'Could not ssh to {0}'.format(host)
        logger.error(msg)
        queue.put(Exception(msg))


def run(servers, **kwargs):
    logger.info('Entering ssh test')

    ips = [ servers[x]['ip'] for x in servers.keys() ]
    procs = {}
    for ip in ips:
        procs[ip] = mp.Process(target=ssh, args=('ubuntu', ip))
        procs[ip].start()

    for ip in ips:
        procs[ip].join()

    if not queue.empty():
        logger.error('At least one exception raised, reraising.')
        raise queue.get()

    while not times.empty():
        time = times.get()
        for server in servers.keys():
            if servers[server]['ip'] == time['host']:
                servers[server]['time'].update(time[time['host']])

    with open('ssh.csv', 'w+b') as f:
        output = csv.writer(f)
        output.writerow([ i for i in range(len(servers.keys())) ])
        output.writerow([ servers[x]['time']['ssh_total'].seconds / 60.0 for x in servers.keys() ])
