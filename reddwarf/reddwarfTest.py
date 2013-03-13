#!/usr/bin/env python

import logging
import os

from reddwarfclient.client import Dbaas


logging.basicConfig(format='%(levelname)s\t%(name)s\t%(message)s')

logger = logging.getLogger('reddwarf_test')
logger.setLevel(logging.INFO)


class RedDwarfServiceTest(object):

    def __init__(self, username=None, password=None, tenant=None,
            auth_url=None, service_url=None, region_name=None):
        self.dbaas = Dbaas(username=username, api_key=password, tenant=tenant,
                auth_url=auth_url, service_url=service_url,
                service_type='hpext:dbaas', region_name=region_name)


    def instances(self):
        logger.info(self.dbaas.instances.list())

if __name__ == '__main__':

    username = os.environ['OS_USERNAME']
    password = os.environ['OS_PASSWORD']
    tenant = os.environ['OS_TENANT_NAME']
    auth_url = os.environ['OS_AUTH_URL']
    service_url = os.environ['OS_DB_URL']

    if not auth_url.endswith('/tokens'):
        auth_url += '/tokens'

    logger.info("Starting up.")
    rdst = RedDwarfServiceTest(username=username, password=password,
            tenant=tenant, auth_url=auth_url, service_url=service_url)

    rdst.instances()
