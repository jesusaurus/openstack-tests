import subprocess
import time

def run(servers, **kwargs):
    print('ping test')

    times = {}
    count = 1
    max_count = 30
    sleep_time = 1
    ips = [ servers[x]['ip'] for x in servers.keys() ]

    while count < max_count:
        procs = []
        for ip in ips:
            if ip not in times:
                procs.append(subprocess.Popen(['ping', '-c 1', ip],
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE))
        for proc in procs:
            proc.communicate()
            if proc.returncode is 0:
                print("ping successful: {0}".format(ip))
                times[ip] = count * sleep_time
        time.sleep(sleep_time)
        count += 1

    for ip in ips:
        if ip not in times:
            raise Exception("Could not ping {0}".format(ip))
