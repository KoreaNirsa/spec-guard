from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


SPEC_DIR_NAME = "specs"
DEFAULT_SPEC_ROOTS = (SPEC_DIR_NAME,)
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


def resolve_spec_packages(path: Path) -> SpecPackageResolution:
    return SpecPackageResolution(
        requested_path=path,
        packages=tuple(discover_spec_packages(path)),
    )


def discover_spec_packages(path: Path) -> list[Path]:
    if (path / "spec.md").is_file():
        return [path]
    if not path.is_dir():
        return []

    packages: set[Path] = set()
    for spec_root in _iter_spec_roots(path):
        packages.update(_feature_dirs_under_spec_root(spec_root))
    return sorted(packages, key=_package_sort_key)


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
        if part != SPEC_DIR_NAME or index + 1 >= len(parts):
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
    if not starts_with(parts, spec_root_parts) or len(parts) <= len(spec_root_parts):
        return ()
    if any(is_excluded_discovery_dir_name(name) for name in spec_root_parts[:-1]):
        return ()
    if is_excluded_discovery_dir_name(parts[len(spec_root_parts)]):
        return ()
    return (spec_root_parts,)


def _path_sort_key(path: Path) -> tuple[str, str]:
    text = path.as_posix()
    return (text.casefold(), text)


def _package_sort_key(path: Path) -> tuple[int, str, str]:
    text = path.as_posix()
    return (len(path.parts), text.casefold(), text)
