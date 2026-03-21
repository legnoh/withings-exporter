from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Callable

import requests
from prometheus_client import Gauge, Counter, Info
from withings import OAuth2Token, WithingsApiError, WithingsClient

logger = logging.getLogger(__name__)

DEFAULT_SCOPE = "user.activity,user.metrics,user.info,user.sleepevents"
DEFAULT_REDIRECT_URI = "http://localhost:8000/"
AUTH_FAILURE_STATUSES = {100, 101, 102, 200, 401, 2553, 2555}
RATE_LIMIT_STATUS = 601


def _parse_datetime(value: str | None) -> datetime.datetime:
    if not value:
        return datetime.datetime.now(datetime.timezone.utc)

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _build_client(credentials: dict[str, str]) -> WithingsClient:
    token = OAuth2Token(
        access_token=credentials["access_token"],
        token_type=credentials.get("token_type") or "Bearer",
        refresh_token=credentials["refresh_token"],
        userid=int(credentials["userid"]),
        expires_in=int(credentials["expires_in"]),
        scope=credentials.get("scope") or DEFAULT_SCOPE,
        obtained_at=_parse_datetime(credentials.get("obtained_at") or credentials.get("created")),
    )

    return WithingsClient(
        client_id=credentials["client_id"],
        client_secret=credentials["consumer_secret"],
        redirect_uri=os.environ.get("WITHINGS_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        token=token,
    )


def _call_with_retry(func: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    while True:
        try:
            return func(*args, **kwargs)
        except WithingsApiError as exc:
            if exc.status != RATE_LIMIT_STATUS:
                raise
            logger.warning("too many requests! sleeping...")
            time.sleep(60)


def _read_config_value(logic: str, key: str) -> str | None:
    env_key = f"WITHINGS_{key.upper()}"
    if logic == "env":
        return os.getenv(env_key)

    if logic == "file":
        try:
            with open(f"./config/tmp/{key}", "r") as f:
                return f.read().strip()
        except IOError:
            return None

    return None


def _collect_paginated(fetch_page: Callable[[int | None], dict[str, Any]], result_key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    offset: int | None = None

    while True:
        body = fetch_page(offset)
        items.extend(body.get(result_key, []))
        if not body.get("more"):
            return items
        offset = body.get("offset")

def get_configs(logic):
    keys = ['access_token', 'token_type', 'refresh_token', 'userid', 'client_id', 'consumer_secret', 'expires_in']
    credentials = {}

    if logic != 'file' and logic != 'env':
        return None

    for key in keys:
        value = _read_config_value(logic, key)
        if value is None:
            return None
        credentials[key] = value

    created = _read_config_value(logic, 'created')
    obtained_at = _read_config_value(logic, 'obtained_at')
    if created is None and obtained_at is None:
        return None

    credentials['created'] = created or obtained_at
    credentials['obtained_at'] = obtained_at or created
    credentials['scope'] = _read_config_value(logic, 'scope') or DEFAULT_SCOPE

    return _build_client(credentials)

def cache_config(api: WithingsClient):
    if api.token is None:
        return None

    values = {
        'access_token': api.token.access_token,
        'token_type': api.token.token_type,
        'refresh_token': api.token.refresh_token,
        'userid': api.token.userid,
        'client_id': api.client_id,
        'consumer_secret': api.client_secret,
        'expires_in': api.token.expires_in,
        'created': api.token.obtained_at.isoformat(),
        'obtained_at': api.token.obtained_at.isoformat(),
        'scope': api.token.scope,
    }

    for key, value in values.items():
        try:
            with open(f"./config/tmp/{key}", "w") as f:
                f.write(str(value))
        except IOError:
            return None

def refresh_config(api: WithingsClient):
    try:
        api.refresh_access_token()
        cache_config(api)
        return api
    except (WithingsApiError, requests.RequestException, ValueError):
        return None

def check_auth(api: WithingsClient, severe=False):
    if api.token is None:
        return False

    try:
        if api.token.is_expired(0 if severe else 300):
            return False

        _call_with_retry(api.get_user_devices)
    except WithingsApiError as exc:
        if exc.status in AUTH_FAILURE_STATUSES:
            return False
        logger.warning("token validation failed: %s", exc)
        return True
    except requests.RequestException as exc:
        logger.warning("token validation failed: %s", exc)
        return False

    return True

def get_latest_meas_datas(api: WithingsClient):
    oneweekago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    return _collect_paginated(
        lambda offset: _call_with_retry(
            api.get_measures,
            startdate=None,
            enddate=None,
            lastupdate=int(oneweekago.timestamp()),
            offset=offset,
        )
        ,
        'measuregrps',
    )

def get_latest_activity_datas(api: WithingsClient, data_fields: list[str]):
    target_date = datetime.date.today()

    for _ in range(7):
        activities = _collect_paginated(
            lambda offset: _call_with_retry(
                api.get_activity,
                startdateymd=target_date,
                enddateymd=target_date,
                lastupdate=None,
                offset=offset,
                data_fields=data_fields,
            ),
            'activities',
        )
        if activities:
            return activities
        target_date -= datetime.timedelta(days=1)

    return []

def get_latest_sleep_datas(api: WithingsClient, data_fields: list[str]):
    target_date = datetime.date.today()

    for _ in range(7):
        series = _collect_paginated(
            lambda offset: _call_with_retry(
                api.get_sleep_summary,
                startdateymd=target_date,
                enddateymd=target_date,
                lastupdate=None,
                data_fields=data_fields,
            ),
            'series',
        )
        if series:
            return series
        target_date -= datetime.timedelta(days=1)

    return []

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
    if value == None:
        pass
    elif m._type == 'gauge':
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
