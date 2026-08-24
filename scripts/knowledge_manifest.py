from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def list_manifests(
    repo_root: Path,
    source_name: str,
    prefix: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    """List available manifests for a source."""
    manifest_dir = repo_root / "knowledge" / source_name / "manifest"
    if not manifest_dir.exists():
        return {
            "source": source_name,
            "prefix": prefix,
            "limit": limit,
            "matched": 0,
            "returned": 0,
            "results": [],
        }
    
    matched = []
    for manifest_path in sorted(manifest_dir.glob("*.yaml")) + sorted(manifest_dir.glob("*.yml")):
        if manifest_path.name == "README.md":
            continue
        
        manifest = _load_manifest(manifest_path)
        name = manifest["name"]
        
        if prefix and not name.startswith(prefix):
            continue
        
        matched.append({
            "name": name,
            "description": manifest.get("description", ""),
            "tree_path_count": len(manifest.get("tree_paths", [])),
            "version": manifest.get("version", "1"),
        })
    
    limited = matched[:limit] if limit is not None else matched
    return {
        "source": source_name,
        "prefix": prefix,
        "limit": limit,
        "matched": len(matched),
        "returned": len(limited),
        "results": limited,
    }


def fetch_manifest(
    repo_root: Path,
    source_name: str,
    manifest_name: str,
) -> dict[str, object]:
    """Fetch a manifest and concatenate its tree entry contents."""
    manifest_dir = repo_root / "knowledge" / source_name / "manifest"
    manifest_path = _find_manifest_file(manifest_dir, manifest_name)
    
    if not manifest_path:
        raise ValueError(f"Manifest '{manifest_name}' not found for source '{source_name}'")
    
    manifest = _load_manifest(manifest_path)
    tree_paths = manifest.get("tree_paths", [])
    
    if not tree_paths:
        raise ValueError(f"Manifest '{manifest_name}' has no tree paths")
    
    tree_root = repo_root / "knowledge" / source_name / "tree"
    content_parts = []
    missing_paths = []
    
    for tree_path in tree_paths:
        entry_path = tree_root / tree_path / "README.md"
        if not entry_path.exists():
            missing_paths.append(tree_path)
            continue
        
        content = entry_path.read_text(encoding="utf-8")
        content_parts.append(f"<!-- Entry: {tree_path} -->\n\n{content}\n")
    
    concatenated_text = "\n".join(content_parts).strip()
    
    return {
        "source": source_name,
        "manifest": manifest_name,
        "description": manifest.get("description", ""),
        "manifest_version": manifest.get("version", "1"),
        "tree_path_count": len(tree_paths),
        "missing_paths": missing_paths,
        "content_version": _content_version(concatenated_text),
        "updated_at_utc": datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "text": concatenated_text,
    }


def _find_manifest_file(manifest_dir: Path, manifest_name: str) -> Path | None:
    """Find manifest file by name (with or without extension)."""
    for ext in (".yaml", ".yml"):
        candidate = manifest_dir / f"{manifest_name}{ext}"
        if candidate.exists():
            return candidate
    return None


def _load_manifest(manifest_path: Path) -> dict[str, object]:
    """Load and validate a manifest YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML is required for manifest support. Install with: pip install pyyaml")
    
    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse manifest {manifest_path}: {e}")
    
    if not isinstance(data, dict):
        raise ValueError(f"Manifest {manifest_path} must be a YAML object")
    
    if "name" not in data:
        raise ValueError(f"Manifest {manifest_path} must have a 'name' field")
    
    if "tree_paths" not in data or not isinstance(data["tree_paths"], list):
        raise ValueError(f"Manifest {manifest_path} must have a 'tree_paths' list")
    
    return data


def _content_version(text: str) -> str:
    """Generate a version hash for the concatenated content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
