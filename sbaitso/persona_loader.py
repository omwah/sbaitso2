"""Allowlisted bundled persona resources; never reads user-selected paths."""

from importlib.resources import files

def persona_names() -> tuple[str, ...]:
    """Discover bundled persona resources; never accept a caller's path."""
    return tuple(sorted(
        resource.name[:-4].lower()
        for resource in files("sbaitso.personas").iterdir()
        if resource.is_file() and resource.name.lower().endswith(".sys")
    ))


def display_personas() -> tuple[str, ...]:
    return tuple(f"{name.upper()}.SYS" for name in persona_names())


def load_persona(name: str) -> tuple[str, str] | None:
    normalized = name.strip().lower().removesuffix(".sys")
    requested = f"{normalized}.sys"
    # Match package resources by name, never by a user-provided filesystem path.
    for resource in files("sbaitso.personas").iterdir():
        if resource.is_file() and resource.name.lower() == requested:
            return f"{normalized.upper()}.SYS", resource.read_text(encoding="utf-8")
    return None
