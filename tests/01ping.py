import subprocess
import time

def run(servers, **kwargs):
    print('ping test')

    times = {}
    count = 1
    max_count = 10
    sleep_time = 3
    ips = [ servers[x]['ip'] for x in servers.keys() ]

    while count < max_count:
        procs = {}
        for ip in ips:
            if ip not in times:
                procs[ip] = subprocess.Popen(['ping', '-c 1', ip],
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE)
        for ip, proc in procs.iteritems():
            print(ip)
            (out, err) = proc.communicate()
            if proc.returncode is 0:
                print(out)
                times[ip] = count * sleep_time
            else:
                print(out)
                print(err)
        time.sleep(sleep_time)
        count += 1

    fail = False
    for ip in ips:
        if ip not in times:
            print("Could not ping {0}.".format(ip))
            fail = True

    if fail:
        raise Exception("Could not ping some servers.")
