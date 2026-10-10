#!/usr/bin/env python3
"""Insert, update, or remove the WeRead entry in an EmulationStation gamelist."""
from pathlib import Path
import argparse
import os
import tempfile
from xml.etree import ElementTree as ET


PATH_VALUES = {"./Weread.sh", "Weread.sh"}


def _entry_values(fragment_bytes):
    root = ET.fromstring(fragment_bytes)
    if root.tag != "game":
        raise ValueError("fragment root must be <game>")
    values = {child.tag: child.text or "" for child in root}
    required = {"path", "name", "desc", "image"}
    missing = required.difference(values)
    if missing:
        raise ValueError("fragment missing: " + ", ".join(sorted(missing)))
    return values


def _write_empty_tag(parent, tag, value):
    child = ET.SubElement(parent, tag)
    child.text = value
    return child


def _replace_entry(root, values):
    old = None
    for game in root.findall("game"):
        if (game.findtext("path") or "").strip() in PATH_VALUES:
            old = game
            break
    if old is None:
        index = len(root)
        old = ET.Element("game")
        root.insert(index, old)
    for child in list(old):
        old.remove(child)
    for tag in ("path", "name", "desc", "image", "genre"):
        if tag in values:
            _write_empty_tag(old, tag, values[tag])
    return old


def remove_weread(xml_bytes):
    root = ET.fromstring(xml_bytes)
    for game in list(root.findall("game")):
        if (game.findtext("path") or "").strip() in PATH_VALUES:
            root.remove(game)
    return _serialize(root)


def _serialize(root):
    try:
        ET.indent(root, space="  ")
    except AttributeError:
        pass
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def upsert_weread(xml_bytes, fragment_bytes=None):
    if fragment_bytes is None:
        fragment_path = Path(__file__).with_name("gamelist.fragment.xml")
        fragment_bytes = fragment_path.read_bytes()
    root = ET.fromstring(xml_bytes)
    if root.tag != "gameList":
        raise ValueError("gamelist root must be <gameList>")
    _replace_entry(root, _entry_values(fragment_bytes))
    return _serialize(root)


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("gamelist", type=Path)
    parser.add_argument("--fragment", type=Path)
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    source = args.gamelist.read_bytes() if args.gamelist.exists() else b"<?xml version='1.0'?><gameList/>"
    if args.remove:
        result = remove_weread(source)
    else:
        fragment = args.fragment.read_bytes() if args.fragment else None
        result = upsert_weread(source, fragment)
    _atomic_write(args.gamelist, result)
    print("updated", args.gamelist)


if __name__ == "__main__":
    main()