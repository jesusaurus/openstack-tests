#!/usr/bin/env python

#python libs
import os
import csv
import hashlib
from datetime import datetime

#swift libs
from swiftclient import client as swift

class SwiftServiceTest(object):

    def __init__(self, username=None, password=None, tenant=None,
                 auth_url=None, auth_ver='2.0', swift_url=None, debug=False):

        self.username = username
        self.password = password
        self.tenant = tenant
        self.auth_url = auth_url
        self.swift_url = swift_url
        self.auth_ver = auth_ver
        self.debug = debug
        self.token = None
        self.http_conn = None


    def connect(self, force=False):
        if self.http_conn is not None and not force:
            return

        swift_url, self.token = swift.get_auth(auth_url=self.auth_url,
                                               user=self.username,
                                               key=self.password,
                                               auth_version=self.auth_ver,
                                               tenant_name=self.tenant)
        if self.debug:
            print(self.auth_url)
            print(self.token)
            print(self.swift_url)
            print(swift_url)
            print
        if not swift_url == self.swift_url:
            print("Different swift_url returned from swift")

        self.http_conn = swift.http_connection(self.swift_url)

        if self.debug:
            print(self.http_conn)
            print


    def get_account(self, deep=True):
        if not self.http_conn:
            self.connect()

        account_info = swift.head_account(url=self.swift_url,
                                          token=self.token,
                                          http_conn=self.http_conn)
        account_head, containers = swift.get_account(url=self.swift_url,
                                                     token=self.token,
                                                     http_conn=self.http_conn)
        if self.debug:
            print(account_info)
            print(account_head)
            for container in containers:
                print(container)
            print

        if deep:
            self.get_containers(containers)


    def get_containers(self, containers):
        for container in containers:
            info, objects = swift.get_container(url=self.swift_url,
                                                token=self.token,
                                                http_conn=self.http_conn,
                                                container=container['name'])
            if self.debug:
                print(container['name'])
                print(info)
                for obj in objects:
                    print(obj)
                print


    def create_container(self, name, headers=None):
        if not self.http_conn:
            self.connect()

        swift.put_container(url=self.swift_url, token=self.token,
                            http_conn=self.http_conn, container=name,
                            headers=headers)
        if self.debug:
            print("Container {0} created".format(name))


    def find_container(self, name):
        if not self.http_conn:
            self.connect()

        retval = swift.get_container(url=self.swift_url, token=self.token,
                                     http_conn=self.http_conn, container=name)
        if self.debug:
            print(retval)
        return retval


    def modify_container(self, name, headers):
        if not self.http_conn:
            self.connect()

        swift.post_container(url=self.swift_url, token=self.token,
                             http_conn=self.http_conn, container=name,
                             headers=headers)
        if self.debug:
            print("Container {0} modified".format(name))


    def delete_container(self, name):
        if not self.http_conn:
            self.connect()

        swift.delete_container(url=self.swift_url, token=self.token,
                               http_conn=self.http_conn, container=name)
        if self.debug:
            print("Container {0} deleted".format(name))


    def create_object(self, cname, oname, contents, length=None):
        swift.put_object(url=self.swift_url, token=self.token,
                         http_conn=self.http_conn, container=cname,
                         name=oname, contents=contents, content_length=length)


    def get_object(self, cname, oname):
        return swift.get_object(url=self.swift_url, token=self.token,
                                http_conn=self.http_conn, container=cname,
                                name=oname)


    def delete_object(self, cname, oname):
        swift.delete_object(url=self.swift_url, token=self.token,
                            http_conn=self.http_conn, container=cname,
                            name=oname)


    def test_api(self, test_name):
        print("Checking API")
        self.connect()
        self.get_account()

        self.create_container(test_name,
                              headers={'X-Container-Meta-Foo': 'Foo'})
        self.get_account()

        self.modify_container(test_name,
                              headers={'X-Container-Meta-Foo': 'Bar'})
        self.get_account()

        self.find_container(test_name)
        self.get_account()

        self.delete_container(test_name)
        self.get_account()


    def stress_test(self, test_name, count=10, size=2**20):
        print("Creating and deleting {0} containers".format(count))

        self.connect()

        start = datetime.now()
        with open('/dev/urandom') as dev_rand:
            for i in range(count):
                name = '{0}{1}'.format(test_name,i)
                self.create_container(name)
                for i in range(count):
                    obj = 'obj{0}'.format(i)
                    if self.debug:
                        print(name,obj)
                    contents = dev_rand.read(size)
                    sha = hashlib.sha1(contents).hexdigest()
                    header='X-Container-Meta-{0}'.format(obj)
                    headers={header: sha}
                    self.create_object(cname=name, oname=obj,
                                       contents=contents, length=size)
                    self.modify_container(name=name, headers=headers)
        create_time = datetime.now() - start

        self.get_account()

        start = datetime.now()
        for i in range(count):
            name = '{0}{1}'.format(test_name,i)
            cont = self.find_container(name)
            for i in range(count):
                obj = 'obj{0}'.format(i)
                headers, contents = self.get_object(cname=name, oname=obj)
                sha = hashlib.sha1(contents).hexdigest()
                header = 'x-container-meta-{0}'.format(obj)
                if cont[0][header] != sha:
                    print
                    print('Bad SHA')
                    print
                    raise ValueError
                self.delete_object(cname=name, oname=obj)
            self.delete_container(name)
        delete_time = datetime.now() - start

        name = 'stress-{0}-{1}-{2}-times.csv'.format(test_name, count, size)
        with open(name, 'w+b') as csvfile:
            output = csv.writer(csvfile)
            output.writerow(['Create time', 'Delete time'])
            output.writerow([create_time.seconds / 60.0,
                             delete_time.seconds / 60.0])


    def test_suite(self, test_name):
        self.test_api(test_name)
        self.stress_test(test_name)


if __name__ == '__main__':
    from optparse import OptionParser
    op = OptionParser()
    op.add_option('-a', '--api', action='store_true', dest='api',
                  default=False, help="Turn on basic api checking.")
    op.add_option('-s', '--stress', action='store_true', dest='stress',
                  default=False, help="Turn on stress testing.")
    op.add_option('-n', '--name', dest='name', default="swift_test",
                  help="Name to prepend to containers")
    op.add_option('--stress-count', dest='count', default=10, type=int,
                  help="Number of containers and objects-per-container.")
    op.add_option('--stress-size', dest='size', default=2**20, type=int,
                  help="Size (in bytes) of each object created")
    options, args = op.parse_args()

    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    tenant = os.environ['OS_TENANT_NAME']
    auth_url = os.environ['OS_AUTH_URL']
    swift_url = os.environ['OS_OBJECT_URL']

    sst = SwiftServiceTest(username=username, password=password, tenant=tenant,
                           auth_url=auth_url, swift_url=swift_url, debug=True)
    sst.connect()

    if options.api:
        sst.test_api(test_name=options.name)

    if options.stress:
        sst.stress_test(test_name=options.name, count=options.count,
                     size=options.size)

    if not (options.api or options.stress):
        print("No tests set to be run")
