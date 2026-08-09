"""Shared catalog normalization and ranking helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.0"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXECUTABLE_SUFFIXES = {
    ".py", ".sh", ".bash", ".zsh", ".ps1", ".js", ".mjs", ".cjs",
    ".ts", ".tsx", ".rb", ".pl", ".lua", ".jar", ".exe",
}

CATEGORY_DEFINITIONS = [
    {
        "id": "engineering",
        "label": "软件开发",
        "description": "编码、架构、API、测试、调试与代码协作",
        "tone": "green",
    },
    {
        "id": "ai-agents",
        "label": "AI 与智能体",
        "description": "Agent 编排、LLM、Prompt、RAG 与模型评估",
        "tone": "violet",
    },
    {
        "id": "automation",
        "label": "自动化与集成",
        "description": "工作流、浏览器自动化、连接器与跨工具协同",
        "tone": "cyan",
    },
    {
        "id": "design-media",
        "label": "设计与创意",
        "description": "UI/UX、品牌、图像、视频、音频与视觉表达",
        "tone": "magenta",
    },
    {
        "id": "research",
        "label": "研究与知识",
        "description": "搜索、资料调研、文档检索与知识整理",
        "tone": "blue",
    },
    {
        "id": "data",
        "label": "数据与分析",
        "description": "表格、SQL、统计、可视化与数据处理",
        "tone": "teal",
    },
    {
        "id": "office-content",
        "label": "办公与内容",
        "description": "写作、文档、演示、邮件、翻译与会议材料",
        "tone": "yellow",
    },
    {
        "id": "business-growth",
        "label": "产品与增长",
        "description": "产品、市场、销售、SEO、融资与商业策略",
        "tone": "orange",
    },
    {
        "id": "devops-cloud",
        "label": "DevOps 与云",
        "description": "CI/CD、部署、容器、云平台与可观测性",
        "tone": "slate",
    },
    {
        "id": "security",
        "label": "安全与合规",
        "description": "安全审计、漏洞、隐私、鉴权与合规治理",
        "tone": "red",
    },
    {
        "id": "general",
        "label": "通用工作流",
        "description": "规划、协作、方法论与跨领域辅助能力",
        "tone": "gray",
    },
]

CATEGORY_KEYWORDS = {
    "engineering": [
        "software", "coding", "code", "api", "backend", "frontend", "react", "next.js",
        "javascript", "typescript", "python", "golang", "rust", "java", "database", "architecture",
        "debug", "testing", "test", "git", "pull request", "code review", "refactor", "sdk", "library",
        "algorithm", "mobile app", "ios", "android", "web app", "developer", "package manager",
    ],
    "ai-agents": [
        "agent", "agents", "multi-agent", "subagent", "llm", "large language model", "prompt",
        "rag", "mcp", "model evaluation", "eval harness", "embedding", "openai", "claude", "gemini",
        "context engineering", "tool calling", "agentic", "skill creation", "writing skills",
    ],
    "automation": [
        "automation", "automate", "workflow", "integration", "browser automation", "web scraping",
        "scraper", "connector", "webhook", "cron", "slack", "notion", "linear", "jira", "zapier",
        "github issue", "github workflow", "cross-platform", "batch processing", "orchestration",
    ],
    "design-media": [
        "design", "ui", "ux", "figma", "image", "video", "audio", "music", "animation", "brand",
        "logo", "typography", "illustration", "visual", "creative", "photography", "3d", "canvas",
        "motion", "media generation", "frontend slides", "design system", "art direction",
    ],
    "research": [
        "research", "web search", "search engine", "literature", "investigate", "knowledge", "documentation",
        "docs lookup", "source attribution", "fact check", "due diligence", "browse", "discovery", "citation",
        "competitive analysis", "information retrieval", "technical docs", "documentation lookup",
    ],
    "data": [
        "data analysis", "analytics", "spreadsheet", "excel", "sql", "dataframe", "visualization", "chart",
        "statistics", "csv", "data pipeline", "data processing", "dashboard", "metrics", "forecasting",
        "financial model", "business intelligence", "bigquery", "postgres", "schema migration",
    ],
    "office-content": [
        "writing", "article", "blog", "content", "copywriting", "document", "pdf", "docx", "slides",
        "presentation", "email", "meeting", "notes", "report", "newsletter", "translation", "translate",
        "resume", "memo", "proposal", "proofread", "editing", "word document", "powerpoint",
    ],
    "business-growth": [
        "marketing", "sales", "seo", "product management", "market research", "market", "competitor",
        "investor", "fundraising", "customer", "growth", "campaign", "pricing", "startup", "business",
        "go-to-market", "strategy", "commerce", "ecommerce", "revenue", "conversion", "social media",
    ],
    "devops-cloud": [
        "devops", "deploy", "deployment", "ci/cd", "pipeline", "docker", "kubernetes", "cloud", "aws",
        "azure", "gcp", "infrastructure", "terraform", "monitoring", "observability", "serverless", "vercel",
        "github actions", "sre", "production operations", "container", "helm", "release engineering",
    ],
    "security": [
        "security", "vulnerability", "threat", "compliance", "privacy", "authentication", "authorization",
        "secret", "penetration", "malware", "security audit", "encryption", "safety", "secure coding",
        "owasp", "incident response", "access control", "risk assessment", "forensics", "zero trust",
    ],
}

CATEGORY_BY_ID = {category["id"]: category for category in CATEGORY_DEFINITIONS}
GENERIC_SKILL_TOPICS = {
    "agent", "agents", "agent-skills", "ai", "claude", "claude-code", "codex",
    "cursor", "skills", "skill", "openai", "gemini", "antigravity",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _clean_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the small scalar subset needed from SKILL.md frontmatter."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    result: dict[str, str] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            index += 1
            continue
        key, raw_value = match.groups()
        if raw_value in {"|", ">", "|-", ">-"}:
            parts: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                if lines[index].strip():
                    parts.append(lines[index].strip())
                index += 1
            result[key] = " ".join(parts)
            continue
        result[key] = _clean_yaml_scalar(raw_value)
        index += 1
    return result


def normalize_name(value: str, fallback: str) -> str:
    candidate = value.strip().lower()
    candidate = re.sub(r"[^a-z0-9]+", "-", candidate).strip("-")
    candidate = re.sub(r"-{2,}", "-", candidate)
    if not candidate:
        candidate = re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-")
    return candidate[:64].rstrip("-") or "unnamed-skill"


def normalize_description(value: str, fallback: str = "") -> str:
    description = re.sub(r"\s+", " ", value).strip()
    if not description or "TODO" in description.upper():
        description = re.sub(r"\s+", " ", fallback).strip()
    return description[:360] or "No description provided."


def _keyword_matches(text: str, keywords: Iterable[str]) -> list[str]:
    normalized = f" {re.sub(r'[^a-z0-9+#./-]+', ' ', text.lower())} "
    matches: list[str] = []
    for keyword in keywords:
        candidate = keyword.lower()
        if f" {candidate} " in normalized or (" " in candidate and candidate in normalized):
            matches.append(keyword)
    return matches


def categorize_skill(
    name: str,
    description: str,
    topics: Iterable[str] = (),
    skill_path: str = "",
) -> dict[str, Any]:
    """Assign one evidence-backed primary category from skill metadata."""
    topic_text = " ".join(topic for topic in topics if topic.lower() not in GENERIC_SKILL_TOPICS)
    scores: dict[str, int] = {}
    signals: dict[str, list[str]] = {}
    for category_id, keywords in CATEGORY_KEYWORDS.items():
        name_matches = _keyword_matches(name.replace("-", " "), keywords)
        description_matches = _keyword_matches(description, keywords)
        topic_matches = _keyword_matches(topic_text.replace("-", " "), keywords)
        path_matches = _keyword_matches(skill_path.replace("-", " "), keywords)
        scores[category_id] = (
            len(name_matches) * 5
            + len(description_matches) * 2
            + len(topic_matches) * 3
            + len(path_matches)
        )
        signals[category_id] = list(dict.fromkeys(name_matches + topic_matches + description_matches + path_matches))

    category_id, best_score = max(scores.items(), key=lambda entry: entry[1])
    if best_score == 0:
        category_id = "general"
    definition = CATEGORY_BY_ID[category_id]
    return {
        "id": category_id,
        "label": definition["label"],
        "confidence": min(100, 35 + best_score * 8) if best_score else 25,
        "signals": signals.get(category_id, [])[:4],
    }


def find_plugin_root(skill_path: str, paths: Iterable[str]) -> str | None:
    candidates: list[str] = []
    for path in paths:
        if not path.endswith(".codex-plugin/plugin.json"):
            continue
        root = path[: -len(".codex-plugin/plugin.json")].rstrip("/")
        prefix = f"{root}/" if root else ""
        if skill_path.startswith(prefix):
            candidates.append(root)
    return max(candidates, key=len) if candidates else None


def _is_under(path: str, root: str | None) -> bool:
    if root in {None, ""}:
        return True
    return path == root or path.startswith(f"{root}/")


def classify_capabilities(paths: Iterable[str], plugin_root: str | None) -> tuple[list[str], dict[str, Any]]:
    scoped = [path for path in paths if _is_under(path, plugin_root)]
    has_plugin = plugin_root is not None
    has_mcp = any(path.endswith(".mcp.json") or path.endswith("mcp.json") for path in scoped)
    has_hooks = any("/hooks/" in f"/{path}/" or path.endswith("hooks.json") for path in scoped)
    has_scripts = any(
        "/scripts/" in f"/{path}/" or Path(path).suffix.lower() in EXECUTABLE_SUFFIXES
        for path in scoped
    )

    types = ["skill"]
    if has_plugin:
        types.append("plugin")
    if has_mcp:
        types.append("mcp")

    signals: list[str] = []
    if has_scripts:
        signals.append("Contains executable scripts")
    if has_mcp:
        signals.append("Configures MCP servers")
    if has_hooks:
        signals.append("Contains hooks")
    if not signals:
        signals.append("Instruction-only skill")

    risk_points = int(has_scripts) + int(has_mcp) + (2 * int(has_hooks))
    level = "high" if risk_points >= 3 else "medium" if risk_points else "low"
    return types, {
        "level": level,
        "has_scripts": has_scripts,
        "has_mcp": has_mcp,
        "has_hooks": has_hooks,
        "signals": signals,
    }


def calculate_score(
    repository: dict[str, Any],
    description: str,
    skill_path: str,
    star_delta_7d: int,
    star_delta_30d: int,
) -> dict[str, int]:
    stars = max(0, int(repository.get("stargazers_count") or 0))
    popularity = min(100, round((math.log10(stars + 1) / 5) * 100))
    momentum = min(100, max(0, round(star_delta_7d * 2.5 + star_delta_30d * 0.35)))

    pushed_at = parse_datetime(repository.get("pushed_at"))
    age_days = 365
    if pushed_at:
        age_days = max(0, (utc_now() - pushed_at).days)
    freshness = max(0, min(100, round(100 - age_days * 1.2)))

    quality = 20
    quality += 30 if len(description) >= 80 else 15 if len(description) >= 30 else 0
    quality += 20 if repository.get("license") else 0
    quality += 15 if repository.get("topics") else 0
    quality += 15 if skill_path.count("/") >= 1 else 5
    quality = min(100, quality)

    trust = 35
    trust += 30 if repository.get("license") else 0
    trust += 20 if not repository.get("archived") else -30
    trust += 15 if stars >= 10 else 0
    trust = max(0, min(100, trust))

    total = round(
        popularity * 0.28
        + momentum * 0.30
        + freshness * 0.18
        + quality * 0.14
        + trust * 0.10
    )
    return {
        "total": total,
        "popularity": popularity,
        "momentum": momentum,
        "freshness": freshness,
        "quality": quality,
        "trust": trust,
        "star_delta_7d": max(0, star_delta_7d),
        "star_delta_30d": max(0, star_delta_30d),
    }


def build_catalog_item(
    repository: dict[str, Any],
    skill_path: str,
    skill_text: str,
    tree_paths: Iterable[str],
    star_delta_7d: int = 0,
    star_delta_30d: int = 0,
) -> dict[str, Any]:
    paths = list(tree_paths)
    metadata = parse_frontmatter(skill_text)
    fallback_name = Path(skill_path).parent.name or repository["name"]
    name = normalize_name(metadata.get("name", ""), fallback_name)
    description = normalize_description(metadata.get("description", ""), repository.get("description") or "")
    plugin_root = find_plugin_root(skill_path, paths)
    types, risk = classify_capabilities(paths, plugin_root)
    full_name = repository["full_name"]
    default_branch = repository.get("default_branch") or "main"
    owner = repository.get("owner") or {}
    license_value = repository.get("license")
    if isinstance(license_value, dict):
        license_value = license_value.get("spdx_id")

    repository_view = {
        "full_name": full_name,
        "url": repository.get("html_url") or f"https://github.com/{full_name}",
        "owner": owner.get("login") or full_name.split("/", 1)[0],
        "owner_avatar": owner.get("avatar_url") or "",
        "stars": int(repository.get("stargazers_count") or 0),
        "forks": int(repository.get("forks_count") or 0),
        "language": repository.get("language"),
        "license": license_value if license_value and license_value != "NOASSERTION" else None,
        "topics": repository.get("topics") or [],
        "default_branch": default_branch,
        "pushed_at": repository.get("pushed_at"),
        "archived": bool(repository.get("archived")),
    }
    score = calculate_score(
        {**repository, "license": repository_view["license"]},
        description,
        skill_path,
        star_delta_7d,
        star_delta_30d,
    )
    install_mode = "plugin" if plugin_root is not None else "skill"
    prompt_target = f"{full_name}:{skill_path}"
    item_id = hashlib.sha256(prompt_target.encode("utf-8")).hexdigest()[:16]
    category = categorize_skill(name, description, repository_view["topics"], skill_path)
    return {
        "id": item_id,
        "name": name,
        "description": description,
        "category": category,
        "types": types,
        "repository": repository_view,
        "skill_path": skill_path,
        "source_url": f"https://github.com/{full_name}/tree/{default_branch}/{Path(skill_path).parent.as_posix()}",
        "install": {
            "mode": install_mode,
            "repo": full_name,
            "ref": default_branch,
            "path": skill_path.rsplit("/", 1)[0] if "/" in skill_path else ".",
            "plugin_path": plugin_root,
            "codex_prompt": f"Use $skill-radar to inspect and install {prompt_target}.",
        },
        "risk": risk,
        "score": score,
    }


def load_star_baselines(snapshot_dir: Path, now: datetime) -> tuple[dict[str, int], dict[str, int]]:
    snapshots: list[tuple[datetime, dict[str, int]]] = []
    if snapshot_dir.exists():
        for path in snapshot_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                created = parse_datetime(payload.get("generated_at"))
                repositories = payload.get("repositories")
                if created and isinstance(repositories, dict):
                    snapshots.append((created, {key: int(value) for key, value in repositories.items()}))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue

    def closest(days: int) -> dict[str, int]:
        target = now.timestamp() - days * 86400
        eligible = [entry for entry in snapshots if entry[0].timestamp() <= target]
        if not eligible:
            return {}
        return max(eligible, key=lambda entry: entry[0])[1]

    return closest(7), closest(30)


def save_star_snapshot(snapshot_dir: Path, now: datetime, repositories: Iterable[dict[str, Any]]) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    destination = snapshot_dir / f"{now.date().isoformat()}.json"
    payload = {
        "generated_at": isoformat_z(now),
        "repositories": {
            repository["full_name"]: int(repository.get("stargazers_count") or 0)
            for repository in repositories
        },
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    snapshots = sorted(snapshot_dir.glob("*.json"), reverse=True)
    for stale in snapshots[45:]:
        stale.unlink(missing_ok=True)
    return destination


def write_catalog(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
