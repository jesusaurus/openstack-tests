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
import subprocess
import time

logger = logging.getLogger('nova_test.ping')

def run(servers, **kwargs):
    logger.info('Entering ping test')

    times = {}
    count = 1
    max_count = 20
    sleep_time = 3
    ips = [ servers[x]['ip'] for x in servers.keys() ]

    while count < max_count:
        procs = {}
        for ip in ips:
            if ip not in times:
                procs[ip] = subprocess.Popen(['ping', '-q', '-n', '-c 3', ip],
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE)
        for ip, proc in procs.iteritems():
            (out, err) = proc.communicate()
            if proc.returncode is 0:
                logger.info('Successful ping: {0}'.format(ip))
                logger.debug(out.strip())
                times[ip] = count * sleep_time
            else:
                logger.warn(out.strip())
                logger.warn(err.strip())
        time.sleep(sleep_time)
        count += 1

    fail = False
    for ip in ips:
        if ip not in times:
            logger.warn("Could not ping {0}.".format(ip))
            fail = True

    if fail:
        raise Exception("Could not ping some servers.")
