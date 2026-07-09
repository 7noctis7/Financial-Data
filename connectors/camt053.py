"""Connecteur production : relevés bancaires SWIFT ISO 20022 camt.053.

Le premier connecteur de PRODUCTION du mesh : il parse le XML camt.053
(relevé de compte de fin de journée) émis par une banque correspondante
et le traduit en batch de relevés `origin=production` — exactement le
même format que le simulateur, donc tout l'aval (réconciliation, grand
livre, rapports) fonctionne sans changement, et la règle G8 débloque
les vrais filings.

Usage :
    from connectors.camt053 import parse_camt053
    batch = parse_camt053(xml_text)          # origin=production par défaut
"""

import xml.etree.ElementTree as ET

from mesh.sources import PRODUCTION, make_batch

NS = {"c": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"}


class Camt053Error(ValueError):
    """XML intraduisible : rejeté avec sa raison, jamais deviné."""


def parse_camt053(xml_text, origin=PRODUCTION):
    """camt.053 → batch de relevés (reference, amount signé, value_date)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise Camt053Error(f"XML invalide : {exc}") from exc
    statements = root.findall(".//c:Stmt", NS)
    if not statements:
        raise Camt053Error("aucun élément Stmt trouvé (namespace camt.053.001.02 attendu)")
    records = []
    produced_at = None
    for stmt in statements:
        created = stmt.find("c:CreDtTm", NS)
        produced_at = created.text if created is not None else produced_at
        for entry in stmt.findall("c:Ntry", NS):
            amount_el = entry.find("c:Amt", NS)
            indicator = entry.find("c:CdtDbtInd", NS)
            ref = entry.find("c:NtryRef", NS)
            if ref is None:
                ref = entry.find(".//c:AcctSvcrRef", NS)
            value_date = entry.find("c:ValDt/c:Dt", NS)
            if amount_el is None or indicator is None or ref is None:
                raise Camt053Error("Ntry incomplet : Amt, CdtDbtInd et NtryRef requis")
            sign = 1 if indicator.text == "CRDT" else -1
            records.append({
                "reference": ref.text.strip(),
                "amount": {"amount": round(sign * float(amount_el.text), 2),
                           "currency": amount_el.get("Ccy")},
                "value_date": (value_date.text + "T00:00:00Z") if value_date is not None
                              else (produced_at or ""),
            })
    return make_batch("urn:fcc:treasury:cash-positions", origin,
                      produced_at or "", records)
