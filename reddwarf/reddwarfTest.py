#!/usr/bin/env python

import logging
import os
import time

import sqlalchemy as sql

from reddwarfclient.client import Dbaas


logging.basicConfig(format='[%(levelname)s\t][%(name)s\t] %(message)s')

logger = logging.getLogger('reddwarf_test')
logger.setLevel(logging.DEBUG)


class RedDwarfServiceTest(object):

    def __init__(self, username=None, password=None, tenant=None,
            auth_url=None, service_url=None, region_name=None):
        self.dbaas = Dbaas(username=username,
                           api_key=password,
                           tenant=tenant,
                           auth_url=auth_url,
                           service_type='hpext:dbaas',
                           region_name=region_name)
        self.dbaas.authenticate()

    def flavor(self):
        return self.dbaas.flavors.list()[0]

    def flavors(self):
        flavors = self.dbaas.flavors.list()
        logger.info(flavors)
        for f in flavors:
            logger.debug(self.dbaas.flavors.get(f))


    def instances(self):
        instances = self.dbaas.instances.list()
        logger.info(instances)
        for i in instances:
            logger.debug(self.dbaas.instances.get(i))

    def volume(self, size=1):
        return {"size": size}

    def test_connection(self, db):
        ngin = sql.create_engine("mysql://{0}:{1}@{2}/mysql".format(db['user'],
                                                                    db['pass'],
                                                                    db['host']))

        ngin.connect()

        meta = sql.MetaData()
        table = sql.Table('test', meta,
                          sql.Column('test_id', sql.Integer, primary_key=True),
                          sql.Column('test_str', sql.String(128)))
        meta.create_all(ngin)

    def test(self, count=1, flavor=None, volume=None,
             size=3, base_name='reddwarf-test-'):

        self.flavors()
        self.instances()

        flavor = flavor or self.flavor().id
        volume = volume or self.volume(size)

        dbs = {}

        for c in xrange(count):
            name = base_name + str(c)
            db = self.dbaas.instances.create(name=name,
                                            flavor_id=flavor,
                                            volume=volume)
            dbs[db.id] = {}
            dbs[db.id]['status'] = db.status
            dbs[db.id]['user'] = db.credential['username']
            dbs[db.id]['pass'] = db.credential['password']

        for db_id, db in dbs.iteritems():
            update = None
            backoff = 1
            while db['status'] == u'building':
                time.sleep(2**backoff)
                update = self.dbaas.instances.get(db_id)
                db['status'] = update.status
            db['host'] = update.hostname
            logger.info(db)

        self.instances()
        for db_id, db in dbs.iteritems():
            self.test_connection(db)

        for db_id, db in dbs.iteritems():
            logger.info("Deleting database " + db_id)
            self.dbaas.instances.delete(db_id)


if __name__ == '__main__':

    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    tenant = os.environ['OS_TENANT_NAME']
    auth_url = os.environ['OS_AUTH_URL']

    auth_url += '/tokens'  # nova and swift don't expect this on the end
    logger.debug("Auth URL: {0}".format(auth_url))

    logger.info("Starting up.")
    rdst = RedDwarfServiceTest(username=username,
                               password=password,
                               tenant=tenant,
                               auth_url=auth_url)

    rdst.test()
