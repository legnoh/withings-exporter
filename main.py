import os,time,yaml, logging, sys
import modules.withings as wi
from prometheus_client import CollectorRegistry, start_http_server
from withings_api.common import TooManyRequestsException

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', filename="./exec.log")

for method in ['env', 'file']:
    api = wi.get_configs(method)
    if wi.check_auth(api) == False:
        api = wi.refresh_config(api)
        if api != None:
            break
    wi.cache_config(api)
if api == None:
    sys.exit(1)

registry = CollectorRegistry()
start_http_server(int(os.environ['PORT']), registry=registry)

with open('config/metrics.yml', 'r') as stream:
    config = yaml.load(stream, Loader=yaml.FullLoader)

meas_metrics = {}
activity_metrics = {}
sleep_metrics = {}

while True:

    if wi.check_auth(api) == False:
        logger.warn("token is expired. refreshing...")
        api = wi.refresh_config(api)
        if api == None:
            logger.error("token refresh is faild. stoped....")
            sys.exit(1)

    try:
        # get measurements
        logger.info("gathering measurement data...")
        res = wi.get_latest_meas_datas(api)
        for measuregrp in res.measuregrps:
            for measure in measuregrp.measures:
                labels = [
                    int(measuregrp.category),
                    measuregrp.deviceid,
                ]
                if measure.type not in meas_metrics:
                    meas_metrics[measure.type] = wi.create_metric_instance(config['meas']['metrics'][measure.type], registry, 'withings_meas_')
                wi.set_metrics(meas_metrics[measure.type], labels, measure.value * (10 ** measure.unit))

        # get activities
        logger.info("gathering activity data...")
        activities = wi.get_latest_activity_datas(api)
        for activity in activities:
            labels = [
                activity.deviceid,
                activity.brand,
                activity.is_tracker,
            ]

            for k, v in list(activity):
                if k in config['activity']['labels']['key'] or k in config['activity']['labels']['exclude']:
                    continue
                if k not in activity_metrics:
                    activity_metrics[k] = wi.create_metric_instance(config['activity']['metrics'][k], registry, 'withings_activity_')
                wi.set_metrics(activity_metrics[k], labels, v)

        # get sleep series
        logger.info("gathering sleep data...")
        sleepseries = wi.get_latest_sleep_datas(api)
        if sleepseries == None:
            logger.info("no sleepseries data... skipped")
        else:
            for sleep_data in sleepseries:
                labels = [
                    int(sleep_data.model),
                ]
                for k, v in list(sleep_data.data):
                    if k not in sleep_metrics:
                        sleep_metrics[k] = wi.create_metric_instance(config['sleep']['metrics'][k], registry, 'withings_sleep_')
                    wi.set_metrics(sleep_metrics[k], labels, v)

        logger.info("gathering health data successfull!")
    except TooManyRequestsException:
        logger.warn("too many requests! sleeping...")
        time.sleep(60)

    time.sleep(60)
