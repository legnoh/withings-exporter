import datetime, logging, os, sys
from prometheus_client import Gauge, Counter, Info
from withings_api import WithingsApi, Credentials2
from withings_api.common import AuthFailedException,GetActivityField,GetSleepSummaryField

def get_configs(logic):
    keys = ['access_token', 'token_type', 'refresh_token', 'userid', 'client_id', 'consumer_secret', 'expires_in']
    credentials = {}

    if logic != 'file' and logic != 'env':
        return None

    for key in keys:
        env_key = "WITHINGS_{key}".format(key=key.upper())
        if logic == 'env':
            if os.getenv(env_key) != None:
                credentials[key] = os.getenv(env_key)
                continue
            else:
                return None
        else:
            try:
                with open('./config/{key}'.format(key=key), "r") as f:
                    credentials[key] = f.read()
            except IOError:
                return None

    return WithingsApi(Credentials2(
        access_token=credentials['access_token'],
        token_type=credentials['token_type'],
        refresh_token=credentials['refresh_token'],
        userid=credentials['userid'],
        client_id=credentials['client_id'],
        consumer_secret=credentials['consumer_secret'],
        expires_in=credentials['expires_in']
    ))

def cache_config(api: WithingsApi):
    keys = ['access_token', 'token_type', 'refresh_token', 'userid', 'client_id', 'consumer_secret', 'expires_in']
    
    for key in keys:
        try:
            with open('./config/{key}'.format(key=key), "w") as f:
                f.write(str(getattr(api._credentials,key)))
        except IOError:
            return None

def refresh_config(api: WithingsApi):
    try:
        api.refresh_token()
        cache_config(api)
        return api
    except AuthFailedException:
        return None


def check_auth(api: WithingsApi):
    try:
        api.user_get_device()
    except AuthFailedException:
        return False
    return True

def get_latest_meas_datas(api: WithingsApi):

    oneweekago = datetime.datetime.now() - datetime.timedelta(days=7)
    meas_result = api.measure_get_meas(
        startdate=None,
        enddate=None,
        lastupdate=oneweekago
    )
    return meas_result

def get_latest_activity_datas(api: WithingsApi):

    target_date = datetime.datetime.now()
    
    i = 0
    res = None
    while res == None or i < 7:
        res = api.measure_get_activity(
            lastupdate=target_date,
            data_fields=GetActivityField,
        )
        if res.activities:
            return res.activities
        else:
            target_date = target_date - datetime.timedelta(days=1)
            res = None
            i += 1
    return None

def get_latest_sleep_datas(api: WithingsApi):

    target_date = datetime.datetime.now()
    
    i = 0
    res = None
    while res == None or i < 7:
        res = api.sleep_get_summary(
            lastupdate=target_date,
            data_fields=GetSleepSummaryField
        )
        if res.series:
            return res.series
        else:
            target_date = target_date - datetime.timedelta(days=1)
            res = None
            i += 1
    return None

def create_metric_instance(metric, registry, prefix):
    if metric['type'] == 'gauge':
        m = Gauge( prefix + metric['name'], metric['desc'], metric['labels'], registry=registry )
    elif metric['type'] == 'counter':
        m = Counter( prefix + metric['name'], metric['desc'], metric['labels'], registry=registry )
    elif metric['type'] == 'summary':
        m = Counter( prefix + metric['name'], metric['desc'], metric['labels'], registry=registry )
    elif metric['type'] == 'info':
        m = Info( prefix + metric['name'], metric['desc'], metric['labels'], registry=registry )
    else:
        return None
    return m

def set_metrics(m, labels, value):
    if m._type == 'gauge':
        m.labels(*labels).set(value)
    elif m._type == 'info':
        infos = {}
        for info in value:
            infos[info['key']] = info['value']
        m.labels(*labels).info(infos)
    elif m._type == 'counter':
        m.labels(*labels).inc(value)
    else:
        pass
