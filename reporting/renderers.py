"""Rendus CSV / XLSX / PDF — stdlib pur, zéro dépendance.

Chaque rendu implémente la même signature :
    render(title, columns, rows, annex_lines) -> bytes
Ajouter un format = ajouter une fonction ici et l'inscrire dans
RENDERERS ; le générateur (generator.py) ne change pas. Si un format
exige plus de sophistication (graphiques Excel, mise en page PDF
complexe), remplacer l'implémentation par XlsxWriter/FPDF derrière la
même signature — le cœur ne bouge pas.

L'« Annexe de Preuve » est TOUJOURS rendue dans le fichier lui-même
(dernières lignes CSV, feuille dédiée XLSX, section finale PDF) : le
livrable et sa preuve ne peuvent pas être séparés.
"""

import csv
import io
import zipfile
import zlib
from xml.sax.saxutils import escape


def render_csv(title, columns, rows, annex_lines, summary_lines=None):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([title])
    for line in (summary_lines or []):
        writer.writerow([line])
    writer.writerow([c["label"] for c in columns])
    for row in rows:
        writer.writerow([row.get(c["key"], "") for c in columns])
    writer.writerow([])
    writer.writerow(["-- ANNEXE DE PREUVE --"])
    for line in annex_lines:
        writer.writerow([line])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _sheet_xml(rows_of_cells):
    body = []
    for r, cells in enumerate(rows_of_cells, start=1):
        cols = []
        for i, value in enumerate(cells):
            ref = f"{chr(65 + i % 26) if i < 26 else 'A' + chr(65 + i - 26)}{r}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cols.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cols.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
                            f"{escape(str(value))}</t></is></c>")
        body.append(f'<row r="{r}">{"".join(cols)}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(body)}</sheetData></worksheet>')


def render_xlsx(title, columns, rows, annex_lines, summary_lines=None):
    data_rows = [[title]] + [[line] for line in (summary_lines or [])]
    data_rows += [[c["label"] for c in columns]]
    data_rows += [[row.get(c["key"], "") for c in columns] for row in rows]
    proof_rows = [["ANNEXE DE PREUVE"]] + [[line] for line in annex_lines]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>")
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>")
        z.writestr("xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Rapport" sheetId="1" r:id="rId1"/>'
            '<sheet name="Annexe de preuve" sheetId="2" r:id="rId2"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            "</Relationships>")
        z.writestr("xl/worksheets/sheet1.xml", _sheet_xml(data_rows))
        z.writestr("xl/worksheets/sheet2.xml", _sheet_xml(proof_rows))
    return buffer.getvalue()


def _pdf_escape(text):
    text = (text.replace("—", "-").replace("–", "-").replace("’", "'")
            .replace("↔", "<->").replace("⇒", "=>"))
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _looks_numeric(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    try:
        float(str(value).replace(" ", "").replace(",", "."))
        return True
    except ValueError:
        return False


def _fmt_cell(value):
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return str(value)


NAVY, LIGHT, MID = "0.075 0.16 0.30", "0.955 0.955 0.945", "0.55 0.55 0.53"


def render_pdf(title, columns, rows, annex_lines, summary_lines=None):
    """PDF institutionnel : bandeau de couverture, synthèse, tableau réglé,
    annexe de preuve sur page dédiée, pieds de page numérotés."""
    LEFT, RIGHT, TOP, BOTTOM = 40, 555, 842, 60
    n_cols = max(len(columns), 1)
    weights = [max(len(c["label"]),
                   *( [8] + [len(_fmt_cell(r.get(c["key"], ""))) for r in rows[:60]] ))
               for c in columns]
    total_w = sum(weights) or 1
    col_x, x = [], LEFT
    for w in weights:
        col_x.append(x)
        x += (RIGHT - LEFT) * w / total_w
    col_x.append(RIGHT)
    numeric = [all(_looks_numeric(r.get(c["key"], 0)) for r in rows) if rows else False
               for c in columns]

    def header(stream, first):
        stream.append(f"{NAVY} rg {LEFT} 762 {RIGHT - LEFT} 46 re f")
        stream.append(f"BT 1 1 1 rg /F1 13 Tf {LEFT + 12} 780 Td "
                      f"({_pdf_escape(title[:78])}) Tj ET")
        stream.append(f"BT 1 1 1 rg /F3 8 Tf {LEFT + 12} 768 Td "
                      "(FINANCIAL COMMAND CENTER) Tj ET")
        return 748 if first else 748

    def footer(stream, page_no):
        stream.append(f"{MID} RG 0.5 w {LEFT} 48 m {RIGHT} 48 l S")
        stream.append(f"BT 0.35 0.35 0.33 rg /F3 7 Tf {LEFT} 38 Td "
                      "(Document genere par le Financial Command Center - "
                      "integrite verifiable via l'annexe de preuve) Tj ET")
        stream.append(f"BT 0.35 0.35 0.33 rg /F3 7 Tf {RIGHT - 40} 38 Td "
                      f"(page {page_no}) Tj ET")

    def table_header(stream, y):
        stream.append(f"0.92 0.92 0.90 rg {LEFT} {y - 14} {RIGHT - LEFT} 18 re f")
        for i, c in enumerate(columns):
            label = _pdf_escape(c["label"][:34])
            tx = col_x[i] + 4
            if numeric[i]:
                stream.append(f"BT 0 0 0 rg /F1 8 Tf {tx} {y - 9} Td ({label}) Tj ET")
            else:
                stream.append(f"BT 0 0 0 rg /F1 8 Tf {tx} {y - 9} Td ({label}) Tj ET")
        stream.append(f"{NAVY} RG 1 w {LEFT} {y - 15} m {RIGHT} {y - 15} l S")
        return y - 28

    pages_streams, stream, page_no = [], [], 1
    y = header(stream, True)
    for line in (summary_lines or []):
        stream.append(f"BT 0.15 0.15 0.14 rg /F2 9 Tf {LEFT} {y} Td "
                      f"({_pdf_escape(line[:110])}) Tj ET")
        y -= 13
    y -= 6
    y = table_header(stream, y)
    for r_i, row in enumerate(rows):
        if y < BOTTOM + 30:
            footer(stream, page_no)
            pages_streams.append(stream)
            stream, page_no = [], page_no + 1
            y = header(stream, False)
            y = table_header(stream, y)
        if r_i % 2 == 1:
            stream.append(f"{LIGHT} rg {LEFT} {y - 4} {RIGHT - LEFT} 14 re f")
        for i, c in enumerate(columns):
            text = _pdf_escape(_fmt_cell(row.get(c["key"], ""))[:38])
            if numeric[i]:
                approx = col_x[i + 1] - 4 - len(text) * 4.2
                stream.append(f"BT 0 0 0 rg /F2 8 Tf {approx:.0f} {y} Td ({text}) Tj ET")
            else:
                stream.append(f"BT 0 0 0 rg /F2 8 Tf {col_x[i] + 4} {y} Td ({text}) Tj ET")
        y -= 14
    footer(stream, page_no)
    pages_streams.append(stream)

    # Annexe de preuve : page dédiée
    stream, page_no = [], page_no + 1
    y = header(stream, False)
    stream.append(f"BT {NAVY} rg /F1 12 Tf {LEFT} {y} Td (ANNEXE DE PREUVE) Tj ET")
    y -= 8
    stream.append(f"{NAVY} RG 1 w {LEFT} {y} m {RIGHT} {y} l S")
    y -= 16
    for line in annex_lines:
        stream.append(f"BT 0.15 0.15 0.14 rg /F3 8 Tf {LEFT} {y} Td "
                      f"({_pdf_escape(line[:118])}) Tj ET")
        y -= 12
    footer(stream, page_no)
    pages_streams.append(stream)

    objects = []
    page_object_ids = [4 + 2 * i for i in range(len(pages_streams))]
    kids = " ".join(f"{oid} 0 R" for oid in page_object_ids)
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages_streams)} >>")
    objects.append("<< /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
                   "/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
                   "/F3 << /Type /Font /Subtype /Type1 /BaseFont /Courier >> >>")
    for i, page_stream in enumerate(pages_streams):
        body = "\n".join(page_stream).encode("latin-1", "replace")
        deflated = zlib.compress(body)
        objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                       f"/Resources << /Font 3 0 R >> /Contents {5 + 2 * i} 0 R >>")
        objects.append((f"<< /Length {len(deflated)} /Filter /FlateDecode >>", deflated))

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        if isinstance(obj, tuple):
            out.write(f"{i} 0 obj\n{obj[0]}\nstream\n".encode("latin-1"))
            out.write(obj[1])
            out.write(b"\nendstream\nendobj\n")
        else:
            out.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
              f"startxref\n{xref}\n%%EOF".encode("latin-1"))
    return out.getvalue()


