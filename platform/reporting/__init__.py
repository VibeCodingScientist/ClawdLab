"""Reporting and Visualization Module.

This module provides comprehensive reporting and visualization capabilities:
- Report generation in multiple formats (Markdown, HTML, JSON, LaTeX)
- Chart and visualization creation (line, bar, scatter, pie, heatmap, etc.)
- Dashboard management with widgets and real-time updates
- Specialized reports for experiments, literature reviews, and progress

The reporting layer enables agents to generate comprehensive reports,
visualizations, and dashboards for research activities.
"""

from platform.reporting.base import (
    # Enums
    ChartType,
    ReportFormat,
    ReportStatus,
    WidgetType,
    # Visualization classes
    Chart,
    ChartConfig,
    DataSeries,
    Visualization,
    # Report classes
    Report,
    ReportMetadata,
    ReportSection,
    # Dashboard classes
    Dashboard,
    DashboardTemplate,
    MetricValue,
    Widget,
    # Template classes
    ReportTemplate,
)
from platform.reporting.config import (
    CHART_TYPES,
    COLOR_PALETTES,
    DASHBOARD_LAYOUTS,
    METRIC_FORMATS,
    OUTPUT_FORMATS,
    REPORT_TYPES,
    WIDGET_TYPES,
    ReportingSettings,
    get_settings,
)
from platform.reporting.dashboard import (
    DashboardService,
    get_dashboard_service,
)
from platform.reporting.generator import (
    ReportGenerator,
    get_report_generator,
)
from platform.reporting.service import (
    ReportingService,
    ReportingStats,
    get_reporting_service,
)
from platform.reporting.visualizations import (
    ChartGenerator,
    get_chart_generator,
)

__all__ = [
    # Config
    "get_settings",
    "ReportingSettings",
    "REPORT_TYPES",
    "OUTPUT_FORMATS",
    "CHART_TYPES",
    "WIDGET_TYPES",
    "COLOR_PALETTES",
    "DASHBOARD_LAYOUTS",
    "METRIC_FORMATS",
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
    # Generators
    "ChartGenerator",
    "get_chart_generator",
    "ReportGenerator",
    "get_report_generator",
    # Dashboard service
    "DashboardService",
    "get_dashboard_service",
    # Main service
    "ReportingService",
    "ReportingStats",
    "get_reporting_service",
]
