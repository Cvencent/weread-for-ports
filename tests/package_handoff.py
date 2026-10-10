"""Create a source archive for the WeRead for Ports repository."""
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "output" / "weread-for-ports-source.zip"
INCLUDE = ("README.md", ".gitignore", ".gitattributes",
           "extension", "launcher", "ports", "docs", "tests", "screenshots")


def iter_files():
    for name in INCLUDE:
        path = ROOT / name
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (item for item in path.rglob("*")
                        if item.is_file() and "__pycache__" not in item.parts
                        and item.suffix != ".pyc")


def main():
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(set(iter_files()))
    temporary = ARCHIVE.with_suffix(".new.zip")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for source in files:
            target.write(source, source.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(temporary) as target:
        assert target.testzip() is None
        for source in files:
            name = source.relative_to(ROOT).as_posix()
            assert hashlib.sha256(target.read(name)).digest() == hashlib.sha256(source.read_bytes()).digest()
    temporary.replace(ARCHIVE)
    print(f"Verified {len(files)} files: {ARCHIVE}")


if __name__ == "__main__":
    main()