from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


SPEC_DIR_NAME = "specs"
DEFAULT_SPEC_ROOTS = (SPEC_DIR_NAME,)
SUPPORTED_PACKAGE_PATH_EXAMPLES = (
    "specs/<feature>/spec.md",
    "backend/specs/<feature>/spec.md",
)
LIKELY_DRAFT_SPEC_FILENAMES = frozenset({
    "prd.md",
    "product-requirements.md",
    "requirements.md",
    "spec.md",
    "specification.md",
})
EXCLUDED_SPEC_DISCOVERY_DIRS = frozenset({
    "__generated__",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "env",
    "generated",
    "htmlcov",
    "node_modules",
    "out",
    "target",
    "vendor",
    "venv",
})


@dataclass(frozen=True)
class SpecPackageResolution:
    requested_path: Path
    packages: tuple[Path, ...]

    @property
    def ambiguous(self) -> bool:
        return len(self.packages) > 1


@dataclass(frozen=True)
class SpecPackageDiscoveryPreview:
    requested_path: Path
    packages: tuple[Path, ...]
    path_exists: bool
    draft_sources: tuple[Path, ...] = ()

    @property
    def status(self) -> str:
        if not self.packages:
            return "missing_spec_package"
        if len(self.packages) > 1:
            return "ambiguous"
        return "resolved"

    @property
    def reason(self) -> str:
        if not self.packages:
            return "path_not_found" if not self.path_exists else "no_candidates"
        if len(self.packages) > 1:
            return "multiple_candidates"
        return "single_candidate"

    def to_payload(self, *, display_root: Path | None = None) -> dict[str, object]:
        root = display_root or Path.cwd()
        candidates = [
            {
                "index": index,
                "path": _display_path(candidate, root),
                "spec_path": _display_path(candidate / "spec.md", root),
                "review_command": _review_command(_display_path(candidate, root)),
                "review_args": ["specguard", "run", _display_path(candidate, root), "--no-llm", "--no-follow-up"],
            }
            for index, candidate in enumerate(self.packages, start=1)
        ]
        draft_sources = [
            {
                "index": index,
                "path": _display_path(source, root),
                "kind": "non_package_spec_document",
            }
            for index, source in enumerate(self.draft_sources, start=1)
        ]
        status = self.status
        return {
            "schema_version": "specguard.discovery_preview.v1",
            "requested_path": _display_path(self.requested_path, root),
            "status": status,
            "reason": self.reason,
            "path_exists": self.path_exists,
            "candidate_count": len(candidates),
            "selection_required": status == "ambiguous",
            "review_allowed": status == "resolved",
            "candidates": candidates,
            "draft_source_count": len(draft_sources),
            "draft_sources": draft_sources,
            "next_action": _next_action(status, candidates, draft_sources),
        }


def resolve_spec_packages(path: Path) -> SpecPackageResolution:
    return SpecPackageResolution(
        requested_path=path,
        packages=tuple(discover_spec_packages(path)),
    )


def preview_spec_package_discovery(path: Path) -> SpecPackageDiscoveryPreview:
    resolution = resolve_spec_packages(path)
    draft_sources = () if resolution.packages else tuple(discover_draft_spec_documents(path))
    return SpecPackageDiscoveryPreview(
        requested_path=path,
        packages=resolution.packages,
        path_exists=path.exists(),
        draft_sources=draft_sources,
    )


def spec_package_discovery_preview_payload(path: Path, *, display_root: Path | None = None) -> dict[str, object]:
    return preview_spec_package_discovery(path).to_payload(display_root=display_root)


def discover_spec_packages(path: Path) -> list[Path]:
    if (path / "spec.md").is_file():
        return [path]
    if not path.is_dir():
        return []

    packages: set[Path] = set()
    for spec_root in _iter_spec_roots(path):
        packages.update(_feature_dirs_under_spec_root(spec_root))
    return sorted(packages, key=_package_sort_key)


def discover_draft_spec_documents(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if _is_likely_draft_spec_document(path) else []
    if not path.is_dir():
        return []

    documents: list[Path] = []
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=_path_sort_key)
        except OSError:
            continue
        for child in reversed(children):
            try:
                relative = child.relative_to(path)
            except ValueError:
                continue
            if any(is_excluded_discovery_dir_name(part) for part in relative.parts[:-1]):
                continue
            if child.is_dir() and not child.is_symlink():
                if not is_excluded_discovery_dir_name(child.name):
                    stack.append(child)
                continue
            if child.is_file() and _is_likely_draft_spec_document(child):
                documents.append(child)
    return sorted(documents, key=_package_sort_key)


def normalize_changed_path(value: str) -> PurePosixPath | None:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def normalize_spec_root_parts(value: str) -> tuple[str, ...]:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ()
    return PurePosixPath(normalized).parts


def spec_root_prefixes_for_changed_path(
    relative: PurePosixPath,
    spec_roots: tuple[str, ...] = DEFAULT_SPEC_ROOTS,
) -> tuple[tuple[str, ...], ...]:
    prefixes: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for spec_root in spec_roots:
        spec_root_parts = normalize_spec_root_parts(spec_root)
        if not spec_root_parts:
            continue
        candidates = (
            _nested_specs_prefixes(relative.parts)
            if spec_root_parts == (SPEC_DIR_NAME,)
            else _explicit_spec_root_prefix(relative.parts, spec_root_parts)
        )
        for prefix in candidates:
            if prefix in seen:
                continue
            seen.add(prefix)
            prefixes.append(prefix)
    return tuple(prefixes)


