import time
import socket
from datetime import datetime, timedelta

import debug
from data.update import UpdateStatus

from requests import Session
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

FORECAST_UPDATE_RATE = 60 * 60  # 1 hour between forecast updates
TOMORROW_API_URL = "https://api.tomorrow.io/v4"


def _is_dns_error(exc):
    cause = exc
    while cause:
        if isinstance(cause, socket.gaierror):
            return True
        cause = cause.__cause__
    return False


class Forecast:
    def __init__(self, config):
        self.apikey = config.forecast_tomorrow_apikey
        self.location = config.forecast_location
        self.units = config.forecast_units
        self.days = config.forecast_days
        self.enabled = config.forecast_enabled

        self.starttime = 0
        self.intervals = []
        self._session = None

        if self.enabled:
            self.update(force=True)

    def _get_session(self):
        if self._session is None:
            self._session = Session()
            retries = Retry(
                total=3,
                connect=3,
                read=3,
                backoff_factor=2,
                allowed_methods=["GET", "POST"],
                status_forcelist=[429, 500, 502, 503, 504],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retries, pool_connections=2, pool_maxsize=2)
            self._session.mount("https://", adapter)
            self._session.mount("http://", adapter)
        return self._session

    def available(self):
        return self.enabled and len(self.intervals) > 0

    def update(self, force=False) -> UpdateStatus:
        if not self.enabled:
            return UpdateStatus.DEFERRED

        if force or self._should_update():
            self.starttime = time.time()
            try:
                intervals = self._fetch_forecast()
                if intervals:
                    self.intervals = intervals
                    debug.log("Forecast updated: %d days", len(intervals))
                    return UpdateStatus.SUCCESS
                else:
                    debug.warning("[FORECAST] No forecast data returned")
                    return UpdateStatus.FAIL
            except RequestException as e:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                if _is_dns_error(e):
                    debug.warning("[%s] [FORECAST] DNS failure - will retry", timestamp)
                else:
                    debug.warning("[%s] [FORECAST] API request failed: %s", timestamp, e)
                return UpdateStatus.FAIL
            except (KeyError, ValueError) as e:
                debug.warning("[FORECAST] Unexpected data format: %s", e)
                return UpdateStatus.FAIL

        return UpdateStatus.DEFERRED

    def _fetch_forecast(self):
        dt = datetime.now() - timedelta(days=1)
        s = self._get_session()
        resp = s.post(
            f"{TOMORROW_API_URL}/timelines",
            headers={
                "Accept-Encoding": "gzip",
                "accept": "application/json",
                "content-type": "application/json",
            },
            params={"apikey": self.apikey},
            json={
                "location": self.location,
                "units": self.units,
                "timezone": "auto",
                "dailyStartHour": 6,
                "fields": [
                    "temperatureMin",
                    "temperatureMax",
                    "weatherCodeFullDay",
                ],
                "timesteps": ["1d"],
                "endTime": (dt + timedelta(days=int(self.days))).isoformat(),
            },
            timeout=(5, 20),
        )
        resp.raise_for_status()

        data = resp.json().get("data", {})
        timelines = data.get("timelines", [])
        if not timelines:
            return []
        return timelines[0].get("intervals", [])

    def get_forecast_days(self):
        """Return forecast intervals starting from today."""
        if not self.intervals:
            return []

        now = datetime.now().astimezone()
        today_local = now.date()

        result = []
        for day in self.intervals:
            raw_start = day["startTime"]
            local_time = datetime.fromisoformat(raw_start)
            entry_date = local_time.date()
            if entry_date < today_local:
                continue
            result.append({
                "day_name": local_time.strftime("%a"),
                "weather_code": day["values"]["weatherCodeFullDay"],
                "temp_min": day["values"]["temperatureMin"],
                "temp_max": day["values"]["temperatureMax"],
            })
        return result

    def _should_update(self):
        return (time.time() - self.starttime) >= FORECAST_UPDATE_RATE
