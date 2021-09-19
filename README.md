withings-exporter
====

Prometheus exporter for [Withings Health Mate](https://www.withings.com/health-mate) (For Public Cloud).

## Usage

At first, create withings app for yours.

- [Register with Withings Public API | Withings](https://developer.withings.com/developer-guide/getting-started/register-to-withings-api)
  - I recommends `http://localhost/` to Callback URI.
  - Please note `CLIENT ID` and `CONSUMER SECRET`.

This exporter script works for creating metrics file only.

```sh
# clone
git clone https://github.com/legnoh/withings_exporter.git && cd withings_exporter
pipenv install
pipenv shell

# prepare env file for your apps
cp example.env .env
vi .env

# execute
pipenv run main
```

Therefore, you should be hosted in other container to export metrics.

```sh
cd container
docker-compose up -d
curl -vvv http://localhost:9101/withings.prom
```

## Metrics

please check [metrics.yml](./config/metrics.yml) or [example](./container/example/withings.prom)

## Disclaim

- This script is NOT authorized by Withings.
  - We are not responsible for any damages caused by using this script.
- This script is not intended to overload these sites or services.
  - When using this script, please keep your posting frequency within a sensible range.
