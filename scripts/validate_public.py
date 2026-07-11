#!/usr/bin/env python3
"""Validate the public skill, links, prompt parity, and claim guardrails."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_NAME = "positioning-companion"
REQUIRED = (
    "SKILL.md",
    "README.md",
    "一鍵定位-貼上任何AI.md",
    "新手安裝使用指南.md",
    "references/定位引擎.md",
    "references/01-intake.md",
    "references/02-choose-lane.md",
    "references/賽道庫.md",
    "docs/index.html",
    "docs/prompt-full.txt",
    "evals/evals.json",
)

CLAIM_PATTERNS = {
    "market rate": re.compile(r"行情(?:參考值)?\s*[:：]"),
    "income claim": re.compile(r"(?:月收|時薪)(?:參考)?(?:區間|落點)?\s*[:：]\s*(?:NT\$|USD|\$|\d)"),
    "guaranteed start timing": re.compile(r"起步時間\s*[:：]"),
    "unsupported money range": re.compile(r"(?:NT\$|USD\s*\$)\s*\d[^\n]{0,60}[-–]\s*\d"),
    "unsupported outcome percentage": re.compile(r"(?:成功率|轉換率|留存率|流失率)[^\n]{0,80}\d+(?:\.\d+)?\s*%"),
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "api credential": re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    "provider token": re.compile(r"\b(?:sk-|gh[pousr]_|AIza|xox[baprs]-)[A-Za-z0-9_-]{12,}"),
    "email value": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "Taiwan mobile value": re.compile(r"(?<!\d)(?:\+?886[- ]?|0)9\d{2}[- ]?\d{3}[- ]?\d{3}(?!\d)"),
}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def normalize(value: str) -> str:
    return value.rstrip("\n") + "\n"


def validate_frontmatter(errors: list[str]) -> None:
    content = text(ROOT / "SKILL.md")
    match = re.match(r"^---\n(.*?)\n---\n", content, re.S)
    if not match:
        errors.append("SKILL.md frontmatter missing or malformed")
        return
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    if fields.get("name") != EXPECTED_NAME:
        errors.append(f"frontmatter name must be {EXPECTED_NAME!r}")
    description = fields.get("description", "")
    if not description:
        errors.append("frontmatter description is empty")
    elif len(description) > 1024:
        errors.append("frontmatter description exceeds 1024 characters")


def validate_links(errors: list[str]) -> None:
    md_link = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    inline_ref = re.compile(r"`((?:references|runners)/[^`]+?\.md)`")
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        content = text(path)
        targets = [m.group(1) for m in md_link.finditer(content)]
        targets.extend(m.group(1) for m in inline_ref.finditer(content))
        for raw in targets:
            target = unquote(raw.split("#", 1)[0].strip())
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if "<" in target or ">" in target:
                continue
            base = ROOT if target.startswith(("references/", "runners/")) else path.parent
            resolved = (base / target).resolve()
            if not resolved.exists():
                errors.append(f"missing local reference: {path.relative_to(ROOT)} -> {target}")


def validate_assets(errors: list[str]) -> None:
    source = normalize(text(ROOT / "一鍵定位-貼上任何AI.md"))
    generated = normalize(text(ROOT / "docs" / "prompt-full.txt"))
    if source != generated:
        errors.append("docs/prompt-full.txt is stale; run scripts/build_public_assets.py")
    html = text(ROOT / "docs" / "index.html")
    for token in ("copyQuickBtn", "copyFullBtn", "quickPromptText", "prompt-full.txt"):
        if token not in html:
            errors.append(f"docs/index.html missing {token}")
    for stale in ("不用帳號", "十幾分鐘"):
        if stale in html:
            errors.append(f"docs/index.html contains stale claim: {stale}")


def validate_method(errors: list[str]) -> None:
    one_click = text(ROOT / "一鍵定位-貼上任何AI.md")
    skill = text(ROOT / "SKILL.md")
    lanes = text(ROOT / "references" / "賽道庫.md")
    for token in ("gate_status", "no_product_alternative", "falsifiable_check"):
        if token not in one_click:
            errors.append(f"one-click prompt missing {token}")
    if "本業放大器" not in lanes or "本業放大器" not in skill:
        errors.append("本業放大器 is not wired through skill and lane library")
    if "暫不定位" not in one_click:
        errors.append("one-click prompt lacks 暫不定位 outcome")


def validate_claims(errors: list[str]) -> None:
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts or "evals" in path.parts:
            continue
        content = text(path)
        for label, pattern in CLAIM_PATTERNS.items():
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                errors.append(f"{label}: {path.relative_to(ROOT)}:{line}")


def validate_evals(errors: list[str]) -> None:
    path = ROOT / "evals" / "evals.json"
    try:
        data = json.loads(text(path))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid evals/evals.json: {exc}")
        return
    if data.get("skill_name") != EXPECTED_NAME:
        errors.append("eval skill_name mismatch")
    evals = data.get("evals")
    if not isinstance(evals, list) or len(evals) < 3:
        errors.append("eval suite needs at least three cases")
        return
    for case in evals:
        for key in ("id", "prompt", "expected_output", "assertions"):
            if not case.get(key):
                errors.append(f"eval {case.get('id', '?')} missing {key}")


def validate_privacy(errors: list[str]) -> None:
    gitignore = text(ROOT / ".gitignore")
    if "runners/*" not in gitignore or "!runners/_範本/" not in gitignore:
        errors.append(".gitignore must exclude runner data and retain only the template")
    runners = ROOT / "runners"
    if runners.is_dir():
        for path in runners.rglob("*"):
            if path.is_file() and "_範本" not in path.parts:
                errors.append(f"non-template runner data in public tree: {path.relative_to(ROOT)}")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in {".md", ".txt", ".html", ".json", ".py", ".yml", ".yaml"}:
            continue
        content = text(path)
        for label, pattern in SECRET_PATTERNS.items():
            match = pattern.search(content)
            if match:
                line = content.count("\n", 0, match.start()) + 1
                errors.append(f"possible {label}: {path.relative_to(ROOT)}:{line}")


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            errors.append(f"missing required file: {rel}")
    if not errors:
        validate_frontmatter(errors)
        validate_links(errors)
        validate_assets(errors)
        validate_method(errors)
        validate_claims(errors)
        validate_evals(errors)
        validate_privacy(errors)
    if errors:
        print("VALIDATION FAILED")
        for item in errors:
            print(f"- {item}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
