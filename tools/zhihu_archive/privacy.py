"""推送前的隐私扫描。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

HARD_PATTERNS = [
    ("zhihu_cookie", re.compile(r"(?:z_c0|d_c0|_xsrf)\s*=")),
    ("github_token", re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{10,}")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{10,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("unc_path", re.compile(r"\\\\[A-Za-z0-9_.-]+\\[A-Za-z0-9_.$-]+")),
    (
        "proxy_config",
        re.compile(r"(?i)\b(?:https?_proxy|all_proxy)\s*=|ProxyCommand\s*="),
    ),
]

REVIEW_PATTERNS = [
    ("windows_path", re.compile(r"\b[A-Za-z]:[\\/]")),
    ("local_address", re.compile(r"\b(?:127\.0\.0\.1|localhost)\b", re.IGNORECASE)),
    (
        "private_ip",
        re.compile(
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        ),
    ),
    ("phone_cn", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("address_hint", re.compile(r"(?:家庭住址|身份证号|住址[:：])")),
]

IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
    ".avif",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    severity: str
    text: str


@dataclass
class ScanReport:
    hard: list[Finding] = field(default_factory=list)
    review: list[Finding] = field(default_factory=list)
    images: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.hard and not self.review


def load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.add(stripped)
    return entries


def _scan_text(text: str, relative: str, allowlist: set[str]) -> tuple[list[Finding], list[Finding]]:
    hard: list[Finding] = []
    review: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in HARD_PATTERNS:
            if pattern.search(line):
                hard.append(Finding(relative, line_number, kind, "hard", line.strip()[:160]))
        for kind, pattern in REVIEW_PATTERNS:
            for match in pattern.finditer(line):
                key = f"{kind}\t{relative}\t{match.group(0)}"
                if key in allowlist:
                    continue
                review.append(
                    Finding(relative, line_number, kind, "review", line.strip()[:160])
                )
    return hard, review


def _iter_files(root: Path, paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        candidate = root / raw
        if candidate.is_dir():
            files.extend(path for path in candidate.rglob("*") if path.is_file())
        elif candidate.is_file():
            files.append(candidate)
    return sorted(set(files))


def scan_paths(root: Path, paths: list[str], allowlist: set[str]) -> ScanReport:
    report = ScanReport()
    root = Path(root)
    for file_path in _iter_files(root, paths):
        relative = file_path.relative_to(root).as_posix()
        suffix = file_path.suffix.lower()
        if suffix in IMAGE_EXTS:
            report.images.append(relative)
            if suffix != ".svg":
                continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hard, review = _scan_text(text, relative, allowlist)
        report.hard.extend(hard)
        report.review.extend(review)
    return report
