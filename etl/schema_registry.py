"""Local-only loading of the shared data contract (D1-05).

Loads every ``*.schema.json`` in ``schemas/v1/`` and resolves ``$ref`` between
them through an in-memory ``referencing`` registry keyed by each file's ``$id``.
The ``$id`` host is the reserved ``exhibitiq.invalid``, so nothing can resolve
over the network, and nothing here fetches anything.

This module only loads the contract. It defines no fields: ``schemas/`` stays the
only place a field is defined (``docs/specs/data-package-contract.md`` §12).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas" / "v1"
_SUFFIX = ".schema.json"


class SchemaError(RuntimeError):
    """The schema set could not be loaded or used."""


class SchemaSet:
    def __init__(self, schema_dir: str | Path | None = None) -> None:
        self.directory = Path(schema_dir) if schema_dir is not None else DEFAULT_SCHEMA_DIR
        paths = sorted(self.directory.glob(f"*{_SUFFIX}"))
        if not paths:
            raise SchemaError(f"no *{_SUFFIX} files in {self.directory}")
        version_file = self.directory / "VERSION"
        if not version_file.is_file():
            raise SchemaError(f"missing {version_file}")
        self.version = version_file.read_text(encoding="utf-8").strip()

        self._schemas: dict[str, dict[str, Any]] = {}
        for path in paths:
            try:
                schema = json.loads(path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise SchemaError(f"{path}: invalid JSON: {exc}") from exc
            if not isinstance(schema, dict) or not isinstance(schema.get("$id"), str):
                raise SchemaError(f"{path}: schema must be an object with a string $id")
            Draft202012Validator.check_schema(schema)
            self._schemas[path.name.removesuffix(_SUFFIX)] = schema

        self._registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema)) for schema in self._schemas.values()
        )
        self._validators: dict[str, Draft202012Validator] = {}

    def entities(self) -> list[str]:
        return sorted(self._schemas)

    def validator(self, entity: str) -> Draft202012Validator:
        if entity not in self._schemas:
            raise SchemaError(f"no schema named {entity!r} in {self.directory}")
        if entity not in self._validators:
            self._validators[entity] = Draft202012Validator(self._schemas[entity], registry=self._registry)
        return self._validators[entity]

    def errors(self, entity: str, instance: Any) -> list[str]:
        """Human-readable validation errors for ``instance`` (empty list = valid)."""
        validator = self.validator(entity)
        try:
            found = sorted(validator.iter_errors(instance), key=lambda e: [str(p) for p in e.absolute_path])
        except Unresolvable as exc:
            raise SchemaError(f"a $ref in the {entity} schema cannot be resolved locally: {exc}") from exc
        messages = []
        for error in found:
            where = "/" + "/".join(str(p) for p in error.absolute_path) if error.absolute_path else "(record)"
            message = error.message if len(error.message) <= 300 else error.message[:297] + "..."
            messages.append(f"{where}: {message}")
        return messages
