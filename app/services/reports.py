from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import unicodedata

from fpdf import FPDF

from app.config import settings


@dataclass
class ReportArtifact:
    path: Path
    format: str

    @property
    def size_bytes(self) -> int:
        try:
            return self.path.stat().st_size
        except FileNotFoundError:
            return 0


def _storage_directory() -> Path:
    base = Path(settings.reports_storage_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _filename(prefix: str, extension: str, period_start: datetime, period_end: datetime) -> str:
    start_str = period_start.strftime("%Y%m%d")
    end_str = period_end.strftime("%Y%m%d")
    return f"{prefix}_{start_str}_{end_str}.{extension}"


def _build_html(summary: Dict, period_start: datetime, period_end: datetime) -> str:
    def _product_label(item: Dict) -> str:
        title = item.get("product_title")
        if title:
            return title
        pid = item.get("product_id")
        return f"Produit #{pid if pid is not None else 'N/A'}"

    top_products_html = "".join(
        f"<li>{_product_label(item)} - {item.get('units')} unites - {item.get('revenue_cents')} centimes</li>"
        for item in summary.get("top_products", [])
    )
    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8" />
    <title>Rapport ventes - {settings.project_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; }}
        h1 {{ font-size: 24px; }}
        h2 {{ font-size: 18px; margin-top: 24px; }}
        table {{ border-collapse: collapse; width: 60%; }}
        th, td {{ padding: 8px 12px; text-align: left; }}
        th {{ background-color: #f3f3f3; }}
    </style>
 </head>
 <body>
    <h1>Rapport des ventes</h1>
    <p>Periode : {period_start.strftime("%d/%m/%Y")} -> {period_end.strftime("%d/%m/%Y")}</p>
    <table border="1">
        <tr><th>Total commandes</th><td>{summary.get("total_orders")}</td></tr>
        <tr><th>Revenu total (centimes)</th><td>{summary.get("total_revenue_cents")}</td></tr>
        <tr><th>Articles vendus</th><td>{summary.get("total_items_sold")}</td></tr>
        <tr><th>Panier moyen (centimes)</th><td>{summary.get("average_order_value_cents")}</td></tr>
    </table>
    <h2>Top produits</h2>
    <ol>{top_products_html or "<li>Aucun produit</li>"}</ol>
 </body>
</html>
""".strip()


def _build_pdf(summary: Dict, period_start: datetime, period_end: datetime, destination: Path) -> None:
    def pdf_safe(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(text))
        return normalized.encode("latin-1", "ignore").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, pdf_safe(f"{settings.project_name} - Rapport des ventes"), ln=True)

    pdf.set_font("Helvetica", size=12)
    pdf.cell(
        0,
        8,
        pdf_safe(f"Periode : {period_start.strftime('%d/%m/%Y')} -> {period_end.strftime('%d/%m/%Y')}") ,
        ln=True,
    )
    pdf.ln(4)

    metrics = [
        ("Total commandes", summary.get("total_orders")),
        ("Revenu total (centimes)", summary.get("total_revenue_cents")),
        ("Articles vendus", summary.get("total_items_sold")),
        ("Panier moyen (centimes)", summary.get("average_order_value_cents")),
    ]
    for label, value in metrics:
        pdf.cell(0, 8, pdf_safe(f"{label} : {value}"), ln=True)

    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, pdf_safe("Top produits"), ln=True)

    pdf.set_font("Helvetica", size=12)
    top_products = summary.get("top_products", [])
    if not top_products:
        pdf.cell(0, 8, pdf_safe("Aucun produit"), ln=True)
    else:
        content_width = getattr(pdf, 'epw', None)
        if not content_width:
            content_width = pdf.w - pdf.l_margin - pdf.r_margin
        for rank, item in enumerate(top_products, start=1):
            label = item.get('product_title') or f"Produit #{item.get('product_id') or 'N/A'}"
            text = pdf_safe(
                f"{rank}. {label} - {item.get('units')} unites - {item.get('revenue_cents')} centimes"
            )
            pdf.multi_cell(content_width, 7, text)

    pdf.output(destination)


def generate_sales_report(summary: Dict, *, period_start: datetime, period_end: datetime) -> List[ReportArtifact]:
    storage = _storage_directory()
    html_name = _filename("sales_report", "html", period_start, period_end)
    pdf_name = _filename("sales_report", "pdf", period_start, period_end)

    html_path = storage / html_name
    pdf_path = storage / pdf_name

    html_content = _build_html(summary, period_start, period_end)
    html_path.write_text(html_content, encoding="utf-8")

    _build_pdf(summary, period_start, period_end, pdf_path)

    return [
        ReportArtifact(path=html_path, format="html"),
        ReportArtifact(path=pdf_path, format="pdf"),
    ]
