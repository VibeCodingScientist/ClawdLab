"""Metrics Collection and Aggregation."""

import statistics
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Generator

from platform.monitoring.base import (
    HistogramBucket,
    HistogramValue,
    Metric,
    MetricType,
    MetricValue,
)
from platform.monitoring.config import STANDARD_METRICS, get_settings


class Counter:
    """A counter metric that only increases."""

    def __init__(self, name: str, description: str = "", labels: list[str] | None = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: dict[tuple, float] = defaultdict(float)

    def increment(self, value: float = 1.0, **label_values: str) -> None:
        """Increment the counter."""
        key = self._make_key(label_values)
        self._values[key] += value

    def get(self, **label_values: str) -> float:
        """Get the current counter value."""
        key = self._make_key(label_values)
        return self._values[key]

    def get_all(self) -> dict[tuple, float]:
        """Get all counter values."""
        return dict(self._values)

    def _make_key(self, label_values: dict[str, str]) -> tuple:
        """Create a key from label values."""
        return tuple(sorted(label_values.items()))


class Gauge:
    """A gauge metric that can go up or down."""

    def __init__(self, name: str, description: str = "", labels: list[str] | None = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: dict[tuple, float] = defaultdict(float)

    def set(self, value: float, **label_values: str) -> None:
        """Set the gauge value."""
        key = self._make_key(label_values)
        self._values[key] = value

    def increment(self, value: float = 1.0, **label_values: str) -> None:
        """Increment the gauge."""
        key = self._make_key(label_values)
        self._values[key] += value

    def decrement(self, value: float = 1.0, **label_values: str) -> None:
        """Decrement the gauge."""
        key = self._make_key(label_values)
        self._values[key] -= value

    def get(self, **label_values: str) -> float:
        """Get the current gauge value."""
        key = self._make_key(label_values)
        return self._values[key]

    def get_all(self) -> dict[tuple, float]:
        """Get all gauge values."""
        return dict(self._values)

    def _make_key(self, label_values: dict[str, str]) -> tuple:
        return tuple(sorted(label_values.items()))


class Histogram:
    """A histogram metric for distributions."""

    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ):
        self.name = name
        self.description = description
        self.labels = labels or []
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._observations: dict[tuple, list[float]] = defaultdict(list)

    def observe(self, value: float, **label_values: str) -> None:
        """Observe a value."""
        key = self._make_key(label_values)
        self._observations[key].append(value)

    def get_histogram(self, **label_values: str) -> HistogramValue:
        """Get histogram data for labels."""
        key = self._make_key(label_values)
        observations = self._observations[key]

        if not observations:
            return HistogramValue(
                buckets=[HistogramBucket(le=b, count=0) for b in self.buckets],
                sum=0.0,
                count=0,
            )

        bucket_counts = []
        for bucket in self.buckets:
            count = sum(1 for v in observations if v <= bucket)
            bucket_counts.append(HistogramBucket(le=bucket, count=count))

        return HistogramValue(
            buckets=bucket_counts,
            sum=sum(observations),
            count=len(observations),
        )

    def get_percentile(self, percentile: float, **label_values: str) -> float:
        """Get a percentile value."""
        key = self._make_key(label_values)
        observations = self._observations[key]

        if not observations:
            return 0.0

        sorted_obs = sorted(observations)
        idx = int(len(sorted_obs) * percentile / 100)
        return sorted_obs[min(idx, len(sorted_obs) - 1)]

    def get_mean(self, **label_values: str) -> float:
        """Get the mean value."""
        key = self._make_key(label_values)
        observations = self._observations[key]
        return statistics.mean(observations) if observations else 0.0

    def get_all(self) -> dict[tuple, HistogramValue]:
        """Get all histogram data."""
        result = {}
        for key in self._observations:
            label_values = dict(key)
            result[key] = self.get_histogram(**label_values)
        return result

    def _make_key(self, label_values: dict[str, str]) -> tuple:
        return tuple(sorted(label_values.items()))


class Timer:
    """A timer metric for measuring durations."""

    def __init__(self, name: str, description: str = "", labels: list[str] | None = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._histogram = Histogram(
            name=name,
            description=description,
            labels=labels,
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
        )
        self._active_timers: dict[str, float] = {}

    def start(self, timer_id: str | None = None) -> str:
        """Start a timer."""
        timer_id = timer_id or str(time.time())
        self._active_timers[timer_id] = time.time()
        return timer_id

    def stop(self, timer_id: str, **label_values: str) -> float:
        """Stop a timer and record the duration."""
        if timer_id not in self._active_timers:
            return 0.0

        start_time = self._active_timers.pop(timer_id)
        duration = time.time() - start_time
        self._histogram.observe(duration, **label_values)
        return duration

    def record(self, duration: float, **label_values: str) -> None:
        """Record a duration directly."""
        self._histogram.observe(duration, **label_values)

    @contextmanager
    def time(self, **label_values: str) -> Generator[None, None, None]:
        """Context manager to time a block of code."""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self._histogram.observe(duration, **label_values)

    def get_mean(self, **label_values: str) -> float:
        """Get the mean duration."""
        return self._histogram.get_mean(**label_values)

    def get_percentile(self, percentile: float, **label_values: str) -> float:
        """Get a percentile duration."""
        return self._histogram.get_percentile(percentile, **label_values)

    def get_histogram(self, **label_values: str) -> HistogramValue:
        """Get histogram data."""
        return self._histogram.get_histogram(**label_values)


class MetricsCollector:
    """Collects and manages metrics."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._timers: dict[str, Timer] = {}
        self._metrics: dict[str, Metric] = {}
        self._history: dict[str, list[MetricValue]] = defaultdict(list)
        self._start_time = datetime.utcnow()

        self._init_standard_metrics()

    def _init_standard_metrics(self) -> None:
        """Initialize standard metrics."""
        for name, config in STANDARD_METRICS.items():
            metric_type = config.get("type", "gauge")
            description = config.get("description", "")
            labels = config.get("labels", [])

            if metric_type == "counter":
                self.create_counter(name, description, labels)
            elif metric_type == "gauge":
                self.create_gauge(name, description, labels)
            elif metric_type == "histogram":
                buckets = config.get("buckets")
                self.create_histogram(name, description, labels, buckets)
            elif metric_type == "timer":
                self.create_timer(name, description, labels)

    # ===========================================
    # METRIC CREATION
    # ===========================================

    def create_counter(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Counter:
        """Create a counter metric."""
        counter = Counter(name, description, labels)
        self._counters[name] = counter

        self._metrics[name] = Metric(
            name=name,
            description=description,
            metric_type=MetricType.COUNTER,
            labels=labels or [],
        )

        return counter

    def create_gauge(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Gauge:
        """Create a gauge metric."""
        gauge = Gauge(name, description, labels)
        self._gauges[name] = gauge

        self._metrics[name] = Metric(
            name=name,
            description=description,
            metric_type=MetricType.GAUGE,
            labels=labels or [],
        )

        return gauge

    def create_histogram(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        """Create a histogram metric."""
        histogram = Histogram(name, description, labels, buckets)
        self._histograms[name] = histogram

        self._metrics[name] = Metric(
            name=name,
            description=description,
            metric_type=MetricType.HISTOGRAM,
            labels=labels or [],
            buckets=histogram.buckets,
        )

        return histogram

    def create_timer(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Timer:
        """Create a timer metric."""
        timer = Timer(name, description, labels)
        self._timers[name] = timer

        self._metrics[name] = Metric(
            name=name,
            description=description,
            metric_type=MetricType.TIMER,
            labels=labels or [],
        )

        return timer

    # ===========================================
    # METRIC ACCESS
    # ===========================================

    def counter(self, name: str) -> Counter | None:
        """Get a counter by name."""
        return self._counters.get(name)

    def gauge(self, name: str) -> Gauge | None:
        """Get a gauge by name."""
        return self._gauges.get(name)

    def histogram(self, name: str) -> Histogram | None:
        """Get a histogram by name."""
        return self._histograms.get(name)

    def timer(self, name: str) -> Timer | None:
        """Get a timer by name."""
        return self._timers.get(name)

    # ===========================================
    # CONVENIENCE METHODS
    # ===========================================

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Increment a counter or gauge."""
        if name in self._counters:
            self._counters[name].increment(value, **labels)
        elif name in self._gauges:
            self._gauges[name].increment(value, **labels)

        self._record_history(name, value, labels)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge value."""
        if name in self._gauges:
            self._gauges[name].set(value, **labels)
        else:
            gauge = self.create_gauge(name, labels=list(labels.keys()))
            gauge.set(value, **labels)

        self._record_history(name, value, labels)

    def observe(self, name: str, value: float, **labels: str) -> None:
        """Observe a value for a histogram."""
        if name in self._histograms:
            self._histograms[name].observe(value, **labels)

        self._record_history(name, value, labels)

    def record_time(self, name: str, duration: float, **labels: str) -> None:
        """Record a duration for a timer."""
        if name in self._timers:
            self._timers[name].record(duration, **labels)

        self._record_history(name, duration, labels)

    @contextmanager
    def time_operation(self, name: str, **labels: str) -> Generator[None, None, None]:
        """Context manager to time an operation."""
        timer = self._timers.get(name)
        if timer:
            with timer.time(**labels):
                yield
        else:
            start = time.time()
            try:
                yield
            finally:
                duration = time.time() - start
                self._record_history(name, duration, labels)

    def _record_history(
        self,
        name: str,
        value: float,
        labels: dict[str, str],
    ) -> None:
        """Record a value in history."""
        self._history[name].append(MetricValue(
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels,
        ))

        # Trim history based on retention
        retention = timedelta(hours=self._settings.metrics_retention_hours)
        cutoff = datetime.utcnow() - retention

        self._history[name] = [
            v for v in self._history[name]
            if v.timestamp > cutoff
        ]

    # ===========================================
    # QUERYING
    # ===========================================

    def get_metric_value(self, name: str, **labels: str) -> float | None:
        """Get the current value of a metric."""
        if name in self._counters:
            return self._counters[name].get(**labels)
        elif name in self._gauges:
            return self._gauges[name].get(**labels)
        elif name in self._histograms:
            return self._histograms[name].get_mean(**labels)
        elif name in self._timers:
            return self._timers[name].get_mean(**labels)
        return None

    def get_metric_history(
        self,
        name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        **labels: str,
    ) -> list[MetricValue]:
        """Get historical values for a metric."""
        history = self._history.get(name, [])

        if start_time:
            history = [v for v in history if v.timestamp >= start_time]

        if end_time:
            history = [v for v in history if v.timestamp <= end_time]

        if labels:
            history = [
                v for v in history
                if all(v.labels.get(k) == val for k, val in labels.items())
            ]

        return history

    def get_all_metrics(self) -> list[Metric]:
        """Get all registered metrics."""
        return list(self._metrics.values())

    def get_metric(self, name: str) -> Metric | None:
        """Get a metric definition by name."""
        return self._metrics.get(name)

    def collect(self) -> dict[str, Any]:
        """Collect all current metric values."""
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "counters": {},
            "gauges": {},
            "histograms": {},
            "timers": {},
        }

        for name, counter in self._counters.items():
            result["counters"][name] = {
                str(k): v for k, v in counter.get_all().items()
            }

        for name, gauge in self._gauges.items():
            result["gauges"][name] = {
                str(k): v for k, v in gauge.get_all().items()
            }

        for name, histogram in self._histograms.items():
            result["histograms"][name] = {
                str(k): v.to_dict() for k, v in histogram.get_all().items()
            }

        for name, timer in self._timers.items():
            all_histograms = timer._histogram.get_all()
            result["timers"][name] = {
                str(k): v.to_dict() for k, v in all_histograms.items()
            }

        return result

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        # Counters
        for name, counter in self._counters.items():
            metric = self._metrics.get(name)
            if metric:
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} counter")

            for labels, value in counter.get_all().items():
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")

        # Gauges
        for name, gauge in self._gauges.items():
            metric = self._metrics.get(name)
            if metric:
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} gauge")

            for labels, value in gauge.get_all().items():
                label_str = self._format_labels(labels)
                lines.append(f"{name}{label_str} {value}")

        # Histograms
        for name, histogram in self._histograms.items():
            metric = self._metrics.get(name)
            if metric:
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} histogram")

            for labels, hist_value in histogram.get_all().items():
                label_str = self._format_labels(labels)
                for bucket in hist_value.buckets:
                    bucket_labels = dict(labels) if labels else {}
                    bucket_labels_str = self._format_labels(
                        tuple(sorted({**dict(labels), "le": str(bucket.le)}.items()))
                    )
                    lines.append(f"{name}_bucket{bucket_labels_str} {bucket.count}")
                lines.append(f"{name}_sum{label_str} {hist_value.sum}")
                lines.append(f"{name}_count{label_str} {hist_value.count}")

        return "\n".join(lines)

    def _format_labels(self, labels: tuple) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        label_pairs = [f'{k}="{v}"' for k, v in labels]
        return "{" + ",".join(label_pairs) + "}"

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the metrics collector."""
        return {
            "total_counters": len(self._counters),
            "total_gauges": len(self._gauges),
            "total_histograms": len(self._histograms),
            "total_timers": len(self._timers),
            "total_metrics": len(self._metrics),
            "history_entries": sum(len(v) for v in self._history.values()),
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
        }


# Singleton instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create metrics collector singleton."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


__all__ = [
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "MetricsCollector",
    "get_metrics_collector",
]
