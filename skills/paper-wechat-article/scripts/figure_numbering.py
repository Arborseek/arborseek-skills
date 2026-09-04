"""Assign reader figure numbers after layout, without changing source identities."""
import re
from bs4 import BeautifulSoup


def number_figures(fragment, items):
    soup = BeautifulSoup(fragment, "html.parser")
    records = {str(item["id"]): item for item in items}
    mapping = {}
    for figure in soup.select("figure[data-visual-id]"):
        ident = figure["data-visual-id"]
        item = records[ident]
        if item.get("role") == "cover" or item.get("placement") == "cover":
            continue
        label = f"图 {len(mapping) + 1}"
        caption = figure.find("figcaption")
        text = caption.get_text(strip=True) if caption else str(item.get("alt") or "")
        # Strip only an explicit leading caption label, never numbers in prose.
        text = re.sub(r"^\s*(?:图\s*\d+[A-Za-z]?|Fig(?:ure)?\.?\s*\d+[A-Za-z]?)\s*[｜|:：·、.\-]\s*", "", text, flags=re.I)
        if caption is None:
            caption = soup.new_tag("figcaption", attrs={"class": "caption"})
            figure.append(caption)
        caption.string = label + "｜" + text
        mapping[ident] = {"article_label": label, "source_label": item.get("paper_figure", {}).get("label", "")}
    for ref in soup.select("[data-figure-ref]"):
        ident = ref["data-figure-ref"]
        if ident not in mapping:
            raise ValueError("Figure reference has no numbered, included figure: " + ident)
        ref.string = mapping[ident]["article_label"]
        del ref["data-figure-ref"]
    return str(soup), mapping
