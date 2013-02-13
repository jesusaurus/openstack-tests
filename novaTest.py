#!/usr/bin/env python

#python libs
import csv
import os
import re
import signal
import sys
from datetime import datetime
from time import sleep

#nova libs
from novaclient import base
from novaclient.exceptions import NotFound as NovaNotFound
from novaclient.v1_1 import client

#cube libs
from cube import Cube


class NovaServiceTest(object):
    '''Class to manage creating and deleting nova instances'''

    def __init__(self, username=None, password=None, tenant=None,
                 auth_url=None, region=None, keypair=None, auth_ver='2.0',
                 count=1, instance_name='NovaServiceTest', debug=False):

        self.username = username
        self.password = password
        self.tenant = tenant
        self.auth_url = auth_url
        self.region = region
        self.keypair = keypair
        self.auth_ver = auth_ver
        self.count = count
        self.test_name = instance_name
        self.debug = debug

        self.nova = None
        self.timeout = 20
        self.server = {}

        self.path = os.path.dirname(__file__)
        if not self.path:
            self.path = '.'


    def connect(self, force=False):
        '''If we haven't already created a nova client, create one.'''
        if self.nova and not force:
            return

        self.nova = client.Client(username=self.username,
                                  api_key=self.password,
                                  project_id=self.tenant,
                                  auth_url=self.auth_url,
                                  region_name=self.region,
                                  service_type="compute")


    def cleanup(self):
        '''Remove any instances with a matching name then exit.'''
        previous = re.compile('^' + self.test_name)
        exit = False
        for _server in self.nova.servers.list():
            if previous.match(_server.name):
                print("\nDetected active instance from another run, deleting")
                self.nova.servers.delete(_server.id)
                exit = True
        if exit:
            self.dieGracefully()


    def set_flavor(self, flavor):
        '''Lookup the specified flavor.'''
        self.flavor = self.nova.flavors.find(name=flavor)


    def set_image(self, image):
        '''Lookup the specified image.'''
        self.image = self.nova.images.find(name=image)


    def create(self):
        '''Create self.count number of instances and time how long it takes.'''
        for i in range(self.count):
            try:
                newserver = self.nova.servers.create(self.test_name + str(i),
                                                     image=self.image,
                                                     flavor=self.flavor,
                                                     key_name=self.keypair)
            except Exception as e:
                print(e)
                self.dieGracefully()

            newid = newserver._info['id']
            self.server[newid] = {}
            self.server[newid]['time'] = {}
            self.server[newid]['time']['create_start'] = datetime.now()
            print("Creating server {0}".format(newid))
            sleep(1) #prevent being rate-limited

        create_list = self.server.keys()
        active_list = []
        backoff = 1
        while create_list:
            for i in create_list:
                try:
                    _server = self.nova.servers.get(i)
                except Exception as e:
                    print(e)
                    self.dieGracefully()

                if _server.status.startswith("BUILD"):
                    pass
                elif _server.status == "ACTIVE":
                    active_list.append(i)
                    create_list.remove(i)
                    self.server[i]['time']['create_end'] = datetime.now()
                    self.server[i]['time']['create_total'] = \
                            self.server[i]['time']['create_end'] - \
                            self.server[i]['time']['create_start']
                    self.server[i]['active'] = True
                    print("Server {0} created".format(i))
                    self.server[i]['ip'] = \
                            _server.addresses['private'][1]['addr']
                    #_server.addresses['public'][0]['addr']
                    #eventually hpcloud will use a version of openstack that
                    #does this right
                elif _server.status.startswith("ERROR"):
                    print("Server {0} status: {1}".format(i, _server.status))
                    self.dieGracefully()
                else:
                    print "Server {0} status: {1}".format(i, _server.status)
                # making nova calls too quickly will get us rate-limited
                sleep(1 * backoff)
                backoff += 1


    def other_tests(self):
        """
        Search the tests/ directory for python modules
        and call the run() function in any modules found.
        """
        print('\nOther Tests...\n')

        test = {}
        tdir = '{0}/{1}'.format(self.path, 'tests')

        if not os.path.isdir(tdir):
            return

        for _file in sorted(os.listdir(tdir)):
            if _file[-3:] == '.py':
                name = _file[:-3]
            else:
                continue

            mod = __import__('tests.' + name, fromlist=[])
            test[name] = mod.__dict__[name]

            if hasattr(test[name], 'run') and callable(test[name].run):
                try:
                    test[name].run(servers=self.server)
                except Exception as e:
                    print(e)
                    self.dieGracefully()


    def delete(self):
        '''
        Wait for each instance to die, and record how long it takes
        Then calculate the total lifespan of the instance.
        '''
        print("\nWaiting for instances to die.")

        deletestart = datetime.now()
        self.deleteAll()

        backoff = 1
        while [ x for x in self.server.keys() \
                if self.server[x]['active'] ]:
            for i in [ x for x in self.server.keys() \
                       if self.server[x]['active'] ]:
                try:
                    _server = self.nova.servers.get(i)
                except NovaNotFound as e:
                    # Server no longer exists
                    self.server[i]['time']['delete_end'] = datetime.now()
                    self.server[i]['time']['delete_total'] = \
                            self.server[i]['time']['delete_end'] - deletestart
                    lifespan = self.server[i]['time']['create_total'] + \
                            self.server[i]['time']['delete_total']
                    self.server[i]['time']['lifespan'] = lifespan
                    self.server[i]['active'] = False
                    print("Server {0} has died".format(i))
                    sys.stdout.flush()
                except Exception as e:
                    print(e)
                    self.dieGracefully()
                else:
                    if _server.status.startswith("ERROR"):
                        print("\nServer {0} has entered an error state"
                                .format(i))
                        self.dieGracefully()
                sleep(1 * backoff) # prevent rate-limiting
                backoff += 1


    def results(self):
        '''Print out some results and calculate the min/max/mean'''
        csvfiles = {
                'create': '{0}/results/creation.csv'.format(self.path),
                'delete': '{0}/results/deletion.csv'.format(self.path),
                'life':  '{0}/results/lifespan.csv'.format(self.path),
                }
        if not os.path.isdir('{0}/results'.format(self.path)):
            os.makedirs('{0}/results'.format(self.path))

        data_cube = Cube(hostname="15.185.114.206")
        cube_data = {}
        cube_data['create_total'] = []
        cube_data['delete_total'] = []
        cube_data['total'] = []
        az = self.region.split('.')[0]

        for i in self.server.keys():
            data = {}
            t = self.server[i]['time']
            print("\nServer ID: {0}".format(i))
            for k,v in t.items():
                print("{0}: {1}".format(k, v))
                if k == 'lifespan':
                    try:
                        if minlife > v:
                            minlife = v
                    except NameError:
                        minlife = v
                    try:
                        if not maxlife or maxlife < v:
                            maxlife = v
                    except NameError:
                        maxlife = v
                    try:
                        sumlife += v
                    except NameError:
                        sumlife = v
                    data['total'] = v.seconds / 60.0
                elif k == 'create_total':
                    data['create_total'] = v.seconds / 60.0
                elif k == 'delete_total':
                    data['delete_total'] = v.seconds / 60.0
            cube_data['create_total'].append(data['create_total'])
            cube_data['delete_total'].append(data['delete_total'])
            cube_data['total'].append(data['total'])
        data_cube.put("server_timing", ({'az': az}, {'times': cube_data}))
        meanlife = sumlife / self.count

        mintime = minlife.seconds / 60.0
        maxtime = maxlife.seconds / 60.0
        meantime = meanlife.seconds / 60.0

        print("\n\nmin lifespan: {0} ({1})".format(str(minlife), mintime))
        print("max lifespan: {0} ({1})".format(str(maxlife), maxtime))
        print("mean lifetime: {0} ({1})".format(str(meanlife), meantime))

        with open(csvfiles['life'], 'w+b') as f:
            output = csv.writer(f)
            output.writerow(['Shortest Lifespan',
                             'Longest Lifespan',
                             'Mean Lifespan'])
            output.writerow([mintime, maxtime, meantime])
        with open(csvfiles['create'], 'w+b') as f:
            output = csv.writer(f)
            output.writerow([i for i in range(self.count)])
            output.writerow([self.server[i]['time']['create_total'].seconds /
                             60.0 for i in self.server.keys()])
        with open(csvfiles['delete'], 'w+b') as f:
            output = csv.writer(f)
            output.writerow([i for i in range(self.count)])
            output.writerow([self.server[i]['time']['delete_total'].seconds /
                             60.0 for i in self.server.keys()])


    def dieGracefully(self, code=-1):
        self.deleteAll()
        sys.exit(code)


    def deleteAll(self):
        for i in self.server.keys():
            self.nova.servers.delete(i)

