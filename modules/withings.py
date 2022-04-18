import arrow,datetime, logging, os, datetime, time
from prometheus_client import Gauge, Counter, Info
from withings_api import WithingsApi, Credentials2
from withings_api.common import AuthFailedException,GetActivityField,GetSleepSummaryField,TooManyRequestsException
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error

logger = logging.getLogger(__name__)

def get_configs(logic):
    keys = ['access_token', 'token_type', 'refresh_token', 'userid', 'client_id', 'consumer_secret', 'expires_in', 'created']
    credentials = {}

    if logic != 'file' and logic != 'env':
        return None

    for key in keys:
        if logic == 'env':
            env_key = "WITHINGS_{key}".format(key=key.upper())
            if os.getenv(env_key) != None:
                credentials[key] = os.getenv(env_key)
                continue
            else:
                return None
        elif logic == 'file':
            try:
                with open('./config/{key}'.format(key=key), "r") as f:
                    credentials[key] = f.read()
            except IOError:
                return None

    return WithingsApi(Credentials2(
        access_token=credentials['access_token'],
        token_type=credentials['token_type'],
        refresh_token=credentials['refresh_token'],
        userid=int(credentials['userid']),
        client_id=credentials['client_id'],
        consumer_secret=credentials['consumer_secret'],
        expires_in=int(credentials['expires_in']),
        created=arrow.get(credentials['created']),
    ))

def cache_config(api: WithingsApi):
    keys = ['access_token', 'token_type', 'refresh_token', 'userid', 'client_id', 'consumer_secret', 'expires_in', 'created']
    
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
    except CustomOAuth2Error:
        return None

def check_auth(api: WithingsApi, severe=False):
    try:
        now = arrow.utcnow().int_timestamp
        expired_time = api._credentials.created.shift(seconds=+api._credentials.expires_in).int_timestamp
        if severe == False and expired_time - now <  300:
            return False
        elif severe == True and expired_time - now < 0:
            return False
        api.user_get_device()
    except AuthFailedException:
        return False
    except CustomOAuth2Error:
        return False
    return True

def get_latest_meas_datas(api: WithingsApi):

    try:
        oneweekago = datetime.datetime.now() - datetime.timedelta(days=7)
        meas_result = api.measure_get_meas(
            startdate=None,
            enddate=None,
            lastupdate=oneweekago
        )
        return meas_result
    except TooManyRequestsException:
        logger.warning("too many requests! sleeping...")
        time.sleep(60)
        return get_latest_meas_datas(api)

def get_latest_activity_datas(api: WithingsApi):

    try:
        target_date = datetime.datetime.now()
        format_date = target_date.strftime('%Y-%m-%d')
        
        i = 0
        res = None
        while res == None and i < 7:
            res = api.measure_get_activity(
                startdateymd=format_date,
                enddateymd=format_date,
                lastupdate=None,
                data_fields=GetActivityField,
            )
            if res.activities:
                return res.activities
            else:
                target_date = target_date - datetime.timedelta(days=1)
                format_date = target_date.strftime('%Y-%m-%d')
                res = None
                i += 1
        return ()
    except TooManyRequestsException:
        logger.warning("too many requests! sleeping...")
        time.sleep(60)
        return get_latest_activity_datas(api)

def get_latest_sleep_datas(api: WithingsApi):

    try:
        target_date = datetime.datetime.now()
        format_date = target_date.strftime('%Y-%m-%d')
        
        i = 0
        res = None
        while res == None and i < 7:
            res = api.sleep_get_summary(
                startdateymd=format_date,
                enddateymd=format_date,
                lastupdate=None,
                data_fields=GetSleepSummaryField,
            )
            if res.series:
                return res.series
            else:
                target_date = target_date - datetime.timedelta(days=1)
                format_date = target_date.strftime('%Y-%m-%d')
                res = None
                i += 1
        return ()
    except TooManyRequestsException:
        logger.warning("too many requests! sleeping...")
        time.sleep(60)
        return get_latest_sleep_datas(api)

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
