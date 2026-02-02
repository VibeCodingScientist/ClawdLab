"""Report Generation."""

import json
from datetime import datetime
from typing import Any

from platform.reporting.base import (
    Chart,
    Report,
    ReportFormat,
    ReportMetadata,
    ReportSection,
    ReportStatus,
    ReportTemplate,
    Visualization,
)
from platform.reporting.config import OUTPUT_FORMATS, REPORT_TYPES, get_settings
from platform.reporting.visualizations import ChartGenerator, get_chart_generator


class ReportGenerator:
    """Generates reports in various formats."""

    def __init__(
        self,
        chart_generator: ChartGenerator | None = None,
    ) -> None:
        self._settings = get_settings()
        self._chart_generator = chart_generator or get_chart_generator()
        self._templates: dict[str, ReportTemplate] = {}
        self._init_default_templates()

    def _init_default_templates(self) -> None:
        """Initialize default report templates."""
        for report_type, info in REPORT_TYPES.items():
            sections = [
                {"title": s.replace("_", " ").title(), "order": i}
                for i, s in enumerate(info.get("sections", []))
            ]
            self._templates[report_type] = ReportTemplate(
                name=info["name"],
                description=info["description"],
                report_type=report_type,
                sections=sections,
            )

    async def create_report(
        self,
        title: str,
        report_type: str = "research_summary",
        format: ReportFormat = ReportFormat.MARKDOWN,
        created_by: str = "system",
    ) -> Report:
        """Create a new report."""
        template = self._templates.get(report_type)

        report = Report(
            report_type=report_type,
            format=format,
            status=ReportStatus.DRAFT,
            created_by=created_by,
        )

        report.metadata = ReportMetadata(
            title=title,
            date=datetime.utcnow(),
        )

        # Add sections from template
        if template:
            for section_info in template.sections:
                section = ReportSection(
                    title=section_info.get("title", ""),
                    order=section_info.get("order", 0),
                )
                report.sections.append(section)

        return report

    async def add_section(
        self,
        report: Report,
        title: str,
        content: str,
        order: int | None = None,
        level: int = 1,
    ) -> ReportSection:
        """Add a section to a report."""
        section = ReportSection(
            title=title,
            content=content,
            order=order if order is not None else len(report.sections),
            level=level,
        )

        report.sections.append(section)
        report.sections.sort(key=lambda s: s.order)
        report.updated_at = datetime.utcnow()

        return section

    async def add_chart_to_section(
        self,
        section: ReportSection,
        chart: Chart,
    ) -> None:
        """Add a chart to a report section."""
        section.charts.append(chart)

    async def add_table_to_section(
        self,
        section: ReportSection,
        headers: list[str],
        rows: list[list[Any]],
        caption: str = "",
    ) -> None:
        """Add a table to a report section."""
        section.tables.append({
            "headers": headers,
            "rows": rows,
            "caption": caption,
        })

    async def generate_report(
        self,
        report: Report,
        format: ReportFormat | None = None,
    ) -> Report:
        """Generate the final report content."""
        report.status = ReportStatus.GENERATING
        output_format = format or report.format

        try:
            if output_format == ReportFormat.MARKDOWN:
                report.rendered_content = self._render_markdown(report)
            elif output_format == ReportFormat.HTML:
                report.rendered_content = self._render_html(report)
            elif output_format == ReportFormat.JSON:
                report.rendered_content = self._render_json(report)
            elif output_format == ReportFormat.LATEX:
                report.rendered_content = self._render_latex(report)
            else:
                report.rendered_content = self._render_markdown(report)

            report.format = output_format
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.utcnow()
            report.size_bytes = len(report.rendered_content.encode("utf-8"))

        except Exception as e:
            report.status = ReportStatus.FAILED
            report.metadata.custom["error"] = str(e)

        report.updated_at = datetime.utcnow()
        return report

    def _render_markdown(self, report: Report) -> str:
        """Render report as Markdown."""
        lines = []

        # Title and metadata
        meta = report.metadata
        lines.append(f"# {meta.title}")
        if meta.subtitle:
            lines.append(f"## {meta.subtitle}")
        lines.append("")

        if meta.authors:
            lines.append(f"**Authors:** {', '.join(meta.authors)}")
        lines.append(f"**Date:** {meta.date.strftime('%Y-%m-%d')}")
        if meta.version:
            lines.append(f"**Version:** {meta.version}")
        lines.append("")

        # Abstract
        if meta.abstract:
            lines.append("## Abstract")
            lines.append("")
            lines.append(meta.abstract)
            lines.append("")

        # Table of contents
        lines.append("## Table of Contents")
        lines.append("")
        for i, section in enumerate(report.sections, 1):
            indent = "  " * (section.level - 1)
            lines.append(f"{indent}{i}. [{section.title}](#{self._slugify(section.title)})")
        lines.append("")

        # Sections
        for section in report.sections:
            lines.extend(self._render_section_markdown(section))

        # Appendices
        if report.appendices:
            lines.append("# Appendices")
            lines.append("")
            for appendix in report.appendices:
                lines.extend(self._render_section_markdown(appendix))

        # References
        if meta.references:
            lines.append("## References")
            lines.append("")
            for i, ref in enumerate(meta.references, 1):
                lines.append(f"{i}. {self._format_reference(ref)}")
            lines.append("")

        # Acknowledgments
        if meta.acknowledgments:
            lines.append("## Acknowledgments")
            lines.append("")
            lines.append(meta.acknowledgments)
            lines.append("")

        return "\n".join(lines)

    def _render_section_markdown(self, section: ReportSection) -> list[str]:
        """Render a section as Markdown."""
        lines = []
        heading = "#" * (section.level + 1)

        lines.append(f"{heading} {section.title}")
        lines.append("")

        if section.content:
            lines.append(section.content)
            lines.append("")

        # Tables
        for table in section.tables:
            if table.get("caption"):
                lines.append(f"*{table['caption']}*")
                lines.append("")

            headers = table.get("headers", [])
            rows = table.get("rows", [])

            if headers:
                lines.append("| " + " | ".join(str(h) for h in headers) + " |")
                lines.append("| " + " | ".join("---" for _ in headers) + " |")

            for row in rows:
                lines.append("| " + " | ".join(str(c) for c in row) + " |")

            lines.append("")

        # Charts (as placeholders or embedded SVG)
        for chart in section.charts:
            if chart.config.title:
                lines.append(f"*Figure: {chart.config.title}*")
            if chart.rendered_svg:
                lines.append("")
                lines.append("```svg")
                lines.append(chart.rendered_svg)
                lines.append("```")
            lines.append("")

        # Subsections
        for subsection in section.subsections:
            lines.extend(self._render_section_markdown(subsection))

        return lines

    def _render_html(self, report: Report) -> str:
        """Render report as HTML."""
        meta = report.metadata

        html = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            f"  <title>{meta.title}</title>",
            "  <meta charset='UTF-8'>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            "  <style>",
            "    body { font-family: 'Georgia', serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; }",
            "    h1 { color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }",
            "    h2 { color: #555; margin-top: 30px; }",
            "    h3 { color: #666; }",
            "    .metadata { color: #666; font-size: 0.9em; margin-bottom: 20px; }",
            "    .abstract { background: #f5f5f5; padding: 15px; border-left: 3px solid #333; margin: 20px 0; }",
            "    table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "    th { background: #f5f5f5; }",
            "    .figure { text-align: center; margin: 20px 0; }",
            "    .figure-caption { font-style: italic; color: #666; }",
            "    .toc { background: #f9f9f9; padding: 15px; margin: 20px 0; }",
            "    .toc ul { list-style-type: none; padding-left: 20px; }",
            "    .references { font-size: 0.9em; }",
            "  </style>",
            "</head>",
            "<body>",
        ]

        # Title and metadata
        html.append(f"<h1>{meta.title}</h1>")
        if meta.subtitle:
            html.append(f"<h2>{meta.subtitle}</h2>")

        html.append("<div class='metadata'>")
        if meta.authors:
            html.append(f"<p><strong>Authors:</strong> {', '.join(meta.authors)}</p>")
        html.append(f"<p><strong>Date:</strong> {meta.date.strftime('%Y-%m-%d')}</p>")
        if meta.version:
            html.append(f"<p><strong>Version:</strong> {meta.version}</p>")
        html.append("</div>")

        # Abstract
        if meta.abstract:
            html.append("<div class='abstract'>")
            html.append("<h2>Abstract</h2>")
            html.append(f"<p>{meta.abstract}</p>")
            html.append("</div>")

        # Table of contents
        html.append("<div class='toc'>")
        html.append("<h2>Table of Contents</h2>")
        html.append("<ul>")
        for section in report.sections:
            html.append(f"<li><a href='#{self._slugify(section.title)}'>{section.title}</a></li>")
        html.append("</ul>")
        html.append("</div>")

        # Sections
        for section in report.sections:
            html.extend(self._render_section_html(section))

        # Appendices
        if report.appendices:
            html.append("<h1>Appendices</h1>")
            for appendix in report.appendices:
                html.extend(self._render_section_html(appendix))

        # References
        if meta.references:
            html.append("<div class='references'>")
            html.append("<h2>References</h2>")
            html.append("<ol>")
            for ref in meta.references:
                html.append(f"<li>{self._format_reference(ref)}</li>")
            html.append("</ol>")
            html.append("</div>")

        # Acknowledgments
        if meta.acknowledgments:
            html.append("<h2>Acknowledgments</h2>")
            html.append(f"<p>{meta.acknowledgments}</p>")

        html.extend(["</body>", "</html>"])

        return "\n".join(html)

    def _render_section_html(self, section: ReportSection) -> list[str]:
        """Render a section as HTML."""
        html = []
        tag = f"h{min(section.level + 1, 6)}"

        html.append(f"<{tag} id='{self._slugify(section.title)}'>{section.title}</{tag}>")

        if section.content:
            paragraphs = section.content.split("\n\n")
            for p in paragraphs:
                html.append(f"<p>{p}</p>")

        # Tables
        for table in section.tables:
            html.append("<table>")
            if table.get("caption"):
                html.append(f"<caption>{table['caption']}</caption>")

            headers = table.get("headers", [])
            rows = table.get("rows", [])

            if headers:
                html.append("<thead><tr>")
                for h in headers:
                    html.append(f"<th>{h}</th>")
                html.append("</tr></thead>")

            html.append("<tbody>")
            for row in rows:
                html.append("<tr>")
                for cell in row:
                    html.append(f"<td>{cell}</td>")
                html.append("</tr>")
            html.append("</tbody></table>")

        # Charts
        for chart in section.charts:
            html.append("<div class='figure'>")
            if chart.rendered_svg:
                html.append(chart.rendered_svg)
            if chart.config.title:
                html.append(f"<p class='figure-caption'>{chart.config.title}</p>")
            html.append("</div>")

        # Subsections
        for subsection in section.subsections:
            html.extend(self._render_section_html(subsection))

        return html

    def _render_json(self, report: Report) -> str:
        """Render report as JSON."""
        return json.dumps(report.to_dict(), indent=2)

    def _render_latex(self, report: Report) -> str:
        """Render report as LaTeX."""
        meta = report.metadata
        lines = [
            "\\documentclass{article}",
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage{graphicx}",
            "\\usepackage{booktabs}",
            "\\usepackage{hyperref}",
            "",
            f"\\title{{{self._escape_latex(meta.title)}}}",
        ]

        if meta.authors:
            lines.append(f"\\author{{{self._escape_latex(', '.join(meta.authors))}}}")

        lines.extend([
            f"\\date{{{meta.date.strftime('%B %d, %Y')}}}",
            "",
            "\\begin{document}",
            "\\maketitle",
            "",
        ])

        # Abstract
        if meta.abstract:
            lines.extend([
                "\\begin{abstract}",
                self._escape_latex(meta.abstract),
                "\\end{abstract}",
                "",
            ])

        # Table of contents
        lines.extend([
            "\\tableofcontents",
            "\\newpage",
            "",
        ])

        # Sections
        for section in report.sections:
            lines.extend(self._render_section_latex(section))

        # References
        if meta.references:
            lines.extend([
                "\\section{References}",
                "\\begin{enumerate}",
            ])
            for ref in meta.references:
                lines.append(f"\\item {self._escape_latex(self._format_reference(ref))}")
            lines.extend([
                "\\end{enumerate}",
                "",
            ])

        lines.append("\\end{document}")

        return "\n".join(lines)

    def _render_section_latex(self, section: ReportSection) -> list[str]:
        """Render a section as LaTeX."""
        lines = []
        section_cmds = ["section", "subsection", "subsubsection", "paragraph", "subparagraph"]
        cmd = section_cmds[min(section.level - 1, len(section_cmds) - 1)]

        lines.append(f"\\{cmd}{{{self._escape_latex(section.title)}}}")
        lines.append("")

        if section.content:
            lines.append(self._escape_latex(section.content))
            lines.append("")

        # Tables
        for table in section.tables:
            headers = table.get("headers", [])
            rows = table.get("rows", [])

            lines.append("\\begin{table}[h]")
            lines.append("\\centering")

            col_spec = "l" * len(headers)
            lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
            lines.append("\\toprule")

            if headers:
                lines.append(" & ".join(self._escape_latex(str(h)) for h in headers) + " \\\\")
                lines.append("\\midrule")

            for row in rows:
                lines.append(" & ".join(self._escape_latex(str(c)) for c in row) + " \\\\")

            lines.append("\\bottomrule")
            lines.append("\\end{tabular}")

            if table.get("caption"):
                lines.append(f"\\caption{{{self._escape_latex(table['caption'])}}}")

            lines.append("\\end{table}")
            lines.append("")

        # Subsections
        for subsection in section.subsections:
            lines.extend(self._render_section_latex(subsection))

        return lines

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        return text.lower().replace(" ", "-").replace("_", "-")

    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters."""
        replacements = [
            ("\\", "\\textbackslash{}"),
            ("&", "\\&"),
            ("%", "\\%"),
            ("$", "\\$"),
            ("#", "\\#"),
            ("_", "\\_"),
            ("{", "\\{"),
            ("}", "\\}"),
            ("~", "\\textasciitilde{}"),
            ("^", "\\textasciicircum{}"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    def _format_reference(self, ref: dict[str, Any]) -> str:
        """Format a reference for display."""
        authors = ref.get("authors", [])
        title = ref.get("title", "")
        year = ref.get("year", "")
        journal = ref.get("journal", "")
        doi = ref.get("doi", "")

        parts = []
        if authors:
            parts.append(", ".join(authors[:3]))
            if len(authors) > 3:
                parts[-1] += " et al."
        if year:
            parts.append(f"({year})")
        if title:
            parts.append(f'"{title}"')
        if journal:
            parts.append(f"*{journal}*")
        if doi:
            parts.append(f"DOI: {doi}")

        return " ".join(parts)

    # ===========================================
    # SPECIALIZED REPORT GENERATORS
    # ===========================================

    async def generate_experiment_report(
        self,
        experiment_data: dict[str, Any],
        include_charts: bool = True,
    ) -> Report:
        """Generate a report for an experiment."""
        report = await self.create_report(
            title=f"Experiment Report: {experiment_data.get('name', 'Untitled')}",
            report_type="experiment_report",
        )

        # Hypothesis section
        await self.add_section(
            report,
            "Hypothesis",
            self._format_hypotheses(experiment_data.get("hypotheses", [])),
            order=0,
        )

        # Design section
        await self.add_section(
            report,
            "Experimental Design",
            self._format_experiment_design(experiment_data),
            order=1,
        )

        # Execution section
        await self.add_section(
            report,
            "Execution",
            self._format_execution_details(experiment_data),
            order=2,
        )

        # Results section
        results_section = await self.add_section(
            report,
            "Results",
            self._format_results_summary(experiment_data.get("results", {})),
            order=3,
        )

        # Add charts for metrics
        if include_charts and experiment_data.get("results", {}).get("metrics"):
            metrics = experiment_data["results"]["metrics"]
            chart = await self._chart_generator.create_bar_chart(
                data=[{
                    "name": "Metrics",
                    "data": list(metrics.values()),
                    "labels": list(metrics.keys()),
                }],
            )
            await self.add_chart_to_section(results_section, chart)

        # Analysis section
        await self.add_section(
            report,
            "Analysis",
            experiment_data.get("results", {}).get("summary", "Analysis pending."),
            order=4,
        )

        return await self.generate_report(report)

    async def generate_literature_review(
        self,
        papers: list[dict[str, Any]],
        topic: str,
        synthesis: str = "",
    ) -> Report:
        """Generate a literature review report."""
        report = await self.create_report(
            title=f"Literature Review: {topic}",
            report_type="literature_review",
        )

        # Introduction
        await self.add_section(
            report,
            "Introduction",
            f"This literature review examines {len(papers)} papers related to {topic}.",
            order=0,
        )

        # Methodology
        await self.add_section(
            report,
            "Methodology",
            "Papers were collected from arXiv, PubMed, and Semantic Scholar using keyword searches.",
            order=1,
        )

        # Findings
        findings = []
        for paper in papers[:20]:  # Limit to 20 papers
            findings.append(f"- **{paper.get('title', 'Untitled')}** ({paper.get('year', 'N/A')})")
            if paper.get("abstract"):
                findings.append(f"  {paper['abstract'][:200]}...")
            findings.append("")

        await self.add_section(
            report,
            "Key Findings",
            "\n".join(findings) if findings else "No papers found.",
            order=2,
        )

        # Gaps
        await self.add_section(
            report,
            "Research Gaps",
            synthesis or "Further analysis required to identify gaps.",
            order=3,
        )

        # References
        report.metadata.references = [
            {
                "authors": p.get("authors", []),
                "title": p.get("title", ""),
                "year": p.get("year", ""),
                "doi": p.get("doi", ""),
            }
            for p in papers
        ]

        return await self.generate_report(report)

    async def generate_progress_report(
        self,
        completed_tasks: list[dict[str, Any]],
        in_progress_tasks: list[dict[str, Any]],
        planned_tasks: list[dict[str, Any]],
        blockers: list[str] | None = None,
    ) -> Report:
        """Generate a progress report."""
        report = await self.create_report(
            title="Research Progress Report",
            report_type="progress_report",
        )

        # Summary
        await self.add_section(
            report,
            "Summary",
            f"Completed: {len(completed_tasks)} | In Progress: {len(in_progress_tasks)} | Planned: {len(planned_tasks)}",
            order=0,
        )

        # Completed
        completed_text = "\n".join(
            f"- {t.get('name', 'Task')}: {t.get('status', 'done')}"
            for t in completed_tasks
        ) or "No tasks completed."
        await self.add_section(report, "Completed Tasks", completed_text, order=1)

        # In Progress
        progress_text = "\n".join(
            f"- {t.get('name', 'Task')}: {t.get('progress', 0)}% complete"
            for t in in_progress_tasks
        ) or "No tasks in progress."
        await self.add_section(report, "In Progress", progress_text, order=2)

        # Planned
        planned_text = "\n".join(
            f"- {t.get('name', 'Task')}"
            for t in planned_tasks
        ) or "No tasks planned."
        await self.add_section(report, "Planned Tasks", planned_text, order=3)

        # Blockers
        if blockers:
            blocker_text = "\n".join(f"- {b}" for b in blockers)
            await self.add_section(report, "Blockers", blocker_text, order=4)

        return await self.generate_report(report)

    def _format_hypotheses(self, hypotheses: list[dict[str, Any]]) -> str:
        """Format hypotheses for report."""
        if not hypotheses:
            return "No hypotheses specified."

        lines = []
        for i, h in enumerate(hypotheses, 1):
            lines.append(f"{i}. **{h.get('title', 'Hypothesis')}**")
            lines.append(f"   Statement: {h.get('statement', 'N/A')}")
            lines.append(f"   Status: {h.get('status', 'unknown')}")
            lines.append("")

        return "\n".join(lines)

    def _format_experiment_design(self, exp: dict[str, Any]) -> str:
        """Format experiment design details."""
        lines = [
            f"**Type:** {exp.get('experiment_type', 'N/A')}",
            f"**Domain:** {exp.get('domain', 'N/A')}",
            "",
            "**Variables:**",
        ]

        for var in exp.get("variables", []):
            lines.append(f"- {var.get('name', 'Variable')}: {var.get('type', 'unknown')}")

        lines.append("")
        lines.append("**Configuration:**")
        config = exp.get("config", {})
        if config.get("random_seed"):
            lines.append(f"- Random seed: {config['random_seed']}")
        if config.get("parameters"):
            for k, v in config["parameters"].items():
                lines.append(f"- {k}: {v}")

        return "\n".join(lines)

    def _format_execution_details(self, exp: dict[str, Any]) -> str:
        """Format execution details."""
        lines = [
            f"**Status:** {exp.get('status', 'N/A')}",
            f"**Progress:** {exp.get('progress', 0) * 100:.1f}%",
        ]

        if exp.get("started_at"):
            lines.append(f"**Started:** {exp['started_at']}")
        if exp.get("completed_at"):
            lines.append(f"**Completed:** {exp['completed_at']}")

        if exp.get("steps"):
            lines.append("")
            lines.append("**Steps:**")
            for step in exp["steps"]:
                lines.append(f"- {step.get('name', 'Step')}: {step.get('status', 'pending')}")

        return "\n".join(lines)

    def _format_results_summary(self, results: dict[str, Any]) -> str:
        """Format results summary."""
        if not results:
            return "No results available."

        lines = []

        if results.get("metrics"):
            lines.append("**Metrics:**")
            for k, v in results["metrics"].items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        if results.get("statistics"):
            lines.append("**Statistics:**")
            for k, v in results["statistics"].items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        if results.get("summary"):
            lines.append("**Summary:**")
            lines.append(results["summary"])

        return "\n".join(lines) or "Results pending analysis."


# Singleton instance
_generator: ReportGenerator | None = None


def get_report_generator() -> ReportGenerator:
    """Get or create report generator singleton."""
    global _generator
    if _generator is None:
        _generator = ReportGenerator()
    return _generator


__all__ = [
    "ReportGenerator",
    "get_report_generator",
]
