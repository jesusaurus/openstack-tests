import subprocess


def run(servers, **kwargs):
    print('ping test')
    for ip in [ servers[x]['ip'] for x in servers.keys() ]:
        try:
            subprocess.check_call(['ping', '-c 3', ip])
        except Exception as e:
            print(e)
        else:
            print("ping successful")

