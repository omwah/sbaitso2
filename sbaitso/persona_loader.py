"""Allowlisted bundled persona resources; never reads user-selected paths."""

from importlib.resources import files

PERSONAS = ("sbaitso", "gentle", "sardonic")


def display_personas() -> tuple[str, ...]:
    return tuple(f"{name.upper()}.SYS" for name in PERSONAS)


def load_persona(name: str) -> tuple[str, str] | None:
    normalized = name.strip().lower().removesuffix(".sys")
    if normalized not in PERSONAS:
        return None
    requested = f"{normalized}.sys"
    # Wheels built before/after the lowercase rename may carry different case.
    # Match package resources by name, never by a user-provided filesystem path.
    for resource in files("sbaitso.personas").iterdir():
        if resource.name.lower() == requested:
            return f"{normalized.upper()}.SYS", resource.read_text(encoding="utf-8")
    return None
