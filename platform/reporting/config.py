"""Configuration for Reporting and Visualization."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class ReportingSettings(BaseSettings):
    """Settings for reporting and visualization."""

    model_config = {"env_prefix": "REPORTING_", "case_sensitive": False}

    # Report Settings
    default_format: str = Field(
        default="markdown",
        description="Default report format (markdown, html, json)",
    )
    max_report_size_mb: int = Field(
        default=50,
        description="Maximum report size in MB",
    )
    report_retention_days: int = Field(
        default=365,
        description="Days to retain generated reports",
    )

    # Visualization Settings
    default_chart_width: int = Field(
        default=800,
        description="Default chart width in pixels",
    )
    default_chart_height: int = Field(
        default=600,
        description="Default chart height in pixels",
    )
    max_data_points: int = Field(
        default=10000,
        description="Maximum data points in a visualization",
    )
    color_palette: str = Field(
        default="viridis",
        description="Default color palette for charts",
    )

    # Dashboard Settings
    dashboard_refresh_seconds: int = Field(
        default=30,
        description="Dashboard auto-refresh interval",
    )
    max_widgets_per_dashboard: int = Field(
        default=20,
        description="Maximum widgets per dashboard",
    )
    max_dashboards_per_user: int = Field(
        default=10,
        description="Maximum dashboards per user",
    )

    # Export Settings
    enable_pdf_export: bool = Field(
        default=True,
        description="Enable PDF export (requires additional dependencies)",
    )
    enable_latex_export: bool = Field(
        default=True,
        description="Enable LaTeX export",
    )

    # Template Settings
    template_directory: str = Field(
        default="templates/reports",
        description="Directory for report templates",
    )
    custom_css_path: str | None = Field(
        default=None,
        description="Path to custom CSS for HTML reports",
    )


@lru_cache
def get_settings() -> ReportingSettings:
    """Get cached reporting settings."""
    return ReportingSettings()


# Report Types
REPORT_TYPES = {
    "research_summary": {
        "name": "Research Summary",
        "description": "Summary of research findings and progress",
        "sections": ["overview", "methodology", "results", "conclusions"],
    },
    "experiment_report": {
        "name": "Experiment Report",
        "description": "Detailed report of experiment execution and results",
        "sections": ["hypothesis", "design", "execution", "results", "analysis"],
    },
    "literature_review": {
        "name": "Literature Review",
        "description": "Comprehensive literature review",
        "sections": ["introduction", "methodology", "findings", "gaps", "references"],
    },
    "progress_report": {
        "name": "Progress Report",
        "description": "Progress update on research activities",
        "sections": ["summary", "completed", "in_progress", "planned", "blockers"],
    },
    "technical_report": {
        "name": "Technical Report",
        "description": "Technical details and specifications",
        "sections": ["abstract", "introduction", "methods", "results", "discussion"],
    },
    "verification_report": {
        "name": "Verification Report",
        "description": "Results of verification and validation",
        "sections": ["overview", "tests", "results", "issues", "recommendations"],
    },
}

# Output Formats
OUTPUT_FORMATS = {
    "markdown": {
        "name": "Markdown",
        "extension": ".md",
        "mime_type": "text/markdown",
    },
    "html": {
        "name": "HTML",
        "extension": ".html",
        "mime_type": "text/html",
    },
    "json": {
        "name": "JSON",
        "extension": ".json",
        "mime_type": "application/json",
    },
    "latex": {
        "name": "LaTeX",
        "extension": ".tex",
        "mime_type": "application/x-latex",
    },
    "pdf": {
        "name": "PDF",
        "extension": ".pdf",
        "mime_type": "application/pdf",
    },
}

# Chart Types
CHART_TYPES = {
    "line": {
        "name": "Line Chart",
        "description": "Show trends over time or sequences",
        "data_format": "series",
    },
    "bar": {
        "name": "Bar Chart",
        "description": "Compare categorical data",
        "data_format": "categories",
    },
    "scatter": {
        "name": "Scatter Plot",
        "description": "Show correlation between variables",
        "data_format": "points",
    },
    "pie": {
        "name": "Pie Chart",
        "description": "Show proportions of a whole",
        "data_format": "categories",
    },
    "heatmap": {
        "name": "Heatmap",
        "description": "Show intensity across two dimensions",
        "data_format": "matrix",
    },
    "histogram": {
        "name": "Histogram",
        "description": "Show distribution of values",
        "data_format": "values",
    },
    "box": {
        "name": "Box Plot",
        "description": "Show statistical distribution",
        "data_format": "groups",
    },
    "network": {
        "name": "Network Graph",
        "description": "Show relationships between entities",
        "data_format": "graph",
    },
    "treemap": {
        "name": "Treemap",
        "description": "Show hierarchical data",
        "data_format": "hierarchy",
    },
    "radar": {
        "name": "Radar Chart",
        "description": "Show multivariate data",
        "data_format": "multivariate",
    },
}

# Widget Types
WIDGET_TYPES = {
    "metric": {
        "name": "Metric",
        "description": "Single value with optional comparison",
        "size": "small",
    },
    "chart": {
        "name": "Chart",
        "description": "Data visualization chart",
        "size": "medium",
    },
    "table": {
        "name": "Table",
        "description": "Tabular data display",
        "size": "medium",
    },
    "text": {
        "name": "Text",
        "description": "Rich text content",
        "size": "variable",
    },
    "list": {
        "name": "List",
        "description": "List of items",
        "size": "small",
    },
    "progress": {
        "name": "Progress",
        "description": "Progress indicator",
        "size": "small",
    },
    "timeline": {
        "name": "Timeline",
        "description": "Chronological events",
        "size": "large",
    },
    "status": {
        "name": "Status",
        "description": "Status indicators",
        "size": "small",
    },
}

# Color Palettes
COLOR_PALETTES = {
    "viridis": ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"],
    "plasma": ["#0d0887", "#46039f", "#7201a8", "#9c179e", "#bd3786", "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921"],
    "inferno": ["#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60", "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4"],
    "magma": ["#000004", "#180f3d", "#440f76", "#721f81", "#9e2f7f", "#cd4071", "#f1605d", "#fd9668", "#feca8d", "#fcfdbf"],
    "cividis": ["#00204d", "#00306f", "#2b446e", "#4a5a6a", "#666f66", "#838461", "#a19a5b", "#c2b151", "#e6c845", "#ffdf00"],
    "scientific": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"],
    "pastel": ["#a6cee3", "#b2df8a", "#fb9a99", "#fdbf6f", "#cab2d6", "#ffff99", "#b15928", "#8dd3c7", "#bebada", "#fb8072"],
}

# Dashboard Layouts
DASHBOARD_LAYOUTS = {
    "single": {"columns": 1, "description": "Single column layout"},
    "two_column": {"columns": 2, "description": "Two equal columns"},
    "three_column": {"columns": 3, "description": "Three equal columns"},
    "sidebar_left": {"columns": 2, "ratios": [1, 3], "description": "Narrow left sidebar"},
    "sidebar_right": {"columns": 2, "ratios": [3, 1], "description": "Narrow right sidebar"},
    "grid_2x2": {"rows": 2, "columns": 2, "description": "2x2 grid"},
    "grid_3x3": {"rows": 3, "columns": 3, "description": "3x3 grid"},
}

# Metric Formats
METRIC_FORMATS = {
    "number": {"format": "{:,.0f}", "description": "Whole number with commas"},
    "decimal": {"format": "{:,.2f}", "description": "Two decimal places"},
    "percent": {"format": "{:.1%}", "description": "Percentage"},
    "currency": {"format": "${:,.2f}", "description": "Currency (USD)"},
    "scientific": {"format": "{:.2e}", "description": "Scientific notation"},
    "duration": {"format": "duration", "description": "Time duration"},
    "bytes": {"format": "bytes", "description": "Data size"},
}
