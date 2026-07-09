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


def render_csv(title, columns, rows, annex_lines):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([title])
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


def render_xlsx(title, columns, rows, annex_lines):
    data_rows = [[title], [c["label"] for c in columns]]
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
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def render_pdf(title, columns, rows, annex_lines):
    """PDF texte multi-pages, Helvetica/Courier, A4 portrait."""
    widths = {c["key"]: max(len(c["label"]),
                            *(len(str(r.get(c["key"], ""))) for r in rows), 4) + 2
              for c in columns} if rows else {c["key"]: len(c["label"]) + 2 for c in columns}
    lines = ["".join(c["label"].ljust(widths[c["key"]]) for c in columns),
             "".join("-" * widths[c["key"]] for c in columns)]
    lines += ["".join(str(row.get(c["key"], "")).ljust(widths[c["key"]]) for c in columns)
              for row in rows]
    lines += ["", "ANNEXE DE PREUVE", "-" * 16, *annex_lines]

    per_page = 54
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objects = []  # (numéro implicite = index + 1)
    page_object_ids = [4 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{oid} 0 R" for oid in page_object_ids)
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")                       # 1
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")  # 2
    objects.append("<< /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
                   "/F2 << /Type /Font /Subtype /Type1 /BaseFont /Courier >> >>")  # 3
    for i, page_lines in enumerate(pages):
        content = [f"BT /F1 14 Tf 40 800 Td ({_pdf_escape(title)}) Tj ET"] if i == 0 else []
        y = 780 if i == 0 else 800
        stream = [f"BT /F2 8 Tf 40 {y} Td 11 TL"]
        for line in page_lines:
            stream.append(f"({_pdf_escape(line)}) Tj T*")
        stream.append("ET")
        body = "\n".join(content + stream).encode("latin-1", "replace")
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


RENDERERS = {"csv": render_csv, "xlsx": render_xlsx, "pdf": render_pdf}