def feature_dir_for_changed_path(repo_root: Path, relative: PurePosixPath, spec_root_parts: tuple[str, ...]) -> Path:
    spec_root = repo_root.joinpath(*spec_root_parts)
    candidate = repo_root.joinpath(*relative.parent.parts)
    while candidate != spec_root.parent:
        if (candidate / "spec.md").exists():
            return candidate
        if candidate == spec_root:
            break
        candidate = candidate.parent

    feature_name = relative.parts[len(spec_root_parts)]
    return spec_root / feature_name


def starts_with(parts: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(parts) >= len(prefix) and parts[:len(prefix)] == prefix


def is_excluded_discovery_dir_name(name: str) -> bool:
    return name.startswith(".") or name in EXCLUDED_SPEC_DISCOVERY_DIRS


def _iter_spec_roots(root: Path):
    if root.name == SPEC_DIR_NAME:
        yield root
        return

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(
                (child for child in current.iterdir() if child.is_dir() and not child.is_symlink()),
                key=_path_sort_key,
            )
        except OSError:
            continue

        for child in reversed(children):
            try:
                relative = child.relative_to(root)
            except ValueError:
                continue
            if any(is_excluded_discovery_dir_name(part) for part in relative.parts):
                continue
            if child.name == SPEC_DIR_NAME:
                yield child
                continue
            stack.append(child)


def _feature_dirs_under_spec_root(spec_root: Path) -> list[Path]:
    try:
        children = sorted(
            (child for child in spec_root.iterdir() if child.is_dir() and not child.is_symlink()),
            key=_path_sort_key,
        )
    except OSError:
        return []
    return [
        child
        for child in children
        if not is_excluded_discovery_dir_name(child.name) and (child / "spec.md").is_file()
    ]


def _nested_specs_prefixes(parts: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    for index, part in enumerate(parts):
        if part != SPEC_DIR_NAME or not _has_feature_relative_path(parts, index + 1):
            continue
        if any(is_excluded_discovery_dir_name(name) for name in parts[:index]):
            continue
        if is_excluded_discovery_dir_name(parts[index + 1]):
            continue
        return (parts[:index + 1],)
    return ()


def _explicit_spec_root_prefix(
    parts: tuple[str, ...],
    spec_root_parts: tuple[str, ...],
) -> tuple[tuple[str, ...], ...]:
    if not starts_with(parts, spec_root_parts) or not _has_feature_relative_path(parts, len(spec_root_parts)):
        return ()
    if any(is_excluded_discovery_dir_name(name) for name in spec_root_parts[:-1]):
        return ()
    if is_excluded_discovery_dir_name(parts[len(spec_root_parts)]):
        return ()
    return (spec_root_parts,)


def _has_feature_relative_path(parts: tuple[str, ...], feature_index: int) -> bool:
    return feature_index + 1 < len(parts)


def _path_sort_key(path: Path) -> tuple[str, str]:
    text = path.as_posix()
    return (text.casefold(), text)


def _package_sort_key(path: Path) -> tuple[int, str, str]:
    text = path.as_posix()
    return (len(path.parts), text.casefold(), text)


def _display_path(path: Path, root: Path) -> str:
    try:
        display = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        display = path
    text = display.as_posix()
    return text if text else "."


def _review_command(path: str) -> str:
    return f"specguard run {_command_arg(path)} --no-llm --no-follow-up"


def _command_arg(value: str) -> str:
    if any(character.isspace() for character in value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _is_likely_draft_spec_document(path: Path) -> bool:
    return path.suffix.lower() == ".md" and path.name.casefold() in LIKELY_DRAFT_SPEC_FILENAMES


def _next_action(
    status: str,
    candidates: list[dict[str, object]],
    draft_sources: list[dict[str, object]],
) -> dict[str, object]:
    if status == "resolved":
        return {
            "type": "run_review",
            "candidate_index": 1,
            "command": candidates[0]["review_command"],
            "args": candidates[0]["review_args"],
        }
    if status == "ambiguous":
        return {
            "type": "choose_candidate",
            "command_template": "specguard run <selected-path> --no-llm --no-follow-up",
            "bulk_review_default": False,
        }
    if draft_sources:
        return {
            "type": "offer_draft_package",
            "requires_user_approval": True,
            "source_options": [source["path"] for source in draft_sources],
            "target_package_template": "specs/<feature>/",
            "command_template": "specguard init <feature-name>",
            "review_status": "not_reviewed",
        }
    return {
        "type": "create_or_select_package",
        "command_template": "specguard init <feature-name>",
        "supported_package_paths": list(SUPPORTED_PACKAGE_PATH_EXAMPLES),
        "manual_shape": {
            "required_file": "spec.md",
            "root_package": "specs/<feature>/",
            "nested_package": "backend/specs/<feature>/",
        },
        "next_commands": [
            "specguard init <feature-name>",
            "specguard discover <path>",
            "specguard run specs/<feature> --no-llm --no-follow-up",
        ],
        "review_status": "not_reviewed",
    }