def render_xbrl(title, columns, rows, annex_lines, summary_lines=None):
    """Instance XBRL SIMPLIFIÉE (pré-mappage DPM/EBA) : un fait par ligne,
    contexte et unité uniques. La soumission réelle exige la taxonomie
    DPM officielle — cette instance en est l'étape de pré-mappage,
    clairement marquée comme telle."""
    from xml.sax.saxutils import escape as _e
    key_col = columns[0]["key"]
    amount_col = next((c["key"] for c in columns
                       if any(isinstance(r.get(c["key"]), (int, float)) for r in rows)),
                      columns[-1]["key"])
    facts = []
    for row in rows:
        value = row.get(amount_col)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        name = "".join(ch if ch.isalnum() else "_" for ch in str(row[key_col]))
        facts.append(f'  <fcc:r{name} contextRef="ctx" unitRef="EUR" '
                     f'decimals="2">{value}</fcc:r{name}>')
    annex = "\n".join("     " + _e(line) for line in annex_lines)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- INSTANCE SIMPLIFIEE (pre-mappage DPM/EBA) - " + _e(title) + " -->\n"
        '<xbrl xmlns="http://www.xbrl.org/2003/instance"\n'
        '      xmlns:iso4217="http://www.xbrl.org/2003/iso4217"\n'
        '      xmlns:fcc="urn:fcc:reporting:pre-dpm">\n'
        '  <context id="ctx"><entity>'
        '<identifier scheme="urn:fcc">BANQUE-TEST-SA</identifier></entity>'
        "<period><instant>1970-01-01</instant></period></context>\n"
        '  <unit id="EUR"><measure>iso4217:EUR</measure></unit>\n'
        + "\n".join(facts) + "\n"
        "  <!-- ANNEXE DE PREUVE\n" + annex + "\n  -->\n"
        "</xbrl>\n")
    return xml.encode("utf-8")


RENDERERS = {"csv": render_csv, "xlsx": render_xlsx, "pdf": render_pdf,
             "xbrl": render_xbrl}
