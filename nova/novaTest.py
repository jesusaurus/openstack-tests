#!/usr/bin/env python

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

#python libs
import csv
import logging
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


logging.basicConfig(format='%(levelname)s\t%(name)s\t%(message)s')

requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

logger = logging.getLogger('nova_test')
logger.setLevel(logging.INFO)

class NovaServiceTest(object):
    '''Class to manage creating and deleting nova instances'''

    def __init__(self, username=None, password=None, tenant=None,
                 auth_url=None, region=None, keypair=None, auth_ver='2.0',
                 count=1, instance_name='NovaServiceTest', timeout=20):

        self.username = username
        self.password = password
        self.tenant = tenant
        self.auth_url = auth_url
        self.region = region
        self.keypair = keypair
        self.auth_ver = auth_ver
        self.count = count
        self.test_name = instance_name
        self.timeout = timeout

        self.nova = None
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
                logger.warning("Detected active instance from another run, deleting")
                self.server[_server.id] = {}
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
                logger.exception("Could not create server.")
                self.dieGracefully(msg='Failed to create servers.')

            newid = newserver._info['id']
            self.server[newid] = {}
            self.server[newid]['time'] = {}
            self.server[newid]['time']['create_start'] = datetime.now()
            logger.info("Creating server {0}".format(newid))
            sleep(1) #prevent being rate-limited

        create_list = self.server.keys()
        backoff = 1
        while create_list:
            for i in create_list:
                try:
                    _server = self.nova.servers.get(i)
                except Exception as e:
                    logger.exception("Could not get server info.")
                    self.dieGracefully()

                if _server.status.startswith("BUILD"):
                    pass
                elif _server.status == "ACTIVE":
                    create_list.remove(i)
                    self.server[i]['time']['create_end'] = datetime.now()
                    self.server[i]['time']['create_total'] = \
                            self.server[i]['time']['create_end'] - \
                            self.server[i]['time']['create_start']
                    self.server[i]['active'] = True
                    logger.info("Server {0} created".format(i))
                    self.server[i]['ip'] = \
                            _server.addresses['private'][1]['addr']
                    #_server.addresses['public'][0]['addr']
                    #eventually hpcloud will use a version of openstack that
                    #does this right
                elif _server.status.startswith("ERROR"):
                    logger.error("Server {0} status: {1}".format(i, _server.status))
                    self.dieGracefully()
                else:
                    logger.warn("Server {0} status: {1}".format(i, _server.status))
                # making nova calls too quickly will get us rate-limited
                sleep(1 * backoff)
                backoff += 1


    def other_tests(self):
        """
        Search the tests/ directory for python modules
        and call the run() function in any modules found.
        """
        logger.info('Running modules in tests/ directory.')

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
                    logger.exception("Test module failed.")
                    self.dieGracefully()


    def delete(self):
        '''
        Wait for each instance to die, and record how long it takes
        Then calculate the total lifespan of the instance.
        '''
        logger.info("Waiting for instances to die.")

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
                    logger.info("Server {0} has died".format(i))
                    sys.stdout.flush()
                except Exception as e:
                    logger.exception("Unknown exception")
                    self.dieGracefully()
                else:
                    if _server.status.startswith("ERROR"):
                        logger.error("Server {0} has entered an error state".format(i))
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

        for i in self.server.keys():
            data = {}
            t = self.server[i]['time']
            logger.debug("Server ID: {0}".format(i))
            for k,v in t.items():
                logger.debug("{0}: {1}".format(k, v))
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
        meanlife = sumlife / self.count

        mintime = minlife.seconds / 60.0
        maxtime = maxlife.seconds / 60.0
        meantime = meanlife.seconds / 60.0

        logger.info("min lifespan: {0} ({1})".format(str(minlife), mintime))
        logger.info("max lifespan: {0} ({1})".format(str(maxlife), maxtime))
        logger.info("mean lifetime: {0} ({1})".format(str(meanlife), meantime))

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


    def dieGracefully(self, code=-1, msg=None):
        self.deleteAll()
        if msg:
            print(msg)
        sys.exit(code)


    def deleteAll(self):
        exc_list = []

        for i in self.server.keys():
            try:
                logger.info('Deleting server: {0}'.format(i))
                self.nova.servers.delete(i)
            except Exception as e:
                logger.exception('Encountered an Exception: {0}'.format(e))
                exc_list.append(e)

        if exc_list:
            logger.warn('Raising encountered exceptions.')
            for e in exc_list:
                raise e

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

    from optparse import OptionParser
    op = OptionParser()
    op.add_option('-l', '--log-level', dest='log_level', type=str,
                  default='info', help='Logging output level.')
    op.add_option('-t', '--timeout', dest='timeout', type=int,
                  default=20, help='Timeout (in minutes) for creating or '
                  'deleting instances')
    options, args = op.parse_args()

    if options.log_level.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR',
                                     'CRITICAL']:
        logger.setLevel(getattr(logging, options.log_level.upper()))

    nova_test = NovaServiceTest(username=username, password=password,
                                tenant=tenant, auth_url=auth_url,
                                region=region, keypair=keypair,
                                instance_name=name, count=count,
                                timeout=options.timeout)

    def signal_handler(signal, frame):
        '''Trap SIGINT'''
        nova_test.dieGracefully(msg='Received SIGINT')
    signal.signal(signal.SIGINT, signal_handler)

    def alarm_handler(signum, frame):
        '''Trap SIGALRM'''
        logger.error("Maximum lifespan greater than {0}".format(nova_test.timeout))
        nova_test.dieGracefully()
    signal.signal(signal.SIGALRM, alarm_handler)

    nova_test.connect()
    nova_test.cleanup()

    logger.info("reticulating splines")
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

