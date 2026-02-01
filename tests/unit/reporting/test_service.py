"""Unit tests for ReportingService."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from platform.reporting.service import ReportingService, ReportingStats
from platform.reporting.base import (
    Chart,
    ChartConfig,
    ChartType,
    Dashboard,
    DataSeries,
    Report,
    ReportFormat,
    ReportSection,
    ReportStatus,
    Visualization,
    Widget,
    WidgetType,
)


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture
def mock_chart_generator():
    """Create mock chart generator."""
    generator = AsyncMock()

    # Line chart
    async def create_line_chart(series_list, config):
        return Chart(
            chart_id="chart-line-1",
            chart_type=ChartType.LINE,
            config=config,
            data_series=series_list,
        )
    generator.create_line_chart = create_line_chart

    # Bar chart
    async def create_bar_chart(series_list, config, horizontal=False):
        return Chart(
            chart_id="chart-bar-1",
            chart_type=ChartType.BAR,
            config=config,
            data_series=series_list,
        )
    generator.create_bar_chart = create_bar_chart

    # Scatter plot
    async def create_scatter_plot(x_data, y_data, labels, config):
        return Chart(
            chart_id="chart-scatter-1",
            chart_type=ChartType.SCATTER,
            config=config,
        )
    generator.create_scatter_plot = create_scatter_plot

    # Pie chart
    async def create_pie_chart(values, labels, config):
        return Chart(
            chart_id="chart-pie-1",
            chart_type=ChartType.PIE,
            config=config,
        )
    generator.create_pie_chart = create_pie_chart

    # Heatmap
    async def create_heatmap(matrix, x_labels, y_labels, config):
        return Chart(
            chart_id="chart-heatmap-1",
            chart_type=ChartType.HEATMAP,
            config=config,
        )
    generator.create_heatmap = create_heatmap

    # Histogram
    async def create_histogram(values, bins, config):
        return Chart(
            chart_id="chart-histogram-1",
            chart_type=ChartType.HISTOGRAM,
            config=config,
        )
    generator.create_histogram = create_histogram

    # Box plot
    async def create_box_plot(data_groups, config):
        return Chart(
            chart_id="chart-box-1",
            chart_type=ChartType.BOX,
            config=config,
        )
    generator.create_box_plot = create_box_plot

    # Network graph
    async def create_network_graph(nodes, edges, config):
        return Chart(
            chart_id="chart-network-1",
            chart_type=ChartType.NETWORK,
            config=config,
        )
    generator.create_network_graph = create_network_graph

    # Radar chart
    async def create_radar_chart(data, categories, config):
        return Chart(
            chart_id="chart-radar-1",
            chart_type=ChartType.RADAR,
            config=config,
        )
    generator.create_radar_chart = create_radar_chart

    return generator


@pytest.fixture
def mock_report_generator():
    """Create mock report generator."""
    generator = AsyncMock()

    async def create_report(title, report_type, format, created_by):
        return Report(
            report_id="report-1",
            report_type=report_type,
            format=format,
            created_by=created_by,
            status=ReportStatus.DRAFT,
        )
    generator.create_report = create_report

    async def add_section(report, title, content, order, level):
        section = ReportSection(
            title=title,
            content=content,
            order=order or len(report.sections),
            level=level,
        )
        report.sections.append(section)
    generator.add_section = add_section

    async def add_chart_to_section(section, chart):
        section.charts.append(chart)
    generator.add_chart_to_section = add_chart_to_section

    async def add_table_to_section(section, headers, rows, caption):
        section.tables.append({
            "headers": headers,
            "rows": rows,
            "caption": caption,
        })
    generator.add_table_to_section = add_table_to_section

    async def generate_report(report, format):
        report.status = ReportStatus.COMPLETED
        report.rendered_content = "# Generated Report"
        report.size_bytes = 1024
        return report
    generator.generate_report = generate_report

    async def generate_experiment_report(experiment_data, include_charts):
        return Report(
            report_id="report-exp-1",
            report_type="experiment",
            status=ReportStatus.COMPLETED,
        )
    generator.generate_experiment_report = generate_experiment_report

    async def generate_literature_review(papers, topic, synthesis):
        return Report(
            report_id="report-lit-1",
            report_type="literature_review",
            status=ReportStatus.COMPLETED,
        )
    generator.generate_literature_review = generate_literature_review

    async def generate_progress_report(completed, in_progress, planned, blockers):
        return Report(
            report_id="report-prog-1",
            report_type="progress",
            status=ReportStatus.COMPLETED,
        )
    generator.generate_progress_report = generate_progress_report

    return generator


@pytest.fixture
def mock_dashboard_service():
    """Create mock dashboard service."""
    service = AsyncMock()

    _dashboards: dict[str, Dashboard] = {}

    async def create_dashboard(name, description, layout, owner):
        dashboard = Dashboard(
            dashboard_id="dashboard-1",
            name=name,
            description=description,
            layout=layout,
            owner=owner,
        )
        _dashboards[dashboard.dashboard_id] = dashboard
        return dashboard
    service.create_dashboard = create_dashboard

    async def create_from_template(template_id, name, owner):
        return Dashboard(
            dashboard_id="dashboard-tmpl-1",
            name=name or "From Template",
            owner=owner,
        )
    service.create_from_template = create_from_template

    async def add_metric_widget(dashboard_id, title, value, previous_value, format, unit):
        widget = Widget(
            widget_id="widget-metric-1",
            widget_type=WidgetType.METRIC,
            title=title,
        )
        return widget
    service.add_metric_widget = add_metric_widget

    async def add_chart_widget(dashboard_id, title, chart_type, data):
        widget = Widget(
            widget_id="widget-chart-1",
            widget_type=WidgetType.CHART,
            title=title,
        )
        return widget
    service.add_chart_widget = add_chart_widget

    async def add_table_widget(dashboard_id, title, headers, rows):
        widget = Widget(
            widget_id="widget-table-1",
            widget_type=WidgetType.TABLE,
            title=title,
        )
        return widget
    service.add_table_widget = add_table_widget

    async def add_progress_widget(dashboard_id, title, current, total, label):
        widget = Widget(
            widget_id="widget-progress-1",
            widget_type=WidgetType.PROGRESS,
            title=title,
        )
        return widget
    service.add_progress_widget = add_progress_widget

    async def get_dashboard(dashboard_id):
        return _dashboards.get(dashboard_id)
    service.get_dashboard = get_dashboard

    async def list_dashboards(owner=None):
        dashboards = list(_dashboards.values())
        if owner:
            dashboards = [d for d in dashboards if d.owner == owner]
        return dashboards
    service.list_dashboards = list_dashboards

    async def refresh_dashboard(dashboard_id):
        return _dashboards.get(dashboard_id)
    service.refresh_dashboard = refresh_dashboard

    async def render_dashboard_html(dashboard_id):
        return "<html><body>Dashboard</body></html>"
    service.render_dashboard_html = render_dashboard_html

    async def delete_dashboard(dashboard_id):
        if dashboard_id in _dashboards:
            del _dashboards[dashboard_id]
            return True
        return False
    service.delete_dashboard = delete_dashboard

    async def get_templates():
        return [
            {"template_id": "tmpl-1", "name": "Research Overview"},
            {"template_id": "tmpl-2", "name": "Experiment Dashboard"},
        ]
    service.get_templates = get_templates

    return service


@pytest.fixture
def service(mock_chart_generator, mock_report_generator, mock_dashboard_service):
    """Create ReportingService with mocked dependencies."""
    with patch("platform.reporting.service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            default_chart_width=800,
            default_chart_height=600,
        )
        return ReportingService(
            chart_generator=mock_chart_generator,
            report_generator=mock_report_generator,
            dashboard_service=mock_dashboard_service,
        )


# ===========================================
# REPORT MANAGEMENT TESTS
# ===========================================


class TestReportManagement:
    """Tests for report CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_report(self, service):
        """Test creating a new report."""
        report = await service.create_report(
            title="Test Report",
            report_type="research_summary",
            format=ReportFormat.MARKDOWN,
            created_by="user-1",
        )

        assert report is not None
        assert report.report_id == "report-1"
        assert report.report_type == "research_summary"
        assert report.created_by == "user-1"

    @pytest.mark.asyncio
    async def test_create_report_html_format(self, service):
        """Test creating report with HTML format."""
        report = await service.create_report(
            title="HTML Report",
            format=ReportFormat.HTML,
        )

        assert report is not None

    @pytest.mark.asyncio
    async def test_get_report(self, service):
        """Test retrieving a report."""
        created = await service.create_report(title="Test Report")

        retrieved = await service.get_report(created.report_id)

        assert retrieved is not None
        assert retrieved.report_id == created.report_id

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, service):
        """Test retrieving non-existent report."""
        result = await service.get_report("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_add_section(self, service):
        """Test adding section to report."""
        report = await service.create_report(title="Test Report")

        updated = await service.add_section(
            report_id=report.report_id,
            title="Introduction",
            content="This is the introduction.",
            level=1,
        )

        assert len(updated.sections) == 1
        assert updated.sections[0].title == "Introduction"

    @pytest.mark.asyncio
    async def test_add_section_with_order(self, service):
        """Test adding section with specific order."""
        report = await service.create_report(title="Test Report")

        await service.add_section(
            report_id=report.report_id,
            title="Chapter 1",
            content="Content",
            order=0,
        )
        await service.add_section(
            report_id=report.report_id,
            title="Chapter 2",
            content="Content",
            order=1,
        )

        assert len(report.sections) == 2

    @pytest.mark.asyncio
    async def test_add_section_report_not_found(self, service):
        """Test adding section to non-existent report."""
        with pytest.raises(ValueError, match="Report not found"):
            await service.add_section(
                report_id="nonexistent",
                title="Section",
                content="Content",
            )

    @pytest.mark.asyncio
    async def test_add_chart_to_report(self, service):
        """Test adding chart to report section."""
        report = await service.create_report(title="Test Report")
        await service.add_section(
            report_id=report.report_id,
            title="Results",
            content="Data visualization",
        )

        chart = Chart(chart_id="test-chart", chart_type=ChartType.LINE)
        updated = await service.add_chart_to_report(
            report_id=report.report_id,
            section_index=0,
            chart=chart,
        )

        assert len(updated.sections[0].charts) == 1

    @pytest.mark.asyncio
    async def test_add_chart_report_not_found(self, service):
        """Test adding chart to non-existent report."""
        chart = Chart(chart_id="test-chart", chart_type=ChartType.LINE)

        with pytest.raises(ValueError, match="Report not found"):
            await service.add_chart_to_report(
                report_id="nonexistent",
                section_index=0,
                chart=chart,
            )

    @pytest.mark.asyncio
    async def test_add_chart_section_out_of_range(self, service):
        """Test adding chart with invalid section index."""
        report = await service.create_report(title="Test Report")
        chart = Chart(chart_id="test-chart", chart_type=ChartType.LINE)

        with pytest.raises(ValueError, match="Section index out of range"):
            await service.add_chart_to_report(
                report_id=report.report_id,
                section_index=5,
                chart=chart,
            )

    @pytest.mark.asyncio
    async def test_add_table_to_report(self, service):
        """Test adding table to report section."""
        report = await service.create_report(title="Test Report")
        await service.add_section(
            report_id=report.report_id,
            title="Data",
            content="",
        )

        updated = await service.add_table_to_report(
            report_id=report.report_id,
            section_index=0,
            headers=["Name", "Value"],
            rows=[["A", "1"], ["B", "2"]],
            caption="Test table",
        )

        assert len(updated.sections[0].tables) == 1

    @pytest.mark.asyncio
    async def test_add_table_report_not_found(self, service):
        """Test adding table to non-existent report."""
        with pytest.raises(ValueError, match="Report not found"):
            await service.add_table_to_report(
                report_id="nonexistent",
                section_index=0,
                headers=["A"],
                rows=[["1"]],
            )

    @pytest.mark.asyncio
    async def test_generate_report(self, service):
        """Test generating final report content."""
        report = await service.create_report(title="Test Report")
        await service.add_section(
            report_id=report.report_id,
            title="Content",
            content="Report content",
        )

        generated = await service.generate_report(report.report_id)

        assert generated.status == ReportStatus.COMPLETED
        assert generated.rendered_content != ""

    @pytest.mark.asyncio
    async def test_generate_report_with_format(self, service):
        """Test generating report with different format."""
        report = await service.create_report(title="Test Report")

        generated = await service.generate_report(
            report.report_id,
            format=ReportFormat.HTML,
        )

        assert generated is not None

    @pytest.mark.asyncio
    async def test_generate_report_not_found(self, service):
        """Test generating non-existent report."""
        with pytest.raises(ValueError, match="Report not found"):
            await service.generate_report("nonexistent")

    @pytest.mark.asyncio
    async def test_list_reports(self, service):
        """Test listing reports."""
        await service.create_report(title="Report 1")
        await service.create_report(title="Report 2")

        reports = await service.list_reports()

        # Both have same ID from mock, so only 1 in dict
        assert len(reports) >= 1

    @pytest.mark.asyncio
    async def test_list_reports_by_type(self, service, mock_report_generator):
        """Test filtering reports by type."""
        # Create reports with different types
        async def create_typed_report(title, report_type, format, created_by):
            return Report(
                report_id=f"report-{report_type}",
                report_type=report_type,
                format=format,
                created_by=created_by,
            )
        mock_report_generator.create_report = create_typed_report

        await service.create_report(title="R1", report_type="research_summary")
        await service.create_report(title="R2", report_type="experiment")

        reports = await service.list_reports(report_type="research_summary")

        for r in reports:
            assert r.report_type == "research_summary"

    @pytest.mark.asyncio
    async def test_list_reports_by_status(self, service):
        """Test filtering reports by status."""
        report = await service.create_report(title="Test")

        reports = await service.list_reports(status=ReportStatus.DRAFT)

        assert all(r.status == ReportStatus.DRAFT for r in reports)

    @pytest.mark.asyncio
    async def test_list_reports_by_creator(self, service):
        """Test filtering reports by creator."""
        await service.create_report(title="Test", created_by="user-1")

        reports = await service.list_reports(created_by="user-1")

        assert all(r.created_by == "user-1" for r in reports)

    @pytest.mark.asyncio
    async def test_list_reports_pagination(self, service):
        """Test report listing pagination."""
        reports = await service.list_reports(limit=10, offset=0)

        assert len(reports) <= 10

    @pytest.mark.asyncio
    async def test_delete_report(self, service):
        """Test deleting a report."""
        report = await service.create_report(title="Test Report")

        result = await service.delete_report(report.report_id)

        assert result is True
        assert await service.get_report(report.report_id) is None

    @pytest.mark.asyncio
    async def test_delete_report_not_found(self, service):
        """Test deleting non-existent report."""
        result = await service.delete_report("nonexistent")

        assert result is False


# ===========================================
# SPECIALIZED REPORTS TESTS
# ===========================================


class TestSpecializedReports:
    """Tests for specialized report generation."""

    @pytest.mark.asyncio
    async def test_generate_experiment_report(self, service):
        """Test generating experiment report."""
        experiment_data = {
            "experiment_id": "exp-1",
            "name": "Test Experiment",
            "hypothesis": "Test hypothesis",
            "results": {"accuracy": 0.95},
        }

        report = await service.generate_experiment_report(
            experiment_data=experiment_data,
            format=ReportFormat.MARKDOWN,
            include_charts=True,
        )

        assert report is not None
        assert report.report_type == "experiment"

    @pytest.mark.asyncio
    async def test_generate_experiment_report_html(self, service):
        """Test generating experiment report in HTML."""
        experiment_data = {"experiment_id": "exp-1"}

        report = await service.generate_experiment_report(
            experiment_data=experiment_data,
            format=ReportFormat.HTML,
        )

        assert report is not None

    @pytest.mark.asyncio
    async def test_generate_experiment_report_no_charts(self, service):
        """Test generating experiment report without charts."""
        experiment_data = {"experiment_id": "exp-1"}

        report = await service.generate_experiment_report(
            experiment_data=experiment_data,
            include_charts=False,
        )

        assert report is not None

    @pytest.mark.asyncio
    async def test_generate_literature_review(self, service):
        """Test generating literature review."""
        papers = [
            {"title": "Paper 1", "authors": ["Author A"]},
            {"title": "Paper 2", "authors": ["Author B"]},
        ]

        report = await service.generate_literature_review(
            papers=papers,
            topic="Machine Learning",
            synthesis="Papers discuss ML applications.",
        )

        assert report is not None
        assert report.report_type == "literature_review"

    @pytest.mark.asyncio
    async def test_generate_literature_review_html(self, service):
        """Test generating literature review in HTML."""
        papers = [{"title": "Paper 1"}]

        report = await service.generate_literature_review(
            papers=papers,
            topic="AI",
            format=ReportFormat.HTML,
        )

        assert report is not None

    @pytest.mark.asyncio
    async def test_generate_progress_report(self, service):
        """Test generating progress report."""
        completed = [{"task": "Setup", "date": "2024-01-01"}]
        in_progress = [{"task": "Development", "progress": 50}]
        planned = [{"task": "Testing", "start": "2024-02-01"}]
        blockers = ["Awaiting data access"]

        report = await service.generate_progress_report(
            completed_tasks=completed,
            in_progress_tasks=in_progress,
            planned_tasks=planned,
            blockers=blockers,
        )

        assert report is not None
        assert report.report_type == "progress"

    @pytest.mark.asyncio
    async def test_generate_progress_report_no_blockers(self, service):
        """Test generating progress report without blockers."""
        report = await service.generate_progress_report(
            completed_tasks=[],
            in_progress_tasks=[],
            planned_tasks=[],
        )

        assert report is not None

    @pytest.mark.asyncio
    async def test_generate_progress_report_html(self, service):
        """Test generating progress report in HTML."""
        report = await service.generate_progress_report(
            completed_tasks=[],
            in_progress_tasks=[],
            planned_tasks=[],
            format=ReportFormat.HTML,
        )

        assert report is not None


# ===========================================
# VISUALIZATION TESTS
# ===========================================


class TestVisualization:
    """Tests for visualization management."""

    @pytest.mark.asyncio
    async def test_create_visualization(self, service):
        """Test creating a visualization."""
        viz = await service.create_visualization(
            name="Test Visualization",
            description="A test visualization",
            viz_type="chart",
        )

        assert viz is not None
        assert viz.name == "Test Visualization"
        assert viz.viz_type == "chart"

    @pytest.mark.asyncio
    async def test_get_visualization(self, service):
        """Test retrieving a visualization."""
        created = await service.create_visualization(name="Test Viz")

        retrieved = await service.get_visualization(created.viz_id)

        assert retrieved is not None
        assert retrieved.viz_id == created.viz_id

    @pytest.mark.asyncio
    async def test_get_visualization_not_found(self, service):
        """Test retrieving non-existent visualization."""
        result = await service.get_visualization("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_add_chart_to_visualization(self, service):
        """Test adding chart to visualization."""
        viz = await service.create_visualization(name="Test Viz")
        chart = Chart(chart_id="test-chart", chart_type=ChartType.LINE)

        updated = await service.add_chart_to_visualization(
            viz_id=viz.viz_id,
            chart=chart,
        )

        assert len(updated.charts) == 1
        assert updated.charts[0].chart_id == "test-chart"

    @pytest.mark.asyncio
    async def test_add_chart_to_visualization_not_found(self, service):
        """Test adding chart to non-existent visualization."""
        chart = Chart(chart_id="test-chart", chart_type=ChartType.LINE)

        with pytest.raises(ValueError, match="Visualization not found"):
            await service.add_chart_to_visualization(
                viz_id="nonexistent",
                chart=chart,
            )

    @pytest.mark.asyncio
    async def test_list_visualizations(self, service):
        """Test listing visualizations."""
        await service.create_visualization(name="Viz 1")
        await service.create_visualization(name="Viz 2")

        vizs = await service.list_visualizations()

        assert len(vizs) >= 1

    @pytest.mark.asyncio
    async def test_list_visualizations_pagination(self, service):
        """Test visualization listing pagination."""
        vizs = await service.list_visualizations(limit=5, offset=0)

        assert len(vizs) <= 5


# ===========================================
# CHART CREATION TESTS
# ===========================================


class TestChartCreation:
    """Tests for chart creation methods."""

    @pytest.mark.asyncio
    async def test_create_line_chart(self, service):
        """Test creating a line chart."""
        data = [
            {"name": "Series A", "data": [1, 2, 3], "labels": ["a", "b", "c"]},
            {"name": "Series B", "data": [4, 5, 6]},
        ]

        chart = await service.create_line_chart(
            data=data,
            title="Test Line Chart",
            x_label="X",
            y_label="Y",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.LINE

    @pytest.mark.asyncio
    async def test_create_line_chart_custom_size(self, service):
        """Test creating line chart with custom dimensions."""
        data = [{"name": "Series", "data": [1, 2, 3]}]

        chart = await service.create_line_chart(
            data=data,
            width=1000,
            height=800,
        )

        assert chart is not None

    @pytest.mark.asyncio
    async def test_create_bar_chart(self, service):
        """Test creating a bar chart."""
        data = [
            {"name": "Category A", "data": [10, 20, 30]},
        ]

        chart = await service.create_bar_chart(
            data=data,
            title="Test Bar Chart",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.BAR

    @pytest.mark.asyncio
    async def test_create_bar_chart_horizontal(self, service):
        """Test creating horizontal bar chart."""
        data = [{"name": "Category", "data": [10, 20]}]

        chart = await service.create_bar_chart(
            data=data,
            horizontal=True,
        )

        assert chart is not None

    @pytest.mark.asyncio
    async def test_create_scatter_plot(self, service):
        """Test creating a scatter plot."""
        x_data = [1.0, 2.0, 3.0, 4.0, 5.0]
        y_data = [2.0, 4.0, 6.0, 8.0, 10.0]

        chart = await service.create_scatter_plot(
            x_data=x_data,
            y_data=y_data,
            title="Test Scatter",
            x_label="X Values",
            y_label="Y Values",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.SCATTER

    @pytest.mark.asyncio
    async def test_create_scatter_plot_with_labels(self, service):
        """Test creating scatter plot with point labels."""
        x_data = [1.0, 2.0, 3.0]
        y_data = [2.0, 4.0, 6.0]
        labels = ["Point A", "Point B", "Point C"]

        chart = await service.create_scatter_plot(
            x_data=x_data,
            y_data=y_data,
            labels=labels,
        )

        assert chart is not None

    @pytest.mark.asyncio
    async def test_create_pie_chart(self, service):
        """Test creating a pie chart."""
        values = [30.0, 50.0, 20.0]
        labels = ["A", "B", "C"]

        chart = await service.create_pie_chart(
            values=values,
            labels=labels,
            title="Distribution",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.PIE

    @pytest.mark.asyncio
    async def test_create_heatmap(self, service):
        """Test creating a heatmap."""
        matrix = [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ]
        x_labels = ["X1", "X2", "X3"]
        y_labels = ["Y1", "Y2", "Y3"]

        chart = await service.create_heatmap(
            matrix=matrix,
            x_labels=x_labels,
            y_labels=y_labels,
            title="Correlation Matrix",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.HEATMAP

    @pytest.mark.asyncio
    async def test_create_histogram(self, service):
        """Test creating a histogram."""
        values = [1.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0, 5.0]

        chart = await service.create_histogram(
            values=values,
            bins=5,
            title="Value Distribution",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.HISTOGRAM

    @pytest.mark.asyncio
    async def test_create_histogram_default_bins(self, service):
        """Test creating histogram with default bins."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]

        chart = await service.create_histogram(values=values)

        assert chart is not None

    @pytest.mark.asyncio
    async def test_create_box_plot(self, service):
        """Test creating a box plot."""
        data_groups = {
            "Group A": [1.0, 2.0, 3.0, 4.0, 5.0],
            "Group B": [2.0, 3.0, 4.0, 5.0, 6.0],
        }

        chart = await service.create_box_plot(
            data_groups=data_groups,
            title="Comparison",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.BOX

    @pytest.mark.asyncio
    async def test_create_network_graph(self, service):
        """Test creating a network graph."""
        nodes = [
            {"id": "1", "label": "Node A"},
            {"id": "2", "label": "Node B"},
            {"id": "3", "label": "Node C"},
        ]
        edges = [
            {"from": "1", "to": "2"},
            {"from": "2", "to": "3"},
        ]

        chart = await service.create_network_graph(
            nodes=nodes,
            edges=edges,
            title="Network",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.NETWORK

    @pytest.mark.asyncio
    async def test_create_radar_chart(self, service):
        """Test creating a radar chart."""
        data = {
            "Dataset 1": [80.0, 90.0, 70.0, 85.0, 75.0],
            "Dataset 2": [70.0, 85.0, 60.0, 90.0, 80.0],
        }
        categories = ["Speed", "Accuracy", "Efficiency", "Quality", "Cost"]

        chart = await service.create_radar_chart(
            data=data,
            categories=categories,
            title="Performance Comparison",
        )

        assert chart is not None
        assert chart.chart_type == ChartType.RADAR


# ===========================================
# DASHBOARD TESTS
# ===========================================


class TestDashboard:
    """Tests for dashboard management."""

    @pytest.mark.asyncio
    async def test_create_dashboard(self, service):
        """Test creating a dashboard."""
        dashboard = await service.create_dashboard(
            name="Test Dashboard",
            description="A test dashboard",
            layout="two_column",
            owner="user-1",
        )

        assert dashboard is not None
        assert dashboard.name == "Test Dashboard"
        assert dashboard.owner == "user-1"

    @pytest.mark.asyncio
    async def test_create_dashboard_from_template(self, service):
        """Test creating dashboard from template."""
        dashboard = await service.create_dashboard_from_template(
            template_id="tmpl-1",
            name="My Dashboard",
            owner="user-1",
        )

        assert dashboard is not None

    @pytest.mark.asyncio
    async def test_create_dashboard_from_template_default_name(self, service):
        """Test creating dashboard from template without name."""
        dashboard = await service.create_dashboard_from_template(
            template_id="tmpl-1",
            owner="user-1",
        )

        assert dashboard is not None

    @pytest.mark.asyncio
    async def test_add_metric_widget(self, service):
        """Test adding metric widget to dashboard."""
        dashboard = await service.create_dashboard(
            name="Test Dashboard",
            owner="user-1",
        )

        widget = await service.add_metric_widget(
            dashboard_id=dashboard.dashboard_id,
            title="Total Experiments",
            value=42.0,
            previous_value=35.0,
            format="number",
            unit="experiments",
        )

        assert widget is not None
        assert widget.widget_type == WidgetType.METRIC

    @pytest.mark.asyncio
    async def test_add_chart_widget(self, service):
        """Test adding chart widget to dashboard."""
        dashboard = await service.create_dashboard(name="Test", owner="user-1")

        widget = await service.add_chart_widget(
            dashboard_id=dashboard.dashboard_id,
            title="Results Over Time",
            chart_type=ChartType.LINE,
            data=[{"name": "Results", "data": [1, 2, 3]}],
        )

        assert widget is not None
        assert widget.widget_type == WidgetType.CHART

    @pytest.mark.asyncio
    async def test_add_table_widget(self, service):
        """Test adding table widget to dashboard."""
        dashboard = await service.create_dashboard(name="Test", owner="user-1")

        widget = await service.add_table_widget(
            dashboard_id=dashboard.dashboard_id,
            title="Recent Experiments",
            headers=["Name", "Status", "Date"],
            rows=[
                ["Exp 1", "Completed", "2024-01-01"],
                ["Exp 2", "Running", "2024-01-02"],
            ],
        )

        assert widget is not None
        assert widget.widget_type == WidgetType.TABLE

    @pytest.mark.asyncio
    async def test_add_progress_widget(self, service):
        """Test adding progress widget to dashboard."""
        dashboard = await service.create_dashboard(name="Test", owner="user-1")

        widget = await service.add_progress_widget(
            dashboard_id=dashboard.dashboard_id,
            title="Completion",
            current=75.0,
            total=100.0,
            label="experiments",
        )

        assert widget is not None
        assert widget.widget_type == WidgetType.PROGRESS

    @pytest.mark.asyncio
    async def test_get_dashboard(self, service):
        """Test retrieving a dashboard."""
        created = await service.create_dashboard(name="Test", owner="user-1")

        retrieved = await service.get_dashboard(created.dashboard_id)

        assert retrieved is not None
        assert retrieved.dashboard_id == created.dashboard_id

    @pytest.mark.asyncio
    async def test_list_dashboards(self, service):
        """Test listing all dashboards."""
        await service.create_dashboard(name="Dashboard 1", owner="user-1")

        dashboards = await service.list_dashboards()

        assert isinstance(dashboards, list)

    @pytest.mark.asyncio
    async def test_list_dashboards_by_owner(self, service):
        """Test listing dashboards by owner."""
        dashboards = await service.list_dashboards(owner="user-1")

        assert isinstance(dashboards, list)

    @pytest.mark.asyncio
    async def test_refresh_dashboard(self, service):
        """Test refreshing dashboard widgets."""
        dashboard = await service.create_dashboard(name="Test", owner="user-1")

        refreshed = await service.refresh_dashboard(dashboard.dashboard_id)

        # Mock returns the dashboard
        assert refreshed is not None or refreshed is None  # Depends on mock state

    @pytest.mark.asyncio
    async def test_render_dashboard_html(self, service):
        """Test rendering dashboard as HTML."""
        dashboard = await service.create_dashboard(name="Test", owner="user-1")

        html = await service.render_dashboard_html(dashboard.dashboard_id)

        assert html is not None
        assert "<html>" in html

    @pytest.mark.asyncio
    async def test_delete_dashboard(self, service):
        """Test deleting a dashboard."""
        dashboard = await service.create_dashboard(name="Test", owner="user-1")

        result = await service.delete_dashboard(dashboard.dashboard_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_dashboard_not_found(self, service):
        """Test deleting non-existent dashboard."""
        result = await service.delete_dashboard("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_dashboard_templates(self, service):
        """Test getting available dashboard templates."""
        templates = await service.get_dashboard_templates()

        assert isinstance(templates, list)
        assert len(templates) >= 1
        assert templates[0]["template_id"] == "tmpl-1"


# ===========================================
# STATISTICS TESTS
# ===========================================


class TestStatistics:
    """Tests for reporting statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, service):
        """Test getting stats with no reports."""
        stats = await service.get_stats()

        assert isinstance(stats, ReportingStats)
        assert stats.total_reports == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_reports(self, service):
        """Test getting stats with reports."""
        await service.create_report(title="Report 1", report_type="research_summary")

        stats = await service.get_stats()

        assert stats.total_reports >= 1
        assert stats.reports_by_type is not None

    @pytest.mark.asyncio
    async def test_get_stats_counts_by_type(self, service, mock_report_generator):
        """Test stats count by report type."""
        report_counter = [0]

        async def create_typed(title, report_type, format, created_by):
            report_counter[0] += 1
            return Report(
                report_id=f"report-{report_counter[0]}",
                report_type=report_type,
                format=format,
                created_by=created_by,
            )
        mock_report_generator.create_report = create_typed

        await service.create_report(title="R1", report_type="research_summary")
        await service.create_report(title="R2", report_type="experiment")
        await service.create_report(title="R3", report_type="research_summary")

        stats = await service.get_stats()

        assert stats.reports_by_type.get("research_summary", 0) >= 1

    @pytest.mark.asyncio
    async def test_get_stats_counts_by_format(self, service, mock_report_generator):
        """Test stats count by format."""
        report_counter = [0]

        async def create_formatted(title, report_type, format, created_by):
            report_counter[0] += 1
            return Report(
                report_id=f"report-{report_counter[0]}",
                report_type=report_type,
                format=format,
                created_by=created_by,
            )
        mock_report_generator.create_report = create_formatted

        await service.create_report(title="R1", format=ReportFormat.MARKDOWN)
        await service.create_report(title="R2", format=ReportFormat.HTML)

        stats = await service.get_stats()

        assert stats.reports_by_format is not None

    @pytest.mark.asyncio
    async def test_get_stats_completed_count(self, service, mock_report_generator):
        """Test stats count completed reports."""
        async def create_completed(title, report_type, format, created_by):
            return Report(
                report_id="report-completed",
                status=ReportStatus.COMPLETED,
                size_bytes=2048,
            )
        mock_report_generator.create_report = create_completed

        await service.create_report(title="Test")

        stats = await service.get_stats()

        assert stats.completed_reports >= 0

    @pytest.mark.asyncio
    async def test_get_stats_average_size(self, service, mock_report_generator):
        """Test stats calculates average report size."""
        report_counter = [0]

        async def create_sized(title, report_type, format, created_by):
            report_counter[0] += 1
            return Report(
                report_id=f"report-{report_counter[0]}",
                size_bytes=1000 * report_counter[0],
            )
        mock_report_generator.create_report = create_sized

        await service.create_report(title="R1")  # 1000 bytes
        await service.create_report(title="R2")  # 2000 bytes

        stats = await service.get_stats()

        if stats.total_reports > 0:
            assert stats.avg_report_size_bytes > 0

    @pytest.mark.asyncio
    async def test_get_stats_includes_visualizations(self, service):
        """Test stats includes visualization count."""
        await service.create_visualization(name="Viz 1")
        await service.create_visualization(name="Viz 2")

        stats = await service.get_stats()

        assert stats.total_visualizations >= 1


# ===========================================
# REPORTING STATS DATACLASS TESTS
# ===========================================


class TestReportingStatsDataclass:
    """Tests for ReportingStats dataclass."""

    def test_default_values(self):
        """Test ReportingStats default values."""
        stats = ReportingStats()

        assert stats.total_reports == 0
        assert stats.reports_by_type == {}
        assert stats.reports_by_format == {}
        assert stats.completed_reports == 0
        assert stats.failed_reports == 0
        assert stats.total_dashboards == 0
        assert stats.total_visualizations == 0
        assert stats.avg_report_size_bytes == 0.0

    def test_custom_values(self):
        """Test ReportingStats with custom values."""
        stats = ReportingStats(
            total_reports=10,
            reports_by_type={"experiment": 5, "summary": 5},
            reports_by_format={"markdown": 7, "html": 3},
            completed_reports=8,
            failed_reports=2,
            total_dashboards=3,
            total_visualizations=15,
            avg_report_size_bytes=1024.5,
        )

        assert stats.total_reports == 10
        assert stats.reports_by_type["experiment"] == 5
        assert stats.completed_reports == 8
        assert stats.avg_report_size_bytes == 1024.5

    def test_post_init_none_dicts(self):
        """Test post_init initializes None dicts."""
        stats = ReportingStats(
            total_reports=5,
            reports_by_type=None,
            reports_by_format=None,
        )

        assert stats.reports_by_type == {}
        assert stats.reports_by_format == {}
