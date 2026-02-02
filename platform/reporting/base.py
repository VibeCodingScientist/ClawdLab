"""Base classes and data structures for Reporting and Visualization."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class ReportFormat(Enum):
    """Output format for reports."""

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    LATEX = "latex"
    PDF = "pdf"


class ChartType(Enum):
    """Type of chart visualization."""

    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    PIE = "pie"
    HEATMAP = "heatmap"
    HISTOGRAM = "histogram"
    BOX = "box"
    NETWORK = "network"
    TREEMAP = "treemap"
    RADAR = "radar"


class WidgetType(Enum):
    """Type of dashboard widget."""

    METRIC = "metric"
    CHART = "chart"
    TABLE = "table"
    TEXT = "text"
    LIST = "list"
    PROGRESS = "progress"
    TIMELINE = "timeline"
    STATUS = "status"


class ReportStatus(Enum):
    """Status of a report."""

    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


# ===========================================
# VISUALIZATION DATA CLASSES
# ===========================================


@dataclass
class DataSeries:
    """A series of data points for visualization."""

    series_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    data: list[Any] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    color: str | None = None
    style: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "name": self.name,
            "data": self.data,
            "labels": self.labels,
            "color": self.color,
            "style": self.style,
        }


@dataclass
class ChartConfig:
    """Configuration for a chart."""

    title: str = ""
    subtitle: str = ""
    x_label: str = ""
    y_label: str = ""
    width: int = 800
    height: int = 600
    show_legend: bool = True
    show_grid: bool = True
    color_palette: str = "scientific"
    interactive: bool = True
    annotations: list[dict[str, Any]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "width": self.width,
            "height": self.height,
            "show_legend": self.show_legend,
            "show_grid": self.show_grid,
            "color_palette": self.color_palette,
            "interactive": self.interactive,
            "annotations": self.annotations,
            "options": self.options,
        }


@dataclass
class Chart:
    """A chart visualization."""

    chart_id: str = field(default_factory=lambda: str(uuid4()))
    chart_type: ChartType = ChartType.LINE
    config: ChartConfig = field(default_factory=ChartConfig)
    data_series: list[DataSeries] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    rendered_html: str = ""
    rendered_svg: str = ""
    image_path: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_id": self.chart_id,
            "chart_type": self.chart_type.value,
            "config": self.config.to_dict(),
            "data_series": [s.to_dict() for s in self.data_series],
            "raw_data": self.raw_data,
            "rendered_html": self.rendered_html,
            "rendered_svg": self.rendered_svg,
            "image_path": self.image_path,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Visualization:
    """A general visualization (charts, diagrams, etc.)."""

    viz_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    viz_type: str = "chart"
    charts: list[Chart] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    layout: dict[str, Any] = field(default_factory=dict)
    interactive: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "viz_id": self.viz_id,
            "name": self.name,
            "description": self.description,
            "viz_type": self.viz_type,
            "charts": [c.to_dict() for c in self.charts],
            "data": self.data,
            "layout": self.layout,
            "interactive": self.interactive,
            "created_at": self.created_at.isoformat(),
        }


# ===========================================
# REPORT DATA CLASSES
# ===========================================


@dataclass
class ReportSection:
    """A section within a report."""

    section_id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    content: str = ""
    order: int = 0
    level: int = 1  # Heading level (1-6)
    subsections: list["ReportSection"] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content": self.content,
            "order": self.order,
            "level": self.level,
            "subsections": [s.to_dict() for s in self.subsections],
            "charts": [c.to_dict() for c in self.charts],
            "tables": self.tables,
            "metadata": self.metadata,
        }


@dataclass
class ReportMetadata:
    """Metadata for a report."""

    title: str = ""
    subtitle: str = ""
    authors: list[str] = field(default_factory=list)
    date: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0"
    keywords: list[str] = field(default_factory=list)
    abstract: str = ""
    acknowledgments: str = ""
    references: list[dict[str, Any]] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "authors": self.authors,
            "date": self.date.isoformat(),
            "version": self.version,
            "keywords": self.keywords,
            "abstract": self.abstract,
            "acknowledgments": self.acknowledgments,
            "references": self.references,
            "custom": self.custom,
        }


@dataclass
class Report:
    """A generated report."""

    report_id: str = field(default_factory=lambda: str(uuid4()))
    report_type: str = "research_summary"
    format: ReportFormat = ReportFormat.MARKDOWN
    status: ReportStatus = ReportStatus.DRAFT
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    sections: list[ReportSection] = field(default_factory=list)
    visualizations: list[Visualization] = field(default_factory=list)
    appendices: list[ReportSection] = field(default_factory=list)
    rendered_content: str = ""
    output_path: str = ""
    size_bytes: int = 0
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "format": self.format.value,
            "status": self.status.value,
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "visualizations": [v.to_dict() for v in self.visualizations],
            "appendices": [a.to_dict() for a in self.appendices],
            "rendered_content": self.rendered_content,
            "output_path": self.output_path,
            "size_bytes": self.size_bytes,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# ===========================================
# DASHBOARD DATA CLASSES
# ===========================================


@dataclass
class MetricValue:
    """A metric value with optional comparison."""

    value: float = 0.0
    previous_value: float | None = None
    change: float | None = None
    change_percent: float | None = None
    trend: str = "stable"  # up, down, stable
    format: str = "number"
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "previous_value": self.previous_value,
            "change": self.change,
            "change_percent": self.change_percent,
            "trend": self.trend,
            "format": self.format,
            "unit": self.unit,
        }


@dataclass
class Widget:
    """A dashboard widget."""

    widget_id: str = field(default_factory=lambda: str(uuid4()))
    widget_type: WidgetType = WidgetType.METRIC
    title: str = ""
    description: str = ""
    position: dict[str, int] = field(default_factory=lambda: {"row": 0, "col": 0})
    size: dict[str, int] = field(default_factory=lambda: {"width": 1, "height": 1})
    data_source: str = ""
    query: str = ""
    refresh_seconds: int = 30
    content: Any = None
    chart: Chart | None = None
    metric: MetricValue | None = None
    config: dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type.value,
            "title": self.title,
            "description": self.description,
            "position": self.position,
            "size": self.size,
            "data_source": self.data_source,
            "query": self.query,
            "refresh_seconds": self.refresh_seconds,
            "content": self.content,
            "chart": self.chart.to_dict() if self.chart else None,
            "metric": self.metric.to_dict() if self.metric else None,
            "config": self.config,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class Dashboard:
    """A dashboard with widgets."""

    dashboard_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    layout: str = "two_column"
    widgets: list[Widget] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)
    time_range: dict[str, Any] = field(default_factory=dict)
    refresh_seconds: int = 30
    is_public: bool = False
    owner: str = ""
    shared_with: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "description": self.description,
            "layout": self.layout,
            "widgets": [w.to_dict() for w in self.widgets],
            "filters": self.filters,
            "time_range": self.time_range,
            "refresh_seconds": self.refresh_seconds,
            "is_public": self.is_public,
            "owner": self.owner,
            "shared_with": self.shared_with,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ===========================================
# TEMPLATE DATA CLASSES
# ===========================================


@dataclass
class ReportTemplate:
    """A template for generating reports."""

    template_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    report_type: str = "research_summary"
    sections: list[dict[str, Any]] = field(default_factory=list)
    default_format: ReportFormat = ReportFormat.MARKDOWN
    variables: list[str] = field(default_factory=list)
    style: dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "report_type": self.report_type,
            "sections": self.sections,
            "default_format": self.default_format.value,
            "variables": self.variables,
            "style": self.style,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DashboardTemplate:
    """A template for creating dashboards."""

    template_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    layout: str = "two_column"
    widget_configs: list[dict[str, Any]] = field(default_factory=list)
    default_filters: list[dict[str, Any]] = field(default_factory=list)
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "layout": self.layout,
            "widget_configs": self.widget_configs,
            "default_filters": self.default_filters,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }


__all__ = [
    # Enums
    "ReportFormat",
    "ChartType",
    "WidgetType",
    "ReportStatus",
    # Visualization classes
    "DataSeries",
    "ChartConfig",
    "Chart",
    "Visualization",
    # Report classes
    "ReportSection",
    "ReportMetadata",
    "Report",
    # Dashboard classes
    "MetricValue",
    "Widget",
    "Dashboard",
    # Template classes
    "ReportTemplate",
    "DashboardTemplate",
]
