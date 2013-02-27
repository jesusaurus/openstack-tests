import subprocess as sp
import multiprocessing as mp
from time import sleep
from datetime import datetime
import csv

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
                break
        except Exception as e:
            queue.put(e)
        sleep(factor * backoff)
        backoff += 1
        count += 1


def run(servers, **kwargs):
    print('ssh test')

    ips = [ servers[x]['ip'] for x in servers.keys() ]
    procs = {}
    for ip in ips:
        procs[ip] = mp.Process(target=ssh, args=('root', ip))
        procs[ip].start()

    for ip in ips:
        procs[ip].join()

    if not queue.empty():
        print('At least one exception raised, reraising.')
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
