"""
Assistente de preparacao para Cheffenia Hard.

Ele nao integra nada no bot sozinho. A ideia e manter um banco revisavel de MVPs
da Cheffenia Hard para depois gerar dataset sintetico, classes YOLO e switches
de elemento com seguranca.

Usos:
  python ro_cheffenia_assist.py --refresh --enrich --write-yaml
  python ro_cheffenia_assist.py --status
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from urllib.request import Request, urlopen


CHEFFENIA_URL = "https://wiki.ragna4th.com/Cheffenia"
DEFAULT_DB = os.path.join("data", "cheffenia_hard_mobs.json")
DEFAULT_YAML = os.path.join("datasets", "ro_mob", "cheffenia_hard_dataset.yaml")

HARD_MOBS_PT = [
    "Abelha-Rainha", "Atroce", "Boitata", "Cavaleiro da Tempestade",
    "Detale", "Doppelganger", "Dracula", "Drake", "Eddga",
    "Egnigem Cenia", "Tao Gunka", "Farao", "Flor do Luar", "Freeoni",
    "General Tartaruga", "Gorynych", "Hatii", "Senhor dos Mortos",
    "Lady Branca", "Lady Tanee", "Leak", "Maya", "Memoria de Thanatos",
    "Senhor das Trevas", "Orc Heroi", "Osiris", "Samurai Encarnado",
    "RSX-0806", "Senhor dos Orcs", "GTB", "Vesper", "Amon Ra",
    "Kraken", "Kiel-D-01", "Valquiria Randgris", "Rainha Scaraba",
    "Belzebu", "Gioia", "Ifrit", "Gertie", "Flamel", "Kathryne",
    "Seyren", "Eremes", "Vigia do Tempo",
]

ELEMENT_PRIORITY = {
    "neutral": "neutral",
    "water": "wind",
    "earth": "fire",
    "fire": "water",
    "wind": "earth",
    "poison": "fire",
    "holy": "dark",
    "dark": "holy",
    "ghost": "ghost",
    "undead": "holy",
}

ELEMENTS = [
    "neutral", "water", "earth", "fire", "wind",
    "poison", "holy", "dark", "ghost", "undead",
]


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def norm(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def slugify(text):
    text = norm(text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def fetch_text(url, timeout=20):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 ro-cheffenia-assist"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href", "")
        if "divine-pride.net/database/monster/" in href:
            self._href = href
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            text = " ".join(self._text).strip()
            if text:
                self.links.append((text, self._href))
            self._href = None
            self._text = []


class TextLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href", "")
            self._text = []

    def handle_data(self, data):
        if data.strip():
            self.text.append(data.strip())
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((" ".join(self._text).strip(), self._href))
            self._href = None
            self._text = []


def absolute_url(url):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.divine-pride.net" + url
    return url


def monster_id_from_url(url):
    m = re.search(r"/database/monster/(\d+)", url)
    return int(m.group(1)) if m else None


def blank_db():
    mobs = []
    for i, name_pt in enumerate(HARD_MOBS_PT):
        mobs.append({
            "class_id": i,
            "class_name": slugify(name_pt),
            "name_pt": name_pt,
            "divine_name": "",
            "divine_pride_id": None,
            "divine_pride_url": "",
            "spritesheet_url": "",
            "race": "",
            "size": "",
            "element": "",
            "element_level": None,
            "recommended_attack_element": "",
            "switch_key": "",
            "enabled": True,
            "reviewed": False,
            "notes": "",
        })
    return {
        "profile": "cheffenia_hard",
        "source": {
            "wiki": CHEFFENIA_URL,
            "notes": "Seed preparado para assistencia; revise antes de treinar/usar switch.",
        },
        "generated_at": now_iso(),
        "switch_slots": {element: "" for element in ELEMENTS},
        "mobs": mobs,
    }


def load_db(path):
    if not os.path.exists(path):
        return blank_db()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
        f.write("\n")


def refresh_from_wiki(db):
    html = fetch_text(CHEFFENIA_URL)
    parser = LinkParser()
    parser.feed(html)
    links_by_name = {}
    for text, href in parser.links:
        links_by_name.setdefault(norm(text), absolute_url(href))

    missing = []
    for mob in db["mobs"]:
        url = links_by_name.get(norm(mob["name_pt"]))
        if not url:
            missing.append(mob["name_pt"])
            continue
        mob["divine_pride_url"] = url
        mob["divine_pride_id"] = monster_id_from_url(url)
    db["source"]["wiki_refreshed_at"] = now_iso()
    return missing


def parse_divine_monster(html):
    parser = TextLinkParser()
    parser.feed(html)
    text_blob = "\n".join(parser.text)
    flat = " ".join(parser.text)

    title_match = re.search(r"Divine Pride\s*-\s*Monster\s*-\s*([^<\n\r]+)", html)
    divine_name = title_match.group(1).strip() if title_match else ""

    info = re.search(
        r"\b(Formless|Undead|Brute|Plant|Insect|Fish|Demon|Demi-Human|Human|Angel|Dragon)\s+"
        r"(Small|Medium|Large)\s+"
        r"(Neutral|Water|Earth|Fire|Wind|Poison|Holy|Dark|Ghost|Undead)\s+([1-4])\b",
        flat,
        flags=re.IGNORECASE,
    )

    spritesheet_url = ""
    for label, href in parser.links:
        if "spritesheet" in norm(label) or "spritesheet" in href.lower():
            spritesheet_url = absolute_url(href)
            break
    if not spritesheet_url:
        m = re.search(r"https?://static\.divine-pride\.net/[^\"' <]+", text_blob)
        if m:
            spritesheet_url = m.group(0)

    data = {"divine_name": divine_name, "spritesheet_url": spritesheet_url}
    if info:
        race, size, element, level = info.groups()
        element_key = element.lower()
        data.update({
            "race": race.lower(),
            "size": size.lower(),
            "element": element_key,
            "element_level": int(level),
            "recommended_attack_element": ELEMENT_PRIORITY.get(element_key, ""),
        })
    return data


def enrich_from_divine(db):
    errors = []
    for mob in db["mobs"]:
        url = mob.get("divine_pride_url")
        if not url:
            errors.append((mob["name_pt"], "sem URL Divine Pride"))
            continue
        try:
            data = parse_divine_monster(fetch_text(url))
        except Exception as exc:
            errors.append((mob["name_pt"], str(exc)))
            continue
        for key, value in data.items():
            if value not in ("", None):
                mob[key] = value
    db["source"]["divine_enriched_at"] = now_iso()
    return errors


def write_yolo_yaml(db, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "path: datasets/ro_mob",
        "train: images/train",
        "val: images/val",
        "",
        "names:",
    ]
    for mob in db["mobs"]:
        if mob.get("enabled", True):
            lines.append(f"  {mob['class_id']}: {mob['class_name']}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_status(db):
    mobs = db["mobs"]
    total = len(mobs)
    ids = sum(1 for m in mobs if m.get("divine_pride_id"))
    elem = sum(1 for m in mobs if m.get("element"))
    sprites = sum(1 for m in mobs if m.get("spritesheet_url"))
    reviewed = sum(1 for m in mobs if m.get("reviewed"))
    print(f"Perfil: {db.get('profile', '')}")
    print(f"Mobs: {total}")
    print(f"Com Divine ID: {ids}/{total}")
    print(f"Com elemento: {elem}/{total}")
    print(f"Com spritesheet: {sprites}/{total}")
    print(f"Revisados: {reviewed}/{total}")
    missing = [m["name_pt"] for m in mobs if not m.get("element")]
    if missing:
        print()
        print("Ainda sem elemento:")
        for name in missing[:20]:
            print(f"  - {name}")
        if len(missing) > 20:
            print(f"  ... +{len(missing) - 20}")


def main():
    ap = argparse.ArgumentParser(description="Preparar banco assistido da Cheffenia Hard")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--refresh", action="store_true", help="Busca links/IDs na wiki Ragna4th")
    ap.add_argument("--enrich", action="store_true", help="Busca elemento/spritesheet no Divine Pride")
    ap.add_argument("--write-yaml", action="store_true", help="Gera YAML com classes YOLO da Cheffenia")
    ap.add_argument("--yaml", default=DEFAULT_YAML)
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    db = load_db(args.db)
    changed = not os.path.exists(args.db)

    if args.refresh:
        missing = refresh_from_wiki(db)
        changed = True
        if missing:
            print("Nao encontrei link na wiki para:")
            for name in missing:
                print(f"  - {name}")

    if args.enrich:
        errors = enrich_from_divine(db)
        changed = True
        if errors:
            print("Falhas ao enriquecer:")
            for name, err in errors[:20]:
                print(f"  - {name}: {err}")

    if changed:
        save_db(db, args.db)
        print(f"Banco salvo em: {args.db}")

    if args.write_yaml:
        write_yolo_yaml(db, args.yaml)
        print(f"YAML YOLO salvo em: {args.yaml}")

    if args.status or not any([args.refresh, args.enrich, args.write_yaml]):
        print_status(db)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido.")
        sys.exit(130)
