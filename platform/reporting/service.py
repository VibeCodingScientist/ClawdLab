"""Main Reporting Service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from platform.reporting.base import (
    Chart,
    ChartConfig,
    ChartType,
    Dashboard,
    DataSeries,
    Report,
    ReportFormat,
    ReportStatus,
    Visualization,
    WidgetType,
)
from platform.reporting.config import get_settings
from platform.reporting.dashboard import DashboardService, get_dashboard_service
from platform.reporting.generator import ReportGenerator, get_report_generator
from platform.reporting.visualizations import ChartGenerator, get_chart_generator


@dataclass
class ReportingStats:
    """Statistics about reporting activities."""

    total_reports: int = 0
    reports_by_type: dict[str, int] | None = None
    reports_by_format: dict[str, int] | None = None
    completed_reports: int = 0
    failed_reports: int = 0
    total_dashboards: int = 0
    total_visualizations: int = 0
    avg_report_size_bytes: float = 0.0

    def __post_init__(self):
        if self.reports_by_type is None:
            self.reports_by_type = {}
        if self.reports_by_format is None:
            self.reports_by_format = {}


class ReportingService:
    """Main service for reporting, visualization, and dashboards."""

    def __init__(
        self,
        chart_generator: ChartGenerator | None = None,
        report_generator: ReportGenerator | None = None,
        dashboard_service: DashboardService | None = None,
    ) -> None:
        self._settings = get_settings()
        self._chart_generator = chart_generator or get_chart_generator()
        self._report_generator = report_generator or get_report_generator()
        self._dashboard_service = dashboard_service or get_dashboard_service()

        # Storage
        self._reports: dict[str, Report] = {}
        self._visualizations: dict[str, Visualization] = {}

    # ===========================================
    # REPORT MANAGEMENT
    # ===========================================

    async def create_report(
        self,
        title: str,
        report_type: str = "research_summary",
        format: ReportFormat = ReportFormat.MARKDOWN,
        created_by: str = "system",
    ) -> Report:
        """Create a new report."""
        report = await self._report_generator.create_report(
            title=title,
            report_type=report_type,
            format=format,
            created_by=created_by,
        )

        self._reports[report.report_id] = report
        return report

    async def add_section(
        self,
        report_id: str,
        title: str,
        content: str,
        order: int | None = None,
        level: int = 1,
    ) -> Report:
        """Add a section to a report."""
        report = self._reports.get(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")

        await self._report_generator.add_section(
            report,
            title=title,
            content=content,
            order=order,
            level=level,
        )

        return report

    async def add_chart_to_report(
        self,
        report_id: str,
        section_index: int,
        chart: Chart,
    ) -> Report:
        """Add a chart to a report section."""
        report = self._reports.get(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")

        if section_index >= len(report.sections):
            raise ValueError(f"Section index out of range: {section_index}")

        section = report.sections[section_index]
        await self._report_generator.add_chart_to_section(section, chart)

        return report

    async def add_table_to_report(
        self,
        report_id: str,
        section_index: int,
        headers: list[str],
        rows: list[list[Any]],
        caption: str = "",
    ) -> Report:
        """Add a table to a report section."""
        report = self._reports.get(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")

        if section_index >= len(report.sections):
            raise ValueError(f"Section index out of range: {section_index}")

        section = report.sections[section_index]
        await self._report_generator.add_table_to_section(
            section,
            headers=headers,
            rows=rows,
            caption=caption,
        )

        return report

    async def generate_report(
        self,
        report_id: str,
        format: ReportFormat | None = None,
    ) -> Report:
        """Generate the final report content."""
        report = self._reports.get(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")

        return await self._report_generator.generate_report(report, format)

    async def get_report(self, report_id: str) -> Report | None:
        """Get a report by ID."""
        return self._reports.get(report_id)

    async def list_reports(
        self,
        report_type: str | None = None,
        status: ReportStatus | None = None,
        created_by: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Report]:
        """List reports with filters."""
        reports = list(self._reports.values())

        if report_type:
            reports = [r for r in reports if r.report_type == report_type]

        if status:
            reports = [r for r in reports if r.status == status]

        if created_by:
            reports = [r for r in reports if r.created_by == created_by]

        reports.sort(key=lambda r: r.created_at, reverse=True)
        return reports[offset : offset + limit]

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report."""
        if report_id in self._reports:
            del self._reports[report_id]
            return True
        return False

    # ===========================================
    # SPECIALIZED REPORTS
    # ===========================================

    async def generate_experiment_report(
        self,
        experiment_data: dict[str, Any],
        format: ReportFormat = ReportFormat.MARKDOWN,
        include_charts: bool = True,
    ) -> Report:
        """Generate a report for an experiment."""
        report = await self._report_generator.generate_experiment_report(
            experiment_data,
            include_charts=include_charts,
        )

        report.format = format
        if format != ReportFormat.MARKDOWN:
            report = await self._report_generator.generate_report(report, format)

        self._reports[report.report_id] = report
        return report

    async def generate_literature_review(
        self,
        papers: list[dict[str, Any]],
        topic: str,
        synthesis: str = "",
        format: ReportFormat = ReportFormat.MARKDOWN,
    ) -> Report:
        """Generate a literature review report."""
        report = await self._report_generator.generate_literature_review(
            papers,
            topic,
            synthesis,
        )

        report.format = format
        if format != ReportFormat.MARKDOWN:
            report = await self._report_generator.generate_report(report, format)

        self._reports[report.report_id] = report
        return report

    async def generate_progress_report(
        self,
        completed_tasks: list[dict[str, Any]],
        in_progress_tasks: list[dict[str, Any]],
        planned_tasks: list[dict[str, Any]],
        blockers: list[str] | None = None,
        format: ReportFormat = ReportFormat.MARKDOWN,
    ) -> Report:
        """Generate a progress report."""
        report = await self._report_generator.generate_progress_report(
            completed_tasks,
            in_progress_tasks,
            planned_tasks,
            blockers,
        )

        report.format = format
        if format != ReportFormat.MARKDOWN:
            report = await self._report_generator.generate_report(report, format)

        self._reports[report.report_id] = report
        return report

    # ===========================================
    # VISUALIZATION MANAGEMENT
    # ===========================================

    async def create_visualization(
        self,
        name: str,
        description: str = "",
        viz_type: str = "chart",
    ) -> Visualization:
        """Create a new visualization container."""
        viz = Visualization(
            name=name,
            description=description,
            viz_type=viz_type,
        )

        self._visualizations[viz.viz_id] = viz
        return viz

    async def create_line_chart(
        self,
        data: list[dict[str, Any]],
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        width: int | None = None,
        height: int | None = None,
    ) -> Chart:
        """Create a line chart."""
        config = ChartConfig(
            title=title,
            x_label=x_label,
            y_label=y_label,
            width=width or self._settings.default_chart_width,
            height=height or self._settings.default_chart_height,
        )

        series_list = [
            DataSeries(
                name=d.get("name", ""),
                data=d.get("data", []),
                labels=d.get("labels", []),
                color=d.get("color"),
            )
            for d in data
        ]

        return await self._chart_generator.create_line_chart(series_list, config)

    async def create_bar_chart(
        self,
        data: list[dict[str, Any]],
        title: str = "",
        horizontal: bool = False,
        width: int | None = None,
        height: int | None = None,
    ) -> Chart:
        """Create a bar chart."""
        config = ChartConfig(
            title=title,
            width=width or self._settings.default_chart_width,
            height=height or self._settings.default_chart_height,
        )

        series_list = [
            DataSeries(
                name=d.get("name", ""),
                data=d.get("data", []),
                labels=d.get("labels", []),
            )
            for d in data
        ]

        return await self._chart_generator.create_bar_chart(series_list, config, horizontal)

    async def create_scatter_plot(
        self,
        x_data: list[float],
        y_data: list[float],
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        labels: list[str] | None = None,
    ) -> Chart:
        """Create a scatter plot."""
        config = ChartConfig(
            title=title,
            x_label=x_label,
            y_label=y_label,
            width=self._settings.default_chart_width,
            height=self._settings.default_chart_height,
        )

        return await self._chart_generator.create_scatter_plot(x_data, y_data, labels, config)

    async def create_pie_chart(
        self,
        values: list[float],
        labels: list[str],
        title: str = "",
    ) -> Chart:
        """Create a pie chart."""
        config = ChartConfig(
            title=title,
            width=self._settings.default_chart_width,
            height=self._settings.default_chart_height,
        )

        return await self._chart_generator.create_pie_chart(values, labels, config)

    async def create_heatmap(
        self,
        matrix: list[list[float]],
        x_labels: list[str],
        y_labels: list[str],
        title: str = "",
    ) -> Chart:
        """Create a heatmap."""
        config = ChartConfig(
            title=title,
            width=self._settings.default_chart_width,
            height=self._settings.default_chart_height,
        )

        return await self._chart_generator.create_heatmap(matrix, x_labels, y_labels, config)

    async def create_histogram(
        self,
        values: list[float],
        bins: int = 10,
        title: str = "",
    ) -> Chart:
        """Create a histogram."""
        config = ChartConfig(
            title=title,
            width=self._settings.default_chart_width,
            height=self._settings.default_chart_height,
        )

        return await self._chart_generator.create_histogram(values, bins, config)

    async def create_box_plot(
        self,
        data_groups: dict[str, list[float]],
        title: str = "",
    ) -> Chart:
        """Create a box plot."""
        config = ChartConfig(
            title=title,
            width=self._settings.default_chart_width,
            height=self._settings.default_chart_height,
        )

        return await self._chart_generator.create_box_plot(data_groups, config)

    async def create_network_graph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        title: str = "",
    ) -> Chart:
        """Create a network graph."""
        config = ChartConfig(
            title=title,
            width=self._settings.default_chart_width,
            height=self._settings.default_chart_height,
        )

        return await self._chart_generator.create_network_graph(nodes, edges, config)

    async def create_radar_chart(
        self,
        data: dict[str, list[float]],
        categories: list[str],
        title: str = "",
    ) -> Chart:
        """Create a radar chart."""
        config = ChartConfig(
            title=title,
            width=self._settings.default_chart_width,
            height=self._settings.default_chart_height,
        )

        return await self._chart_generator.create_radar_chart(data, categories, config)

    async def add_chart_to_visualization(
        self,
        viz_id: str,
        chart: Chart,
    ) -> Visualization:
        """Add a chart to a visualization."""
        viz = self._visualizations.get(viz_id)
        if not viz:
            raise ValueError(f"Visualization not found: {viz_id}")

        viz.charts.append(chart)
        return viz

    async def get_visualization(self, viz_id: str) -> Visualization | None:
        """Get a visualization by ID."""
        return self._visualizations.get(viz_id)

    async def list_visualizations(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Visualization]:
        """List visualizations."""
        vizs = list(self._visualizations.values())
        vizs.sort(key=lambda v: v.created_at, reverse=True)
        return vizs[offset : offset + limit]

    # ===========================================
    # DASHBOARD MANAGEMENT (delegated)
    # ===========================================

    async def create_dashboard(
        self,
        name: str,
        description: str = "",
        layout: str = "two_column",
        owner: str = "system",
    ) -> Dashboard:
        """Create a new dashboard."""
        return await self._dashboard_service.create_dashboard(
            name=name,
            description=description,
            layout=layout,
            owner=owner,
        )

    async def create_dashboard_from_template(
        self,
        template_id: str,
        name: str | None = None,
        owner: str = "system",
    ) -> Dashboard:
        """Create a dashboard from a template."""
        return await self._dashboard_service.create_from_template(
            template_id=template_id,
            name=name,
            owner=owner,
        )

    async def add_metric_widget(
        self,
        dashboard_id: str,
        title: str,
        value: float,
        previous_value: float | None = None,
        format: str = "number",
        unit: str = "",
    ) -> Any:
        """Add a metric widget to a dashboard."""
        return await self._dashboard_service.add_metric_widget(
            dashboard_id=dashboard_id,
            title=title,
            value=value,
            previous_value=previous_value,
            format=format,
            unit=unit,
        )

    async def add_chart_widget(
        self,
        dashboard_id: str,
        title: str,
        chart_type: ChartType,
        data: list[dict[str, Any]],
    ) -> Any:
        """Add a chart widget to a dashboard."""
        return await self._dashboard_service.add_chart_widget(
            dashboard_id=dashboard_id,
            title=title,
            chart_type=chart_type,
            data=data,
        )

    async def add_table_widget(
        self,
        dashboard_id: str,
        title: str,
        headers: list[str],
        rows: list[list[Any]],
    ) -> Any:
        """Add a table widget to a dashboard."""
        return await self._dashboard_service.add_table_widget(
            dashboard_id=dashboard_id,
            title=title,
            headers=headers,
            rows=rows,
        )

    async def add_progress_widget(
        self,
        dashboard_id: str,
        title: str,
        current: float,
        total: float,
        label: str = "",
    ) -> Any:
        """Add a progress widget to a dashboard."""
        return await self._dashboard_service.add_progress_widget(
            dashboard_id=dashboard_id,
            title=title,
            current=current,
            total=total,
            label=label,
        )

    async def get_dashboard(self, dashboard_id: str) -> Dashboard | None:
        """Get a dashboard by ID."""
        return await self._dashboard_service.get_dashboard(dashboard_id)

    async def list_dashboards(
        self,
        owner: str | None = None,
    ) -> list[Dashboard]:
        """List dashboards."""
        return await self._dashboard_service.list_dashboards(owner=owner)

    async def refresh_dashboard(self, dashboard_id: str) -> Dashboard | None:
        """Refresh all widgets in a dashboard."""
        return await self._dashboard_service.refresh_dashboard(dashboard_id)

    async def render_dashboard_html(self, dashboard_id: str) -> str:
        """Render dashboard as HTML."""
        return await self._dashboard_service.render_dashboard_html(dashboard_id)

    async def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard."""
        return await self._dashboard_service.delete_dashboard(dashboard_id)

    async def get_dashboard_templates(self) -> list[Any]:
        """Get available dashboard templates."""
        return await self._dashboard_service.get_templates()

    # ===========================================
    # STATISTICS
    # ===========================================

    async def get_stats(self) -> ReportingStats:
        """Get reporting statistics."""
        reports = list(self._reports.values())
        dashboards = await self._dashboard_service.list_dashboards()

        stats = ReportingStats(
            total_reports=len(reports),
            reports_by_type={},
            reports_by_format={},
            total_dashboards=len(dashboards),
            total_visualizations=len(self._visualizations),
        )

        total_size = 0
        for report in reports:
            # Count by type
            stats.reports_by_type[report.report_type] = (
                stats.reports_by_type.get(report.report_type, 0) + 1
            )

            # Count by format
            stats.reports_by_format[report.format.value] = (
                stats.reports_by_format.get(report.format.value, 0) + 1
            )

            # Count by status
            if report.status == ReportStatus.COMPLETED:
                stats.completed_reports += 1
            elif report.status == ReportStatus.FAILED:
                stats.failed_reports += 1

            total_size += report.size_bytes

        if reports:
            stats.avg_report_size_bytes = total_size / len(reports)

        return stats


# Singleton instance
_service: ReportingService | None = None


def get_reporting_service() -> ReportingService:
    """Get or create reporting service singleton."""
    global _service
    if _service is None:
        _service = ReportingService()
    return _service


__all__ = [
    "ReportingStats",
    "ReportingService",
    "get_reporting_service",
]
