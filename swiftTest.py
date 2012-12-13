#!/usr/bin/env python

#python libs
import os

#swift libs
from swiftclient import client as swift

class SwiftServiceTest(object):

    def __init__(self, username=None, password=None, tenant=None, auth_url=None,
               auth_ver='2.0', swift_url=None, debug=False):

        self.auth_ver = auth_ver
        self.debug = debug
        self.token = None
        self.http_conn = None

        def _default(var, env):
            if var:
                return var
            if env in os.environ:
                return os.environ[env]
            return None

        self.username = _default(username, 'OS_USERNAME')
        self.password = _default(password, 'OS_PASSWORD')
        self.tenant = _default(tenant, 'OS_TENANT_NAME')
        self.auth_url = _default(auth_url, 'OS_AUTH_URL')
        self.swift_url = _default(swift_url, 'OS_OBJECT_URL')


    def connect(self, force=False):
        if self.http_conn is not None and not force:
            return

        swift_url, self.token = swift.get_auth(auth_url=self.auth_url,
                                              user=self.username,
                                              key=self.password,
                                              auth_version=self.auth_ver,
                                              tenant_name=self.tenant)
        if not swift_url == self.swift_url:
            print("Different swift_url returned from swift")
        if self.debug:
            print(self.auth_url)
            print(self.token)
            print(self.swift_url)
            print(swift_url)
            print

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
        if not account_info == account_head:
            print("Different account info returned")
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


    def delete_object(self, cname, oname):
        swift.delete_object(url=self.swift_url, token=self.token,
                            http_conn=self.http_conn, container=cname,
                            name=oname)


    def test_api(self, test_name):
        print("Checking API")
        self.connect()
        self.get_account()

        self.create_container(test_name, headers={'X-Container-Meta-Foo': 'Foo'})
        self.get_account()

        self.modify_container(test_name, headers={'X-Container-Meta-Foo': 'Bar'})
        self.get_account()

        self.find_container(test_name)
        self.get_account()

        self.delete_container(test_name)
        self.get_account()


    def stress_test(self, test_name, count=10, size=2**20):
        print("Creating and deleting {0} containers".format(count))
        self.connect()

        with open('/dev/urandom') as dev_rand:
            for i in range(count):
                name = '{0}{1}'.format(test_name,i)
                self.create_container(name)
                for i in range(count):
                    obj = 'obj{0}'.format(i)
                    print(name,obj)
                    self.create_object(cname=name, oname=obj,
                                       contents=dev_rand, length=size)

        self.get_account()

        for i in range(count):
            name = '{0}{1}'.format(test_name,i)
            for i in range(count):
                obj = 'obj{0}'.format(i)
                self.delete_object(cname=name, oname=obj)
            self.delete_container(name)


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
    op.add_option('-n', '--name', dest='name', default="stress_test",
                  help="Name to prepend to containers")
    op.add_option('--stress-count', dest='count', default=10, type=int,
                  help="Number of containers and objects-per-container.")
    op.add_option('--stress-size', dest='size', default=2**20, type=int,
                  help="Size (in bytes) of each object created")
    options, args = op.parse_args()

    sst = SwiftServiceTest(debug=True)
    sst.connect()

    if options.api:
        sst.test_api(test_name=options.name)
    
    if options.stress:
        sst.stress_test(test_name=options.name, count=options.count,
                     size=options.size)

