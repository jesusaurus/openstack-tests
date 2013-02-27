import logging
import subprocess
import time

logger = logging.getLogger('nova_test.ping')

def run(servers, **kwargs):
    logger.info('entering ping test')

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
                logger.debug(out)
                times[ip] = count * sleep_time
            else:
                logger.info(out)
                logger.warn(err)
        time.sleep(sleep_time)
        count += 1

    fail = False
    for ip in ips:
        if ip not in times:
            logger.warn("Could not ping {0}.".format(ip))
            fail = True

    if fail:
        raise Exception("Could not ping some servers.")
