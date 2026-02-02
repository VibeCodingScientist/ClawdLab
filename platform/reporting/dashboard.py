"""Dashboard Management Service."""

from datetime import datetime, timedelta
from typing import Any, Callable

from platform.reporting.base import (
    Chart,
    ChartConfig,
    ChartType,
    Dashboard,
    DashboardTemplate,
    DataSeries,
    MetricValue,
    Widget,
    WidgetType,
)
from platform.reporting.config import DASHBOARD_LAYOUTS, WIDGET_TYPES, get_settings
from platform.reporting.visualizations import ChartGenerator, get_chart_generator


class DashboardService:
    """Service for creating and managing dashboards."""

    def __init__(
        self,
        chart_generator: ChartGenerator | None = None,
    ) -> None:
        self._settings = get_settings()
        self._chart_generator = chart_generator or get_chart_generator()
        self._dashboards: dict[str, Dashboard] = {}
        self._templates: dict[str, DashboardTemplate] = {}
        self._data_sources: dict[str, Callable[[], Any]] = {}

        self._init_default_templates()

    def _init_default_templates(self) -> None:
        """Initialize default dashboard templates."""
        # Research overview template
        self._templates["research_overview"] = DashboardTemplate(
            name="Research Overview",
            description="Overview of research activities",
            layout="three_column",
            widget_configs=[
                {
                    "type": "metric",
                    "title": "Active Experiments",
                    "data_source": "experiments.active_count",
                    "position": {"row": 0, "col": 0},
                },
                {
                    "type": "metric",
                    "title": "Hypotheses Tested",
                    "data_source": "hypotheses.tested_count",
                    "position": {"row": 0, "col": 1},
                },
                {
                    "type": "metric",
                    "title": "Papers Analyzed",
                    "data_source": "literature.paper_count",
                    "position": {"row": 0, "col": 2},
                },
                {
                    "type": "chart",
                    "title": "Experiment Progress",
                    "chart_type": "line",
                    "data_source": "experiments.progress_over_time",
                    "position": {"row": 1, "col": 0},
                    "size": {"width": 2, "height": 1},
                },
                {
                    "type": "list",
                    "title": "Recent Activity",
                    "data_source": "activity.recent",
                    "position": {"row": 1, "col": 2},
                },
            ],
        )

        # Experiment dashboard template
        self._templates["experiment_dashboard"] = DashboardTemplate(
            name="Experiment Dashboard",
            description="Monitor experiment execution",
            layout="two_column",
            widget_configs=[
                {
                    "type": "progress",
                    "title": "Current Experiment",
                    "data_source": "experiment.current_progress",
                    "position": {"row": 0, "col": 0},
                    "size": {"width": 2, "height": 1},
                },
                {
                    "type": "chart",
                    "title": "Resource Usage",
                    "chart_type": "line",
                    "data_source": "resources.usage_over_time",
                    "position": {"row": 1, "col": 0},
                },
                {
                    "type": "table",
                    "title": "Step Status",
                    "data_source": "experiment.step_status",
                    "position": {"row": 1, "col": 1},
                },
                {
                    "type": "chart",
                    "title": "Metrics",
                    "chart_type": "bar",
                    "data_source": "experiment.metrics",
                    "position": {"row": 2, "col": 0},
                    "size": {"width": 2, "height": 1},
                },
            ],
        )

        # System status template
        self._templates["system_status"] = DashboardTemplate(
            name="System Status",
            description="Platform system status and health",
            layout="grid_2x2",
            widget_configs=[
                {
                    "type": "status",
                    "title": "Service Health",
                    "data_source": "system.service_health",
                    "position": {"row": 0, "col": 0},
                },
                {
                    "type": "chart",
                    "title": "CPU Usage",
                    "chart_type": "line",
                    "data_source": "system.cpu_usage",
                    "position": {"row": 0, "col": 1},
                },
                {
                    "type": "chart",
                    "title": "Memory Usage",
                    "chart_type": "line",
                    "data_source": "system.memory_usage",
                    "position": {"row": 1, "col": 0},
                },
                {
                    "type": "metric",
                    "title": "Queue Depth",
                    "data_source": "system.queue_depth",
                    "position": {"row": 1, "col": 1},
                },
            ],
        )

    async def create_dashboard(
        self,
        name: str,
        description: str = "",
        layout: str = "two_column",
        owner: str = "system",
    ) -> Dashboard:
        """Create a new dashboard."""
        dashboard = Dashboard(
            name=name,
            description=description,
            layout=layout,
            owner=owner,
            refresh_seconds=self._settings.dashboard_refresh_seconds,
        )

        self._dashboards[dashboard.dashboard_id] = dashboard
        return dashboard

    async def create_from_template(
        self,
        template_id: str,
        name: str | None = None,
        owner: str = "system",
    ) -> Dashboard:
        """Create a dashboard from a template."""
        template = self._templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        dashboard = Dashboard(
            name=name or template.name,
            description=template.description,
            layout=template.layout,
            owner=owner,
            filters=template.default_filters.copy(),
        )

        # Create widgets from template config
        for widget_config in template.widget_configs:
            widget = await self._create_widget_from_config(widget_config)
            dashboard.widgets.append(widget)

        self._dashboards[dashboard.dashboard_id] = dashboard
        return dashboard

    async def _create_widget_from_config(
        self,
        config: dict[str, Any],
    ) -> Widget:
        """Create a widget from configuration."""
        widget_type_str = config.get("type", "metric")
        widget_type = WidgetType(widget_type_str)

        widget = Widget(
            widget_type=widget_type,
            title=config.get("title", ""),
            description=config.get("description", ""),
            position=config.get("position", {"row": 0, "col": 0}),
            size=config.get("size", {"width": 1, "height": 1}),
            data_source=config.get("data_source", ""),
            refresh_seconds=config.get("refresh_seconds", self._settings.dashboard_refresh_seconds),
            config=config,
        )

        return widget

    async def add_widget(
        self,
        dashboard_id: str,
        widget_type: WidgetType,
        title: str,
        data_source: str = "",
        position: dict[str, int] | None = None,
        size: dict[str, int] | None = None,
        config: dict[str, Any] | None = None,
    ) -> Widget:
        """Add a widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        if len(dashboard.widgets) >= self._settings.max_widgets_per_dashboard:
            raise ValueError("Maximum widgets per dashboard exceeded")

        widget = Widget(
            widget_type=widget_type,
            title=title,
            data_source=data_source,
            position=position or {"row": 0, "col": 0},
            size=size or {"width": 1, "height": 1},
            config=config or {},
        )

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    async def add_metric_widget(
        self,
        dashboard_id: str,
        title: str,
        value: float,
        previous_value: float | None = None,
        format: str = "number",
        unit: str = "",
        position: dict[str, int] | None = None,
    ) -> Widget:
        """Add a metric widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        # Calculate change
        change = None
        change_percent = None
        trend = "stable"

        if previous_value is not None:
            change = value - previous_value
            if previous_value != 0:
                change_percent = (change / previous_value) * 100
            trend = "up" if change > 0 else "down" if change < 0 else "stable"

        metric = MetricValue(
            value=value,
            previous_value=previous_value,
            change=change,
            change_percent=change_percent,
            trend=trend,
            format=format,
            unit=unit,
        )

        widget = Widget(
            widget_type=WidgetType.METRIC,
            title=title,
            position=position or {"row": 0, "col": 0},
            metric=metric,
        )

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    async def add_chart_widget(
        self,
        dashboard_id: str,
        title: str,
        chart_type: ChartType,
        data: list[dict[str, Any]],
        position: dict[str, int] | None = None,
        size: dict[str, int] | None = None,
    ) -> Widget:
        """Add a chart widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        # Create chart
        config = ChartConfig(title=title, width=400, height=300)
        series_list = [
            DataSeries(
                name=d.get("name", ""),
                data=d.get("data", []),
                labels=d.get("labels", []),
            )
            for d in data
        ]

        if chart_type == ChartType.LINE:
            chart = await self._chart_generator.create_line_chart(series_list, config)
        elif chart_type == ChartType.BAR:
            chart = await self._chart_generator.create_bar_chart(series_list, config)
        elif chart_type == ChartType.PIE:
            chart = await self._chart_generator.create_pie_chart(
                data[0].get("data", []) if data else [],
                data[0].get("labels", []) if data else [],
                config,
            )
        else:
            chart = await self._chart_generator.create_line_chart(series_list, config)

        widget = Widget(
            widget_type=WidgetType.CHART,
            title=title,
            position=position or {"row": 0, "col": 0},
            size=size or {"width": 1, "height": 1},
            chart=chart,
        )

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    async def add_table_widget(
        self,
        dashboard_id: str,
        title: str,
        headers: list[str],
        rows: list[list[Any]],
        position: dict[str, int] | None = None,
    ) -> Widget:
        """Add a table widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        widget = Widget(
            widget_type=WidgetType.TABLE,
            title=title,
            position=position or {"row": 0, "col": 0},
            content={"headers": headers, "rows": rows},
        )

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    async def add_progress_widget(
        self,
        dashboard_id: str,
        title: str,
        current: float,
        total: float,
        label: str = "",
        position: dict[str, int] | None = None,
    ) -> Widget:
        """Add a progress widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        percent = (current / total * 100) if total > 0 else 0

        widget = Widget(
            widget_type=WidgetType.PROGRESS,
            title=title,
            position=position or {"row": 0, "col": 0},
            content={
                "current": current,
                "total": total,
                "percent": percent,
                "label": label or f"{percent:.1f}%",
            },
        )

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    async def add_timeline_widget(
        self,
        dashboard_id: str,
        title: str,
        events: list[dict[str, Any]],
        position: dict[str, int] | None = None,
        size: dict[str, int] | None = None,
    ) -> Widget:
        """Add a timeline widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        widget = Widget(
            widget_type=WidgetType.TIMELINE,
            title=title,
            position=position or {"row": 0, "col": 0},
            size=size or {"width": 2, "height": 1},
            content={"events": events},
        )

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    async def add_status_widget(
        self,
        dashboard_id: str,
        title: str,
        statuses: list[dict[str, Any]],
        position: dict[str, int] | None = None,
    ) -> Widget:
        """Add a status widget to a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        widget = Widget(
            widget_type=WidgetType.STATUS,
            title=title,
            position=position or {"row": 0, "col": 0},
            content={"statuses": statuses},
        )

        dashboard.widgets.append(widget)
        dashboard.updated_at = datetime.utcnow()

        return widget

    async def update_widget(
        self,
        dashboard_id: str,
        widget_id: str,
        updates: dict[str, Any],
    ) -> Widget | None:
        """Update a widget in a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None

        for widget in dashboard.widgets:
            if widget.widget_id == widget_id:
                # Update allowed fields
                if "title" in updates:
                    widget.title = updates["title"]
                if "position" in updates:
                    widget.position = updates["position"]
                if "size" in updates:
                    widget.size = updates["size"]
                if "data_source" in updates:
                    widget.data_source = updates["data_source"]
                if "refresh_seconds" in updates:
                    widget.refresh_seconds = updates["refresh_seconds"]
                if "config" in updates:
                    widget.config.update(updates["config"])

                widget.last_updated = datetime.utcnow()
                dashboard.updated_at = datetime.utcnow()
                return widget

        return None

    async def remove_widget(
        self,
        dashboard_id: str,
        widget_id: str,
    ) -> bool:
        """Remove a widget from a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return False

        for i, widget in enumerate(dashboard.widgets):
            if widget.widget_id == widget_id:
                dashboard.widgets.pop(i)
                dashboard.updated_at = datetime.utcnow()
                return True

        return False

    async def refresh_widget(
        self,
        dashboard_id: str,
        widget_id: str,
    ) -> Widget | None:
        """Refresh a widget's data."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None

        for widget in dashboard.widgets:
            if widget.widget_id == widget_id:
                # Fetch data from source if registered
                if widget.data_source and widget.data_source in self._data_sources:
                    data_fn = self._data_sources[widget.data_source]
                    widget.content = data_fn()

                widget.last_updated = datetime.utcnow()
                return widget

        return None

    async def refresh_dashboard(self, dashboard_id: str) -> Dashboard | None:
        """Refresh all widgets in a dashboard."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None

        for widget in dashboard.widgets:
            await self.refresh_widget(dashboard_id, widget.widget_id)

        dashboard.updated_at = datetime.utcnow()
        return dashboard

    def register_data_source(
        self,
        name: str,
        data_fn: Callable[[], Any],
    ) -> None:
        """Register a data source function."""
        self._data_sources[name] = data_fn

    async def get_dashboard(self, dashboard_id: str) -> Dashboard | None:
        """Get a dashboard by ID."""
        return self._dashboards.get(dashboard_id)

    async def list_dashboards(
        self,
        owner: str | None = None,
        include_public: bool = True,
    ) -> list[Dashboard]:
        """List dashboards."""
        dashboards = list(self._dashboards.values())

        if owner:
            dashboards = [
                d for d in dashboards
                if d.owner == owner or (include_public and d.is_public)
            ]

        return dashboards

    async def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard."""
        if dashboard_id in self._dashboards:
            del self._dashboards[dashboard_id]
            return True
        return False

    async def share_dashboard(
        self,
        dashboard_id: str,
        user_ids: list[str],
    ) -> Dashboard | None:
        """Share a dashboard with users."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None

        dashboard.shared_with.extend(user_ids)
        dashboard.shared_with = list(set(dashboard.shared_with))
        dashboard.updated_at = datetime.utcnow()

        return dashboard

    async def set_public(
        self,
        dashboard_id: str,
        is_public: bool,
    ) -> Dashboard | None:
        """Set dashboard public status."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None

        dashboard.is_public = is_public
        dashboard.updated_at = datetime.utcnow()

        return dashboard

    async def get_templates(self) -> list[DashboardTemplate]:
        """Get available dashboard templates."""
        return list(self._templates.values())

    async def render_dashboard_html(self, dashboard_id: str) -> str:
        """Render dashboard as HTML."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return "<html><body>Dashboard not found</body></html>"

        layout_info = DASHBOARD_LAYOUTS.get(dashboard.layout, DASHBOARD_LAYOUTS["two_column"])
        columns = layout_info.get("columns", 2)

        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{dashboard.name}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }",
            ".dashboard { max-width: 1200px; margin: 0 auto; }",
            ".dashboard-title { font-size: 24px; margin-bottom: 20px; }",
            f".widget-grid {{ display: grid; grid-template-columns: repeat({columns}, 1fr); gap: 20px; }}",
            ".widget { background: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            ".widget-title { font-size: 14px; color: #666; margin-bottom: 10px; }",
            ".metric-value { font-size: 32px; font-weight: bold; }",
            ".metric-change { font-size: 14px; }",
            ".metric-change.up { color: #22c55e; }",
            ".metric-change.down { color: #ef4444; }",
            ".progress-bar { background: #e5e5e5; border-radius: 4px; height: 20px; overflow: hidden; }",
            ".progress-fill { background: #3b82f6; height: 100%; }",
            ".status-item { display: flex; align-items: center; padding: 5px 0; }",
            ".status-dot { width: 10px; height: 10px; border-radius: 50%; margin-right: 10px; }",
            ".status-ok { background: #22c55e; }",
            ".status-warning { background: #f59e0b; }",
            ".status-error { background: #ef4444; }",
            "table { width: 100%; border-collapse: collapse; }",
            "th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }",
            "th { background: #f9f9f9; }",
            "</style>",
            "</head>",
            "<body>",
            "<div class='dashboard'>",
            f"<h1 class='dashboard-title'>{dashboard.name}</h1>",
            "<div class='widget-grid'>",
        ]

        # Render widgets
        for widget in dashboard.widgets:
            html.append(self._render_widget_html(widget))

        html.extend([
            "</div>",
            "</div>",
            f"<script>setTimeout(() => location.reload(), {dashboard.refresh_seconds * 1000})</script>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html)

    def _render_widget_html(self, widget: Widget) -> str:
        """Render a single widget as HTML."""
        size = widget.size
        style = ""
        if size.get("width", 1) > 1:
            style = f"grid-column: span {size['width']};"

        html = [f"<div class='widget' style='{style}'>"]
        html.append(f"<div class='widget-title'>{widget.title}</div>")

        if widget.widget_type == WidgetType.METRIC and widget.metric:
            m = widget.metric
            html.append(f"<div class='metric-value'>{self._format_metric(m)}</div>")
            if m.change is not None:
                css_class = f"metric-change {m.trend}"
                sign = "+" if m.change > 0 else ""
                html.append(f"<div class='{css_class}'>{sign}{m.change_percent:.1f}%</div>")

        elif widget.widget_type == WidgetType.CHART and widget.chart:
            html.append(widget.chart.rendered_svg or "No chart data")

        elif widget.widget_type == WidgetType.TABLE and widget.content:
            content = widget.content
            html.append("<table>")
            if content.get("headers"):
                html.append("<tr>")
                for h in content["headers"]:
                    html.append(f"<th>{h}</th>")
                html.append("</tr>")
            for row in content.get("rows", []):
                html.append("<tr>")
                for cell in row:
                    html.append(f"<td>{cell}</td>")
                html.append("</tr>")
            html.append("</table>")

        elif widget.widget_type == WidgetType.PROGRESS and widget.content:
            content = widget.content
            percent = content.get("percent", 0)
            html.append(f"<div class='progress-bar'><div class='progress-fill' style='width: {percent}%'></div></div>")
            html.append(f"<div>{content.get('label', '')}</div>")

        elif widget.widget_type == WidgetType.STATUS and widget.content:
            for status in widget.content.get("statuses", []):
                status_class = f"status-{status.get('status', 'ok')}"
                html.append(f"<div class='status-item'><div class='status-dot {status_class}'></div>{status.get('name', '')}</div>")

        elif widget.widget_type == WidgetType.LIST and widget.content:
            html.append("<ul>")
            for item in widget.content if isinstance(widget.content, list) else []:
                html.append(f"<li>{item}</li>")
            html.append("</ul>")

        elif widget.widget_type == WidgetType.TEXT:
            html.append(f"<div>{widget.content or ''}</div>")

        html.append("</div>")
        return "\n".join(html)

    def _format_metric(self, metric: MetricValue) -> str:
        """Format a metric value for display."""
        fmt = metric.format
        val = metric.value

        if fmt == "percent":
            return f"{val:.1%}"
        elif fmt == "currency":
            return f"${val:,.2f}"
        elif fmt == "decimal":
            return f"{val:,.2f}"
        elif fmt == "scientific":
            return f"{val:.2e}"
        else:
            return f"{val:,.0f}"


# Singleton instance
_dashboard_service: DashboardService | None = None


def get_dashboard_service() -> DashboardService:
    """Get or create dashboard service singleton."""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service


__all__ = [
    "DashboardService",
    "get_dashboard_service",
]
