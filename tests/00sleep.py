import logging
from time import sleep

logger = logging.getLogger('nova_test.sleep')

def run(servers, **kwargs):
    logger.info("sleeping")
    sleep(5)
