"""Read-only descriptor snapshots under explicit roots; no project writes."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat


class PolicyError(ValueError):
    """A scoped read was denied."""


@dataclass(frozen=True)
class Snapshot:
    root: Path
    relative: str
    data: bytes
    digest: str


@dataclass(frozen=True)
class ReadPolicy:
    roots: tuple[Path, ...]
    max_file_bytes: int = 1_048_576

    @classmethod
    def from_environment(cls):
        """JSON array avoids ambiguous Windows drive/path separator handling."""
        value = os.environ.get("RAS_MCP_ALLOWED_ROOTS", "[]")
        try:
            paths = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PolicyError("RAS_MCP_ALLOWED_ROOTS must be a JSON array") from exc
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
            raise PolicyError("Configure a nonempty JSON array in RAS_MCP_ALLOWED_ROOTS")
        roots = []
        for item in paths:
            path = Path(item)
            if not path.is_absolute() or path.is_symlink():
                raise PolicyError("Allowed roots must be absolute real directories")
            resolved = path.resolve(strict=True)
            if not resolved.is_dir():
                raise PolicyError("Allowed roots must be directories")
            roots.append(resolved)
        return cls(tuple(dict.fromkeys(roots)))

    def read(self, root: str, relative: str, kind: str) -> Snapshot:
        """Take one stable, bounded snapshot; never follow project references."""
        chosen = Path(root)
        if not chosen.is_absolute() or chosen not in self.roots:
            raise PolicyError("root must exactly match a configured resolved root")
        parts = relative.replace("\\", "/").split("/")
        if (not parts or any(part in {"", ".", ".."} for part in parts)
                or Path(relative).is_absolute() or PureWindowsPath(relative).drive
                or any(":" in part or "\x00" in part for part in parts)):
            raise PolicyError("file must be a relative path without traversal or drive syntax")
        name = parts[-1]
        suffix = Path(name).suffix.lower()
        if kind == "project" and suffix != ".prj":
            raise PolicyError("Only .prj project text is permitted")
        if kind == "plan" and not re.fullmatch(r"\.p[0-9]{2}", suffix):
            raise PolicyError("Only .p01 through .p99 plan text is permitted")
        if kind not in {"project", "plan"} or suffix == ".p00":
            raise PolicyError("Unsupported file kind")
        fd = self._open(chosen, parts)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise PolicyError("Only regular text files are permitted")
            if before.st_size > self.max_file_bytes:
                raise PolicyError("Input exceeds file-size limit; use the Python library")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                content = stream.read(self.max_file_bytes + 1)
            after = os.fstat(fd)
            if len(content) > self.max_file_bytes:
                raise PolicyError("Input exceeds file-size limit; use the Python library")
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise PolicyError("Input changed during read; retry a stable file")
            if b"\x00" in content:
                raise PolicyError("NUL-containing input is not eligible text")
        finally:
            os.close(fd)
        return Snapshot(chosen, "/".join(parts), content, hashlib.sha256(content).hexdigest())

    @staticmethod
    def _open(root: Path, parts: list[str]) -> int:
        if os.name == "posix":
            # Walk beneath a descriptor, with no symlink following at any level.
            current = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                # Also anchor configured absolute-root ancestors. A replaced
                # parent symlink must not bypass the below-root walk.
                for part in [*root.parts[1:], *parts[:-1]]:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                    os.close(current)
                    current = next_fd
                return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=current)
            finally:
                os.close(current)
        if os.name == "nt":
            # Check the actual opened handle before reading, rather than relying
            # on a resolve-then-open check vulnerable to junction/symlink swaps.
            import ctypes
            from ctypes import wintypes
            import msvcrt
            path = root.joinpath(*parts)
            fd = os.open(path, os.O_RDONLY | os.O_BINARY)
            try:
                get_name = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
                get_name.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
                get_name.restype = wintypes.DWORD
                buffer = ctypes.create_unicode_buffer(32768)
                count = get_name(msvcrt.get_osfhandle(fd), buffer, len(buffer), 0)
                if not count or count >= len(buffer):
                    raise PolicyError("Could not verify opened file identity")
                final = buffer.value
                if final.startswith("\\\\?\\UNC\\"):
                    final = "\\\\" + final[8:]
                elif final.startswith("\\\\?\\"):
                    final = final[4:]
                actual = Path(final)
                if not actual.is_relative_to(root):
                    raise PolicyError("Opened file escaped the configured root")
                # In-root links still stay within the boundary. No content has
                # been read yet. Windows behavior requires native qualification.
                return fd
            except BaseException:
                os.close(fd)
                raise
        raise PolicyError("Descriptor-safe reads are unsupported on this platform")
