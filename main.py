import os
import yaml
from withings_api import WithingsAuth, WithingsApi, AuthScope
from prometheus_client import CollectorRegistry, write_to_textfile
import modules.withings as wi
import logging
import sys

email = os.environ['WITHINGS_EMAIL']
password = os.environ['WITHINGS_PASSWORD']

auth = WithingsAuth(
    client_id=os.environ['WITHINGS_CLIENT_ID'],
    consumer_secret=os.environ['WITHINGS_CONSUMER_SECRET'],
    callback_uri=os.environ['WITHINGS_CALLBACK_URI'],
    scope=(
        AuthScope.USER_ACTIVITY,
        AuthScope.USER_METRICS,
        AuthScope.USER_INFO,
        AuthScope.USER_SLEEP_EVENTS,
    )
)
authorize_url = auth.get_authorize_url()

logging.info("get access token....")
code = wi.get_code(email, password, authorize_url)
if code == None:
    logging.error("failed to get code")
    sys.exit(1)

credentials = auth.get_credentials(code)
api = WithingsApi(credentials)

registry = CollectorRegistry()

with open('config/metrics.yml', 'r') as stream:
    config = yaml.load(stream, Loader=yaml.FullLoader)

# get measurements
logging.info("gathering measurement data...")
measuregrps = wi.get_latest_meas_datas(credentials.access_token)
meas_metrics = {}
if measuregrps == None:
    logging.info("no measurement data... skipped")
else:
    for measuregrp in measuregrps:
        for measure in measuregrp['measures']:
            labels = [
                measuregrp['category'],
                measuregrp['hash_deviceid'],
            ]
            if measure['type'] not in meas_metrics:
                meas_metrics[measure['type']] = wi.create_metric_instance(config['meas']['metrics'][measure['type']], registry, 'withings_meas_')
            wi.set_metrics(meas_metrics[measure['type']], labels, measure['value'] * (10 ** measure['unit']))

# get activities
logging.info("gathering activity data...")
activities = wi.get_latest_activity_datas(credentials.access_token, config['activity'])
if activities == None:
    logging.info("no activity data... skipped")
else:
    activity_metrics = {}
    for activity in activities:
        labels = [
            activity['hash_deviceid'],
            activity['brand'],
            activity['is_tracker']
        ]

        for k, v in activity.items():
            if k in config['activity']['labels']['key'] or k in config['activity']['labels']['exclude']:
                continue
            if k not in activity_metrics:
                activity_metrics[k] = wi.create_metric_instance(config['activity']['metrics'][k], registry, 'withings_activity_')
            wi.set_metrics(activity_metrics[k], labels, v)

# get sleep series
logging.info("gathering sleep data...")
sleepseries = wi.get_latest_sleep_datas(credentials.access_token, config['sleep'])
if sleepseries == None:
    logging.info("no sleepseries data... skipped")
else:
    sleep_metrics = {}
    for sleep_data in sleepseries:
        labels = [
            sleep_data['model'],
            sleep_data['model_id'],
            sleep_data['hash_deviceid'],
        ]
        for k, v in sleep_data['data'].items():
            if k not in sleep_metrics:
                sleep_metrics[k] = wi.create_metric_instance(config['sleep']['metrics'][k], registry, 'withings_sleep_')
            wi.set_metrics(sleep_metrics[k], labels, v)

write_to_textfile('./container/public/withings.prom', registry)
logging.info("gathering health data successfull!")
