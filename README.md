withings-exporter
====

[![Badge](https://img.shields.io/badge/docker-legnoh/withings--exporter-blue?logo=docker&link=https://hub.docker.com/r/legnoh/withings-exporter)](https://hub.docker.com/r/legnoh/withings-exporter) [![ci](https://github.com/legnoh/withings-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/legnoh/withings-exporter/actions/workflows/ci.yml)

Prometheus exporter for [Withings Health Mate](https://www.withings.com/health-mate) (For Public Cloud).

## Usage

At first, create withings app for yours.

- [Register with Withings Public API | Withings](https://developer.withings.com/developer-guide/v3/integration-guide/public-health-data-api/developer-account/create-your-accesses-no-medical-cloud#create-your-application)
  - I recommend `http://localhost:8000/` to Callback URI.
  - Please note `CLIENT ID` and `CONSUMER SECRET`.

### Start(Docker)

The simplest way to use it is with Docker.

```
# set env
export WITHINGS_CLIENT_ID="YOURCRIENTID"
export WITHINGS_CONSUMER_SECRET="YOURCLIENTSECRET"

# run get_token.py
docker run -p 8000:8000 \
    --env WITHINGS_CLIENT_ID \
    --env WITHINGS_CONSUMER_SECRET \
    legnoh/withings-exporter python3 get_token.py

# paste your generated data to .env (and edit TZ)
vi .env

# run exporter(with above .env file)
docker run -p 9101:9101 \
    --env-file='.env' \
    legnoh/withings-exporter
```

## Start(source)

Alternatively, it can be started from the source.

```sh
# clone
git clone https://github.com/legnoh/withings_exporter.git && cd withings_exporter
pipenv install

# prepare env file for your apps
cp example/example.env .env

# input WITHINGS_CLIENT_ID, WITHINGS_CONSUMER_SECRET
vi .env

# exec get_token.py(in your browser)
pipenv run get-token

# paste your env to .env 3rd block (and edit TZ)
vi .env

# run exporter
pipenv run main
```

## Metrics

please check [metrics.yml](./config/metrics.yml) or [example](./example/withings.prom)

## Disclaim

- This script is NOT authorized by Withings.
  - We are not responsible for any damages caused by using this script.
- This script is not intended to overload these sites or services.
  - When using this script, please keep your posting frequency within a sensible range.