if __name__ == "__main__":

    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    tenant = os.environ['OS_TENANT_NAME']
    auth_url = os.environ['OS_AUTH_URL']
    region = os.environ['OS_REGION_NAME']
    keypair = os.environ['OS_KEYPAIR']

    count = 20
    if 'NOVA_INSTANCE_COUNT' in os.environ:
        count = int(os.environ['NOVA_INSTANCE_COUNT'])

    name = 'nova_test'
    if 'NOVA_NAME' in os.environ:
        name = os.environ['NOVA_NAME']

    nova_test = NovaServiceTest(username=username, password=password,
                                tenant=tenant, auth_url=auth_url,
                                region=region, keypair=keypair,
                                instance_name=name, count=count, debug=True)

    def signal_handler(signal, frame):
        '''Trap SIGINT'''
        nova_test.dieGracefully()
    signal.signal(signal.SIGINT, signal_handler)

    def alarm_handler(signum, frame):
        '''Trap SIGALRM'''
        print("Maximum lifespan greater than {0}".format(hardLimit))
        nova_test.dieGracefully()
    signal.signal(signal.SIGALRM, alarm_handler)

    nova_test.connect()
    nova_test.cleanup()

    print("reticulating splines")
    nova_test.set_flavor('standard.xsmall')
    nova_test.set_image('Ubuntu Precise 12.04 LTS Server 64-bit 20121026 (b)')

    signal.alarm(nova_test.timeout*60)
    nova_test.create()
    signal.alarm(0)

    nova_test.other_tests()

    signal.alarm(nova_test.timeout*60)
    nova_test.delete()
    signal.alarm(0)

    nova_test.results()

