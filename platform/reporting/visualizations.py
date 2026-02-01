"""Chart and Visualization Generation."""

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from platform.reporting.base import (
    Chart,
    ChartConfig,
    ChartType,
    DataSeries,
    Visualization,
)
from platform.reporting.config import CHART_TYPES, COLOR_PALETTES, get_settings


class ChartGenerator:
    """Generates various types of charts and visualizations."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def get_color_palette(self, name: str | None = None) -> list[str]:
        """Get a color palette by name."""
        palette_name = name or self._settings.color_palette
        return COLOR_PALETTES.get(palette_name, COLOR_PALETTES["scientific"])

    async def create_line_chart(
        self,
        data: list[DataSeries],
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a line chart."""
        config = config or ChartConfig()
        chart = Chart(
            chart_type=ChartType.LINE,
            config=config,
            data_series=data,
        )

        # Generate SVG
        chart.rendered_svg = self._render_line_svg(data, config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_bar_chart(
        self,
        data: list[DataSeries],
        config: ChartConfig | None = None,
        horizontal: bool = False,
    ) -> Chart:
        """Create a bar chart."""
        config = config or ChartConfig()
        config.options["horizontal"] = horizontal

        chart = Chart(
            chart_type=ChartType.BAR,
            config=config,
            data_series=data,
        )

        chart.rendered_svg = self._render_bar_svg(data, config, horizontal)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_scatter_plot(
        self,
        x_data: list[float],
        y_data: list[float],
        labels: list[str] | None = None,
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a scatter plot."""
        config = config or ChartConfig()

        series = DataSeries(
            name="scatter",
            data=list(zip(x_data, y_data)),
            labels=labels or [],
        )

        chart = Chart(
            chart_type=ChartType.SCATTER,
            config=config,
            data_series=[series],
        )

        chart.rendered_svg = self._render_scatter_svg([series], config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_pie_chart(
        self,
        values: list[float],
        labels: list[str],
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a pie chart."""
        config = config or ChartConfig()

        series = DataSeries(
            name="pie",
            data=values,
            labels=labels,
        )

        chart = Chart(
            chart_type=ChartType.PIE,
            config=config,
            data_series=[series],
        )

        chart.rendered_svg = self._render_pie_svg(series, config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_heatmap(
        self,
        matrix: list[list[float]],
        x_labels: list[str],
        y_labels: list[str],
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a heatmap."""
        config = config or ChartConfig()

        chart = Chart(
            chart_type=ChartType.HEATMAP,
            config=config,
            raw_data={
                "matrix": matrix,
                "x_labels": x_labels,
                "y_labels": y_labels,
            },
        )

        chart.rendered_svg = self._render_heatmap_svg(matrix, x_labels, y_labels, config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_histogram(
        self,
        values: list[float],
        bins: int = 10,
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a histogram."""
        config = config or ChartConfig()

        # Calculate histogram bins
        bin_data = self._calculate_histogram(values, bins)

        series = DataSeries(
            name="histogram",
            data=bin_data["counts"],
            labels=[f"{b:.2f}" for b in bin_data["edges"][:-1]],
        )

        chart = Chart(
            chart_type=ChartType.HISTOGRAM,
            config=config,
            data_series=[series],
            raw_data=bin_data,
        )

        chart.rendered_svg = self._render_histogram_svg(series, bin_data, config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_box_plot(
        self,
        data_groups: dict[str, list[float]],
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a box plot."""
        config = config or ChartConfig()

        # Calculate statistics for each group
        stats = {}
        for name, values in data_groups.items():
            stats[name] = self._calculate_box_stats(values)

        chart = Chart(
            chart_type=ChartType.BOX,
            config=config,
            raw_data={"groups": data_groups, "stats": stats},
        )

        chart.rendered_svg = self._render_box_svg(stats, config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_network_graph(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a network graph visualization."""
        config = config or ChartConfig()

        chart = Chart(
            chart_type=ChartType.NETWORK,
            config=config,
            raw_data={"nodes": nodes, "edges": edges},
        )

        chart.rendered_svg = self._render_network_svg(nodes, edges, config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    async def create_radar_chart(
        self,
        data: dict[str, list[float]],
        categories: list[str],
        config: ChartConfig | None = None,
    ) -> Chart:
        """Create a radar chart."""
        config = config or ChartConfig()

        series_list = []
        for name, values in data.items():
            series_list.append(DataSeries(
                name=name,
                data=values,
                labels=categories,
            ))

        chart = Chart(
            chart_type=ChartType.RADAR,
            config=config,
            data_series=series_list,
        )

        chart.rendered_svg = self._render_radar_svg(series_list, categories, config)
        chart.rendered_html = self._wrap_in_html(chart.rendered_svg, config)

        return chart

    # ===========================================
    # SVG RENDERING METHODS
    # ===========================================

    def _render_line_svg(
        self,
        data: list[DataSeries],
        config: ChartConfig,
    ) -> str:
        """Render line chart as SVG."""
        width = config.width
        height = config.height
        padding = 60
        colors = self.get_color_palette(config.color_palette)

        # Calculate data bounds
        all_values = []
        max_len = 0
        for series in data:
            all_values.extend(series.data)
            max_len = max(max_len, len(series.data))

        min_val = min(all_values) if all_values else 0
        max_val = max(all_values) if all_values else 1
        val_range = max_val - min_val or 1

        # Start SVG
        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']

        # Background
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        # Title
        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        # Grid
        if config.show_grid:
            svg.append(self._render_grid(padding, width - padding, padding + 20, height - padding, 5, 5))

        # Axis labels
        if config.x_label:
            svg.append(f'<text x="{width/2}" y="{height - 10}" text-anchor="middle" font-size="12">{config.x_label}</text>')
        if config.y_label:
            svg.append(f'<text x="15" y="{height/2}" text-anchor="middle" font-size="12" transform="rotate(-90, 15, {height/2})">{config.y_label}</text>')

        # Plot area
        plot_width = width - 2 * padding
        plot_height = height - 2 * padding - 20

        # Draw lines
        for i, series in enumerate(data):
            color = series.color or colors[i % len(colors)]
            points = []

            for j, val in enumerate(series.data):
                x = padding + (j / max(max_len - 1, 1)) * plot_width
                y = height - padding - ((val - min_val) / val_range) * plot_height
                points.append(f"{x},{y}")

            svg.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>')

            # Data points
            for j, val in enumerate(series.data):
                x = padding + (j / max(max_len - 1, 1)) * plot_width
                y = height - padding - ((val - min_val) / val_range) * plot_height
                svg.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')

        # Legend
        if config.show_legend and len(data) > 1:
            svg.append(self._render_legend(data, colors, width - padding - 100, padding + 30))

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_bar_svg(
        self,
        data: list[DataSeries],
        config: ChartConfig,
        horizontal: bool = False,
    ) -> str:
        """Render bar chart as SVG."""
        width = config.width
        height = config.height
        padding = 60
        colors = self.get_color_palette(config.color_palette)

        # Get first series
        series = data[0] if data else DataSeries()
        values = series.data
        labels = series.labels

        max_val = max(values) if values else 1
        n_bars = len(values)

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        plot_width = width - 2 * padding
        plot_height = height - 2 * padding - 20
        bar_width = plot_width / (n_bars * 1.5) if n_bars else plot_width

        for i, val in enumerate(values):
            color = colors[i % len(colors)]
            bar_height = (val / max_val) * plot_height

            if horizontal:
                x = padding
                y = padding + 20 + i * (bar_width * 1.5)
                w = bar_height
                h = bar_width
            else:
                x = padding + i * (bar_width * 1.5) + bar_width * 0.25
                y = height - padding - bar_height
                w = bar_width
                h = bar_height

            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}"/>')

            # Label
            if i < len(labels):
                if horizontal:
                    svg.append(f'<text x="{padding - 5}" y="{y + h/2 + 4}" text-anchor="end" font-size="10">{labels[i]}</text>')
                else:
                    svg.append(f'<text x="{x + w/2}" y="{height - padding + 15}" text-anchor="middle" font-size="10">{labels[i]}</text>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_scatter_svg(
        self,
        data: list[DataSeries],
        config: ChartConfig,
    ) -> str:
        """Render scatter plot as SVG."""
        width = config.width
        height = config.height
        padding = 60
        colors = self.get_color_palette(config.color_palette)

        series = data[0] if data else DataSeries()
        points = series.data  # List of (x, y) tuples

        if not points:
            return f'<svg width="{width}" height="{height}"><text x="{width/2}" y="{height/2}">No data</text></svg>'

        x_vals = [p[0] for p in points]
        y_vals = [p[1] for p in points]

        min_x, max_x = min(x_vals), max(x_vals)
        min_y, max_y = min(y_vals), max(y_vals)
        x_range = max_x - min_x or 1
        y_range = max_y - min_y or 1

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        if config.show_grid:
            svg.append(self._render_grid(padding, width - padding, padding + 20, height - padding, 5, 5))

        plot_width = width - 2 * padding
        plot_height = height - 2 * padding - 20

        for i, (x, y) in enumerate(points):
            px = padding + ((x - min_x) / x_range) * plot_width
            py = height - padding - ((y - min_y) / y_range) * plot_height
            color = colors[0]
            svg.append(f'<circle cx="{px}" cy="{py}" r="5" fill="{color}" opacity="0.7"/>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_pie_svg(
        self,
        series: DataSeries,
        config: ChartConfig,
    ) -> str:
        """Render pie chart as SVG."""
        width = config.width
        height = config.height
        colors = self.get_color_palette(config.color_palette)

        cx, cy = width / 2, height / 2
        radius = min(width, height) / 2 - 60

        total = sum(series.data) if series.data else 1
        values = series.data
        labels = series.labels

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        start_angle = 0
        for i, val in enumerate(values):
            angle = (val / total) * 2 * math.pi
            end_angle = start_angle + angle

            x1 = cx + radius * math.cos(start_angle)
            y1 = cy + radius * math.sin(start_angle)
            x2 = cx + radius * math.cos(end_angle)
            y2 = cy + radius * math.sin(end_angle)

            large_arc = 1 if angle > math.pi else 0
            color = colors[i % len(colors)]

            path = f"M {cx},{cy} L {x1},{y1} A {radius},{radius} 0 {large_arc},1 {x2},{y2} Z"
            svg.append(f'<path d="{path}" fill="{color}" stroke="white" stroke-width="2"/>')

            # Label
            if i < len(labels):
                mid_angle = start_angle + angle / 2
                label_x = cx + (radius * 0.7) * math.cos(mid_angle)
                label_y = cy + (radius * 0.7) * math.sin(mid_angle)
                svg.append(f'<text x="{label_x}" y="{label_y}" text-anchor="middle" font-size="10" fill="white">{labels[i]}</text>')

            start_angle = end_angle

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_heatmap_svg(
        self,
        matrix: list[list[float]],
        x_labels: list[str],
        y_labels: list[str],
        config: ChartConfig,
    ) -> str:
        """Render heatmap as SVG."""
        width = config.width
        height = config.height
        padding = 80

        if not matrix:
            return f'<svg width="{width}" height="{height}"><text x="{width/2}" y="{height/2}">No data</text></svg>'

        n_rows = len(matrix)
        n_cols = len(matrix[0]) if matrix else 0

        all_vals = [v for row in matrix for v in row]
        min_val, max_val = min(all_vals), max(all_vals)
        val_range = max_val - min_val or 1

        cell_width = (width - 2 * padding) / n_cols
        cell_height = (height - 2 * padding - 20) / n_rows

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        # Color gradient (blue to red)
        for i, row in enumerate(matrix):
            for j, val in enumerate(row):
                intensity = (val - min_val) / val_range
                r = int(255 * intensity)
                b = int(255 * (1 - intensity))
                color = f"rgb({r}, 0, {b})"

                x = padding + j * cell_width
                y = padding + 20 + i * cell_height

                svg.append(f'<rect x="{x}" y="{y}" width="{cell_width}" height="{cell_height}" fill="{color}"/>')

        # X labels
        for j, label in enumerate(x_labels[:n_cols]):
            x = padding + j * cell_width + cell_width / 2
            svg.append(f'<text x="{x}" y="{height - padding + 15}" text-anchor="middle" font-size="10">{label}</text>')

        # Y labels
        for i, label in enumerate(y_labels[:n_rows]):
            y = padding + 20 + i * cell_height + cell_height / 2
            svg.append(f'<text x="{padding - 5}" y="{y + 4}" text-anchor="end" font-size="10">{label}</text>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_histogram_svg(
        self,
        series: DataSeries,
        bin_data: dict[str, Any],
        config: ChartConfig,
    ) -> str:
        """Render histogram as SVG."""
        width = config.width
        height = config.height
        padding = 60
        colors = self.get_color_palette(config.color_palette)

        counts = bin_data["counts"]
        edges = bin_data["edges"]
        max_count = max(counts) if counts else 1

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        plot_width = width - 2 * padding
        plot_height = height - 2 * padding - 20
        bar_width = plot_width / len(counts) if counts else plot_width

        for i, count in enumerate(counts):
            bar_height = (count / max_count) * plot_height
            x = padding + i * bar_width
            y = height - padding - bar_height

            svg.append(f'<rect x="{x}" y="{y}" width="{bar_width - 1}" height="{bar_height}" fill="{colors[0]}"/>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_box_svg(
        self,
        stats: dict[str, dict[str, float]],
        config: ChartConfig,
    ) -> str:
        """Render box plot as SVG."""
        width = config.width
        height = config.height
        padding = 60
        colors = self.get_color_palette(config.color_palette)

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        # Calculate bounds
        all_vals = []
        for s in stats.values():
            all_vals.extend([s["min"], s["max"]])
        min_val, max_val = min(all_vals), max(all_vals)
        val_range = max_val - min_val or 1

        plot_width = width - 2 * padding
        plot_height = height - 2 * padding - 20
        n_groups = len(stats)
        box_width = plot_width / (n_groups * 2) if n_groups else plot_width

        for i, (name, s) in enumerate(stats.items()):
            x = padding + i * (box_width * 2) + box_width / 2
            color = colors[i % len(colors)]

            # Scale y values
            def y_scale(val: float) -> float:
                return height - padding - ((val - min_val) / val_range) * plot_height

            y_min = y_scale(s["min"])
            y_q1 = y_scale(s["q1"])
            y_median = y_scale(s["median"])
            y_q3 = y_scale(s["q3"])
            y_max = y_scale(s["max"])

            # Whiskers
            svg.append(f'<line x1="{x + box_width/2}" y1="{y_min}" x2="{x + box_width/2}" y2="{y_q1}" stroke="{color}" stroke-width="2"/>')
            svg.append(f'<line x1="{x + box_width/2}" y1="{y_q3}" x2="{x + box_width/2}" y2="{y_max}" stroke="{color}" stroke-width="2"/>')

            # Box
            svg.append(f'<rect x="{x}" y="{y_q3}" width="{box_width}" height="{y_q1 - y_q3}" fill="{color}" opacity="0.5" stroke="{color}" stroke-width="2"/>')

            # Median line
            svg.append(f'<line x1="{x}" y1="{y_median}" x2="{x + box_width}" y2="{y_median}" stroke="{color}" stroke-width="3"/>')

            # Label
            svg.append(f'<text x="{x + box_width/2}" y="{height - padding + 15}" text-anchor="middle" font-size="10">{name}</text>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_network_svg(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        config: ChartConfig,
    ) -> str:
        """Render network graph as SVG."""
        width = config.width
        height = config.height
        colors = self.get_color_palette(config.color_palette)

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        # Simple force-directed layout simulation
        node_positions = self._calculate_network_layout(nodes, edges, width, height)

        # Draw edges
        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            if source in node_positions and target in node_positions:
                x1, y1 = node_positions[source]
                x2, y2 = node_positions[target]
                svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#999" stroke-width="1" opacity="0.6"/>')

        # Draw nodes
        for i, node in enumerate(nodes):
            node_id = node.get("id", str(i))
            if node_id in node_positions:
                x, y = node_positions[node_id]
                color = colors[i % len(colors)]
                size = node.get("size", 10)

                svg.append(f'<circle cx="{x}" cy="{y}" r="{size}" fill="{color}"/>')

                label = node.get("label", node_id)
                svg.append(f'<text x="{x}" y="{y + size + 12}" text-anchor="middle" font-size="10">{label}</text>')

        svg.append('</svg>')
        return '\n'.join(svg)

    def _render_radar_svg(
        self,
        data: list[DataSeries],
        categories: list[str],
        config: ChartConfig,
    ) -> str:
        """Render radar chart as SVG."""
        width = config.width
        height = config.height
        colors = self.get_color_palette(config.color_palette)

        cx, cy = width / 2, height / 2
        radius = min(width, height) / 2 - 80
        n = len(categories)

        svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')

        if config.title:
            svg.append(f'<text x="{width/2}" y="25" text-anchor="middle" font-size="16" font-weight="bold">{config.title}</text>')

        # Draw grid circles
        for i in range(1, 6):
            r = radius * i / 5
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#ddd" stroke-width="1"/>')

        # Draw axis lines and labels
        for i, cat in enumerate(categories):
            angle = (i / n) * 2 * math.pi - math.pi / 2
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            svg.append(f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="#ddd" stroke-width="1"/>')

            label_x = cx + (radius + 20) * math.cos(angle)
            label_y = cy + (radius + 20) * math.sin(angle)
            svg.append(f'<text x="{label_x}" y="{label_y}" text-anchor="middle" font-size="10">{cat}</text>')

        # Draw data polygons
        for j, series in enumerate(data):
            color = series.color or colors[j % len(colors)]
            max_val = max(series.data) if series.data else 1
            points = []

            for i, val in enumerate(series.data):
                angle = (i / n) * 2 * math.pi - math.pi / 2
                r = radius * (val / max_val)
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                points.append(f"{x},{y}")

            svg.append(f'<polygon points="{" ".join(points)}" fill="{color}" fill-opacity="0.3" stroke="{color}" stroke-width="2"/>')

        svg.append('</svg>')
        return '\n'.join(svg)

    # ===========================================
    # HELPER METHODS
    # ===========================================

    def _render_grid(
        self,
        x1: float,
        x2: float,
        y1: float,
        y2: float,
        x_lines: int,
        y_lines: int,
    ) -> str:
        """Render grid lines."""
        lines = ['<g class="grid" stroke="#eee" stroke-width="1">']

        for i in range(x_lines + 1):
            x = x1 + (x2 - x1) * i / x_lines
            lines.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}"/>')

        for i in range(y_lines + 1):
            y = y1 + (y2 - y1) * i / y_lines
            lines.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}"/>')

        lines.append('</g>')
        return '\n'.join(lines)

    def _render_legend(
        self,
        data: list[DataSeries],
        colors: list[str],
        x: float,
        y: float,
    ) -> str:
        """Render chart legend."""
        lines = [f'<g class="legend" transform="translate({x}, {y})">']

        for i, series in enumerate(data):
            color = series.color or colors[i % len(colors)]
            cy = i * 20
            lines.append(f'<rect x="0" y="{cy}" width="15" height="15" fill="{color}"/>')
            lines.append(f'<text x="20" y="{cy + 12}" font-size="12">{series.name}</text>')

        lines.append('</g>')
        return '\n'.join(lines)

    def _wrap_in_html(self, svg: str, config: ChartConfig) -> str:
        """Wrap SVG in HTML with optional interactivity."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{config.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .chart-container {{ display: inline-block; }}
    </style>
</head>
<body>
    <div class="chart-container">
        {svg}
    </div>
</body>
</html>"""
        return html

    def _calculate_histogram(self, values: list[float], bins: int) -> dict[str, Any]:
        """Calculate histogram bins."""
        if not values:
            return {"counts": [], "edges": []}

        min_val, max_val = min(values), max(values)
        bin_width = (max_val - min_val) / bins if max_val != min_val else 1

        edges = [min_val + i * bin_width for i in range(bins + 1)]
        counts = [0] * bins

        for val in values:
            bin_idx = min(int((val - min_val) / bin_width), bins - 1)
            counts[bin_idx] += 1

        return {"counts": counts, "edges": edges}

    def _calculate_box_stats(self, values: list[float]) -> dict[str, float]:
        """Calculate box plot statistics."""
        sorted_vals = sorted(values)
        n = len(sorted_vals)

        return {
            "min": sorted_vals[0] if n else 0,
            "q1": sorted_vals[n // 4] if n else 0,
            "median": sorted_vals[n // 2] if n else 0,
            "q3": sorted_vals[3 * n // 4] if n else 0,
            "max": sorted_vals[-1] if n else 0,
            "mean": sum(sorted_vals) / n if n else 0,
        }

    def _calculate_network_layout(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        width: float,
        height: float,
    ) -> dict[str, tuple[float, float]]:
        """Calculate simple network layout positions."""
        positions = {}
        n = len(nodes)

        # Simple circular layout
        cx, cy = width / 2, height / 2
        radius = min(width, height) / 2 - 100

        for i, node in enumerate(nodes):
            angle = (i / n) * 2 * math.pi
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            positions[node.get("id", str(i))] = (x, y)

        return positions


# Singleton instance
_chart_generator: ChartGenerator | None = None


def get_chart_generator() -> ChartGenerator:
    """Get or create chart generator singleton."""
    global _chart_generator
    if _chart_generator is None:
        _chart_generator = ChartGenerator()
    return _chart_generator


__all__ = [
    "ChartGenerator",
    "get_chart_generator",
]
