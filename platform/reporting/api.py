"""REST API endpoints for Reporting and Visualization."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from platform.reporting.base import ChartType, ReportFormat, ReportStatus
from platform.reporting.service import get_reporting_service


router = APIRouter(prefix="/reporting", tags=["reporting"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class ReportCreateRequest(BaseModel):
    """Request to create a report."""

    title: str = Field(..., description="Report title")
    report_type: str = Field(default="research_summary", description="Type of report")
    format: str = Field(default="markdown", description="Output format")
    created_by: str = Field(default="api", description="Creator")


class SectionAddRequest(BaseModel):
    """Request to add a section."""

    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    order: int | None = Field(default=None, description="Section order")
    level: int = Field(default=1, ge=1, le=6, description="Heading level")


class TableAddRequest(BaseModel):
    """Request to add a table."""

    section_index: int = Field(..., ge=0, description="Section index")
    headers: list[str] = Field(..., description="Table headers")
    rows: list[list[Any]] = Field(..., description="Table rows")
    caption: str = Field(default="", description="Table caption")


class ChartCreateRequest(BaseModel):
    """Request to create a chart."""

    chart_type: str = Field(..., description="Chart type (line, bar, pie, etc.)")
    data: list[dict[str, Any]] = Field(..., description="Chart data")
    title: str = Field(default="", description="Chart title")
    x_label: str = Field(default="", description="X-axis label")
    y_label: str = Field(default="", description="Y-axis label")
    width: int | None = Field(default=None, description="Chart width")
    height: int | None = Field(default=None, description="Chart height")


class ScatterPlotRequest(BaseModel):
    """Request to create a scatter plot."""

    x_data: list[float] = Field(..., description="X-axis data")
    y_data: list[float] = Field(..., description="Y-axis data")
    title: str = Field(default="", description="Chart title")
    x_label: str = Field(default="", description="X-axis label")
    y_label: str = Field(default="", description="Y-axis label")
    labels: list[str] | None = Field(default=None, description="Point labels")


class HeatmapRequest(BaseModel):
    """Request to create a heatmap."""

    matrix: list[list[float]] = Field(..., description="Data matrix")
    x_labels: list[str] = Field(..., description="X-axis labels")
    y_labels: list[str] = Field(..., description="Y-axis labels")
    title: str = Field(default="", description="Chart title")


class HistogramRequest(BaseModel):
    """Request to create a histogram."""

    values: list[float] = Field(..., description="Data values")
    bins: int = Field(default=10, ge=1, le=100, description="Number of bins")
    title: str = Field(default="", description="Chart title")


class BoxPlotRequest(BaseModel):
    """Request to create a box plot."""

    data_groups: dict[str, list[float]] = Field(..., description="Data groups")
    title: str = Field(default="", description="Chart title")


class NetworkGraphRequest(BaseModel):
    """Request to create a network graph."""

    nodes: list[dict[str, Any]] = Field(..., description="Graph nodes")
    edges: list[dict[str, Any]] = Field(..., description="Graph edges")
    title: str = Field(default="", description="Chart title")


class DashboardCreateRequest(BaseModel):
    """Request to create a dashboard."""

    name: str = Field(..., description="Dashboard name")
    description: str = Field(default="", description="Dashboard description")
    layout: str = Field(default="two_column", description="Layout type")
    owner: str = Field(default="api", description="Owner")


class MetricWidgetRequest(BaseModel):
    """Request to add a metric widget."""

    title: str = Field(..., description="Widget title")
    value: float = Field(..., description="Metric value")
    previous_value: float | None = Field(default=None, description="Previous value for comparison")
    format: str = Field(default="number", description="Value format")
    unit: str = Field(default="", description="Unit")


class ChartWidgetRequest(BaseModel):
    """Request to add a chart widget."""

    title: str = Field(..., description="Widget title")
    chart_type: str = Field(..., description="Chart type")
    data: list[dict[str, Any]] = Field(..., description="Chart data")


class TableWidgetRequest(BaseModel):
    """Request to add a table widget."""

    title: str = Field(..., description="Widget title")
    headers: list[str] = Field(..., description="Table headers")
    rows: list[list[Any]] = Field(..., description="Table rows")


class ProgressWidgetRequest(BaseModel):
    """Request to add a progress widget."""

    title: str = Field(..., description="Widget title")
    current: float = Field(..., ge=0, description="Current value")
    total: float = Field(..., gt=0, description="Total value")
    label: str = Field(default="", description="Progress label")


class ExperimentReportRequest(BaseModel):
    """Request to generate an experiment report."""

    experiment_data: dict[str, Any] = Field(..., description="Experiment data")
    format: str = Field(default="markdown", description="Output format")
    include_charts: bool = Field(default=True, description="Include charts")


class LiteratureReviewRequest(BaseModel):
    """Request to generate a literature review."""

    papers: list[dict[str, Any]] = Field(..., description="Papers to review")
    topic: str = Field(..., description="Review topic")
    synthesis: str = Field(default="", description="Synthesis text")
    format: str = Field(default="markdown", description="Output format")


class ProgressReportRequest(BaseModel):
    """Request to generate a progress report."""

    completed_tasks: list[dict[str, Any]] = Field(default=[], description="Completed tasks")
    in_progress_tasks: list[dict[str, Any]] = Field(default=[], description="In-progress tasks")
    planned_tasks: list[dict[str, Any]] = Field(default=[], description="Planned tasks")
    blockers: list[str] | None = Field(default=None, description="Blockers")
    format: str = Field(default="markdown", description="Output format")


# ===========================================
# REPORT ENDPOINTS
# ===========================================


@router.post("/reports")
async def create_report(request: ReportCreateRequest):
    """Create a new report."""
    service = get_reporting_service()

    try:
        report_format = ReportFormat(request.format)
    except ValueError:
        report_format = ReportFormat.MARKDOWN

    report = await service.create_report(
        title=request.title,
        report_type=request.report_type,
        format=report_format,
        created_by=request.created_by,
    )

    return report.to_dict()


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get a report by ID."""
    service = get_reporting_service()
    report = await service.get_report(report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report.to_dict()


@router.get("/reports")
async def list_reports(
    report_type: str | None = Query(default=None, description="Filter by type"),
    status: str | None = Query(default=None, description="Filter by status"),
    created_by: str | None = Query(default=None, description="Filter by creator"),
    limit: int = Query(default=50, ge=1, le=100, description="Limit"),
    offset: int = Query(default=0, ge=0, description="Offset"),
):
    """List reports."""
    service = get_reporting_service()

    report_status = ReportStatus(status) if status else None

    reports = await service.list_reports(
        report_type=report_type,
        status=report_status,
        created_by=created_by,
        limit=limit,
        offset=offset,
    )

    return {
        "reports": [r.to_dict() for r in reports],
        "total": len(reports),
        "limit": limit,
        "offset": offset,
    }


@router.post("/reports/{report_id}/sections")
async def add_section(report_id: str, request: SectionAddRequest):
    """Add a section to a report."""
    service = get_reporting_service()

    try:
        report = await service.add_section(
            report_id=report_id,
            title=request.title,
            content=request.content,
            order=request.order,
            level=request.level,
        )
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reports/{report_id}/tables")
async def add_table(report_id: str, request: TableAddRequest):
    """Add a table to a report section."""
    service = get_reporting_service()

    try:
        report = await service.add_table_to_report(
            report_id=report_id,
            section_index=request.section_index,
            headers=request.headers,
            rows=request.rows,
            caption=request.caption,
        )
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reports/{report_id}/generate")
async def generate_report(
    report_id: str,
    format: str | None = Query(default=None, description="Output format"),
):
    """Generate the final report content."""
    service = get_reporting_service()

    try:
        report_format = ReportFormat(format) if format else None
    except ValueError:
        report_format = None

    try:
        report = await service.generate_report(report_id, format=report_format)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/reports/{report_id}/content", response_class=HTMLResponse)
async def get_report_content(report_id: str):
    """Get the rendered report content."""
    service = get_reporting_service()
    report = await service.get_report(report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if not report.rendered_content:
        raise HTTPException(status_code=400, detail="Report not yet generated")

    if report.format == ReportFormat.HTML:
        return HTMLResponse(content=report.rendered_content)
    else:
        return report.rendered_content


@router.delete("/reports/{report_id}")
async def delete_report(report_id: str):
    """Delete a report."""
    service = get_reporting_service()

    if await service.delete_report(report_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Report not found")


# ===========================================
# SPECIALIZED REPORT ENDPOINTS
# ===========================================


@router.post("/reports/experiment")
async def generate_experiment_report(request: ExperimentReportRequest):
    """Generate an experiment report."""
    service = get_reporting_service()

    try:
        report_format = ReportFormat(request.format)
    except ValueError:
        report_format = ReportFormat.MARKDOWN

    report = await service.generate_experiment_report(
        experiment_data=request.experiment_data,
        format=report_format,
        include_charts=request.include_charts,
    )

    return report.to_dict()


@router.post("/reports/literature-review")
async def generate_literature_review(request: LiteratureReviewRequest):
    """Generate a literature review report."""
    service = get_reporting_service()

    try:
        report_format = ReportFormat(request.format)
    except ValueError:
        report_format = ReportFormat.MARKDOWN

    report = await service.generate_literature_review(
        papers=request.papers,
        topic=request.topic,
        synthesis=request.synthesis,
        format=report_format,
    )

    return report.to_dict()


@router.post("/reports/progress")
async def generate_progress_report(request: ProgressReportRequest):
    """Generate a progress report."""
    service = get_reporting_service()

    try:
        report_format = ReportFormat(request.format)
    except ValueError:
        report_format = ReportFormat.MARKDOWN

    report = await service.generate_progress_report(
        completed_tasks=request.completed_tasks,
        in_progress_tasks=request.in_progress_tasks,
        planned_tasks=request.planned_tasks,
        blockers=request.blockers,
        format=report_format,
    )

    return report.to_dict()


# ===========================================
# VISUALIZATION ENDPOINTS
# ===========================================


@router.post("/charts/line")
async def create_line_chart(request: ChartCreateRequest):
    """Create a line chart."""
    service = get_reporting_service()

    chart = await service.create_line_chart(
        data=request.data,
        title=request.title,
        x_label=request.x_label,
        y_label=request.y_label,
        width=request.width,
        height=request.height,
    )

    return chart.to_dict()


@router.post("/charts/bar")
async def create_bar_chart(
    request: ChartCreateRequest,
    horizontal: bool = Query(default=False, description="Horizontal bars"),
):
    """Create a bar chart."""
    service = get_reporting_service()

    chart = await service.create_bar_chart(
        data=request.data,
        title=request.title,
        horizontal=horizontal,
        width=request.width,
        height=request.height,
    )

    return chart.to_dict()


@router.post("/charts/scatter")
async def create_scatter_plot(request: ScatterPlotRequest):
    """Create a scatter plot."""
    service = get_reporting_service()

    chart = await service.create_scatter_plot(
        x_data=request.x_data,
        y_data=request.y_data,
        title=request.title,
        x_label=request.x_label,
        y_label=request.y_label,
        labels=request.labels,
    )

    return chart.to_dict()


@router.post("/charts/pie")
async def create_pie_chart(request: ChartCreateRequest):
    """Create a pie chart."""
    service = get_reporting_service()

    data = request.data[0] if request.data else {"data": [], "labels": []}
    chart = await service.create_pie_chart(
        values=data.get("data", []),
        labels=data.get("labels", []),
        title=request.title,
    )

    return chart.to_dict()


@router.post("/charts/heatmap")
async def create_heatmap(request: HeatmapRequest):
    """Create a heatmap."""
    service = get_reporting_service()

    chart = await service.create_heatmap(
        matrix=request.matrix,
        x_labels=request.x_labels,
        y_labels=request.y_labels,
        title=request.title,
    )

    return chart.to_dict()


@router.post("/charts/histogram")
async def create_histogram(request: HistogramRequest):
    """Create a histogram."""
    service = get_reporting_service()

    chart = await service.create_histogram(
        values=request.values,
        bins=request.bins,
        title=request.title,
    )

    return chart.to_dict()


@router.post("/charts/box")
async def create_box_plot(request: BoxPlotRequest):
    """Create a box plot."""
    service = get_reporting_service()

    chart = await service.create_box_plot(
        data_groups=request.data_groups,
        title=request.title,
    )

    return chart.to_dict()


@router.post("/charts/network")
async def create_network_graph(request: NetworkGraphRequest):
    """Create a network graph."""
    service = get_reporting_service()

    chart = await service.create_network_graph(
        nodes=request.nodes,
        edges=request.edges,
        title=request.title,
    )

    return chart.to_dict()


# ===========================================
# DASHBOARD ENDPOINTS
# ===========================================


@router.post("/dashboards")
async def create_dashboard(request: DashboardCreateRequest):
    """Create a new dashboard."""
    service = get_reporting_service()

    dashboard = await service.create_dashboard(
        name=request.name,
        description=request.description,
        layout=request.layout,
        owner=request.owner,
    )

    return dashboard.to_dict()


@router.post("/dashboards/from-template/{template_id}")
async def create_dashboard_from_template(
    template_id: str,
    name: str | None = Query(default=None, description="Dashboard name"),
    owner: str = Query(default="api", description="Owner"),
):
    """Create a dashboard from a template."""
    service = get_reporting_service()

    try:
        dashboard = await service.create_dashboard_from_template(
            template_id=template_id,
            name=name,
            owner=owner,
        )
        return dashboard.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    """Get a dashboard by ID."""
    service = get_reporting_service()
    dashboard = await service.get_dashboard(dashboard_id)

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    return dashboard.to_dict()


@router.get("/dashboards/{dashboard_id}/html", response_class=HTMLResponse)
async def render_dashboard(dashboard_id: str):
    """Render a dashboard as HTML."""
    service = get_reporting_service()
    html = await service.render_dashboard_html(dashboard_id)
    return HTMLResponse(content=html)


@router.get("/dashboards")
async def list_dashboards(
    owner: str | None = Query(default=None, description="Filter by owner"),
):
    """List dashboards."""
    service = get_reporting_service()
    dashboards = await service.list_dashboards(owner=owner)
    return {"dashboards": [d.to_dict() for d in dashboards], "total": len(dashboards)}


@router.post("/dashboards/{dashboard_id}/widgets/metric")
async def add_metric_widget(dashboard_id: str, request: MetricWidgetRequest):
    """Add a metric widget to a dashboard."""
    service = get_reporting_service()

    try:
        widget = await service.add_metric_widget(
            dashboard_id=dashboard_id,
            title=request.title,
            value=request.value,
            previous_value=request.previous_value,
            format=request.format,
            unit=request.unit,
        )
        return widget.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dashboards/{dashboard_id}/widgets/chart")
async def add_chart_widget(dashboard_id: str, request: ChartWidgetRequest):
    """Add a chart widget to a dashboard."""
    service = get_reporting_service()

    try:
        chart_type = ChartType(request.chart_type)
    except ValueError:
        chart_type = ChartType.LINE

    try:
        widget = await service.add_chart_widget(
            dashboard_id=dashboard_id,
            title=request.title,
            chart_type=chart_type,
            data=request.data,
        )
        return widget.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dashboards/{dashboard_id}/widgets/table")
async def add_table_widget(dashboard_id: str, request: TableWidgetRequest):
    """Add a table widget to a dashboard."""
    service = get_reporting_service()

    try:
        widget = await service.add_table_widget(
            dashboard_id=dashboard_id,
            title=request.title,
            headers=request.headers,
            rows=request.rows,
        )
        return widget.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dashboards/{dashboard_id}/widgets/progress")
async def add_progress_widget(dashboard_id: str, request: ProgressWidgetRequest):
    """Add a progress widget to a dashboard."""
    service = get_reporting_service()

    try:
        widget = await service.add_progress_widget(
            dashboard_id=dashboard_id,
            title=request.title,
            current=request.current,
            total=request.total,
            label=request.label,
        )
        return widget.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dashboards/{dashboard_id}/refresh")
async def refresh_dashboard(dashboard_id: str):
    """Refresh all widgets in a dashboard."""
    service = get_reporting_service()
    dashboard = await service.refresh_dashboard(dashboard_id)

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    return dashboard.to_dict()


@router.delete("/dashboards/{dashboard_id}")
async def delete_dashboard(dashboard_id: str):
    """Delete a dashboard."""
    service = get_reporting_service()

    if await service.delete_dashboard(dashboard_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Dashboard not found")


@router.get("/dashboards/templates")
async def get_dashboard_templates():
    """Get available dashboard templates."""
    service = get_reporting_service()
    templates = await service.get_dashboard_templates()
    return {"templates": [t.to_dict() for t in templates]}


# ===========================================
# STATISTICS ENDPOINT
# ===========================================


@router.get("/stats")
async def get_stats():
    """Get reporting statistics."""
    service = get_reporting_service()
    stats = await service.get_stats()

    return {
        "total_reports": stats.total_reports,
        "reports_by_type": stats.reports_by_type,
        "reports_by_format": stats.reports_by_format,
        "completed_reports": stats.completed_reports,
        "failed_reports": stats.failed_reports,
        "total_dashboards": stats.total_dashboards,
        "total_visualizations": stats.total_visualizations,
        "avg_report_size_bytes": stats.avg_report_size_bytes,
    }


__all__ = ["router"]
