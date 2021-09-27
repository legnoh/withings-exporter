from urllib import parse
from selenium import webdriver
import chromedriver_binary
import datetime
import requests
import time
import logging
from prometheus_client import Gauge, Counter, Info

def get_code(email, password, authorize_url):

    driver = webdriver.Chrome()

    logging.info("access to login page & get credentials...")
    driver.get(authorize_url);
    driver.implicitly_wait(10);

    cookie_allow_button = driver.find_element_by_class_name('primary')
    cookie_allow_button. click()

    email_box = driver.find_element_by_name('email')
    email_box.send_keys(email)
    time.sleep(5)

    password_box = driver.find_element_by_name('password')
    password_box.send_keys(password)
    time.sleep(5)
    password_box.submit()

    if driver.current_url.find("'https://account.withings.com/oauth2_user/account_login"):
        if driver.find_element_by_css_selector('div.alert > li'):
            get_error_message = driver.find_element_by_css_selector('div.alert > li').text
            logging.error("UI alerts: " + get_error_message)
            return None

    app_allow_button = driver.find_element_by_class_name('primary')
    app_allow_button.click()    

    code_url = driver.current_url
    params = dict(parse.parse_qsl(parse.urlsplit(code_url).query))

    driver.quit()
    return params['code']


def get_latest_meas_datas(access_token):

    oneweekago = datetime.datetime.now() - datetime.timedelta(days=7)

    res = request(access_token, "/measure", data={
                "action": "getmeas",
                "lastupdate": oneweekago.timestamp()
    })

    if res['body']['measuregrps']:
            return res['body']['measuregrps']
    return None

def get_latest_activity_datas(access_token, config):

    target_date = datetime.datetime.now()
    format_date = target_date.strftime('%Y-%m-%d')

    activity_data_fields = ""
    for activity_metric in config['metrics']:
        if activity_data_fields != "":
            activity_data_fields += "," + activity_metric
        else:
            activity_data_fields += activity_metric
    
    i = 0
    res = None
    while res == None or i < 7:
        res = request(access_token, config['request']['path'], data={
                    "action": config['request']['action'],
                    "startdateymd": format_date,
                    "enddateymd": format_date,
                    "data_fields": activity_data_fields,
        })
        if res['body']['activities']:
            return res['body']['activities']
        else:
            target_date = target_date - datetime.timedelta(days=1)
            format_date = target_date.strftime('%Y-%m-%d')
            res = None
            i += 1
    return None

def get_latest_sleep_datas(access_token, config):

    target_date = datetime.datetime.now()
    format_date = target_date.strftime('%Y-%m-%d')

    sleep_data_fields = ""
    for sleep_metric in config['metrics']:
        if sleep_data_fields != "":
            sleep_data_fields += "," + sleep_metric
        else:
            sleep_data_fields += sleep_metric
    
    i = 0
    res = None
    while res == None or i < 7:
        res = request(access_token, config['request']['path'], data={
                    "action": config['request']['action'],
                    "startdateymd": format_date,
                    "enddateymd": format_date,
                    "data_fields": sleep_data_fields,
        })
        if res['body']['series']:
            return res['body']['series']
        else:
            target_date = target_date - datetime.timedelta(days=1)
            format_date = target_date.strftime('%Y-%m-%d')
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

def request(access_token, path, data):

    try:
        response = requests.post(
            url="https://wbsapi.withings.net" + path,
            headers={
                "Authorization": "Bearer " + access_token,
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
            data=data,
        )
        response_json = response.json()
        if response_json['body']:
            return response_json
        return None
    except requests.exceptions.RequestException:
        logging.error('HTTP Request failed')
        return None
