#!/usr/bin/env python

#python libs
import csv
import os
import re
import signal
import sys
from datetime import datetime
from time import sleep

#swift libs
from swiftclient import client as swift

debug = True
userName = os.environ['OS_USERNAME']
password = os.environ['OS_PASSWORD']
tenantName = os.environ['OS_TENANT_NAME']
authURL = os.environ['OS_AUTH_URL']
authVersion = '2.0'
swiftURL = os.environ['OS_OBJECT_URL']

auth_url, token = swift.get_auth(authURL, userName, password, auth_version=authVersion, tenant_name=tenantName)
if debug:
    print(auth_url)
    print(token)

http_conn = swift.http_connection(swiftURL)
if debug:
    print(http_conn)

stats = swift.head_account(url=swiftURL, token=token, http_conn=http_conn)
if debug:
    print(stats)

header, containers = swift.get_account(url=swiftURL, token=token, http_conn=http_conn)
if debug:
    print(header)

for container in containers:
    header, objects = swift.get_container(url=swiftURL, token=token, container=container['name'], http_conn=http_conn)
    if debug:
        print(container)
        print(header)
        for obj in objects:
            print(obj)
