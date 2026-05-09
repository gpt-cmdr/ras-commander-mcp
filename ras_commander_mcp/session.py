"""Session state primitives for future stateful MCP workflows."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SessionState:
    """Minimal session state container reserved for Phase 0.4 behavior."""

    project_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def set_project(self, project_path: str | Path) -> None:
        """Set the active HEC-RAS project path for a session."""
        self.project_path = Path(project_path)
