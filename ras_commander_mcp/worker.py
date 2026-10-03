"""Killable, bounded informational workers; domain imports stay off stdout."""

from contextlib import ExitStack, redirect_stdout
import multiprocessing
import sys
import tempfile
from pathlib import Path
import threading

from .contracts import MetadataRequest, Request, Result
from .policy import PolicyError, ReadPolicy

_slots = threading.BoundedSemaphore(2)


def _query(connection, policy, operation, payload, scratch):
    try:
        tempfile.tempdir = scratch
        with redirect_stdout(sys.stderr):
            from .adapter import RasAdapter
            request = (MetadataRequest if operation in {"project_metadata", "plan_configuration"}
                       else Request).model_validate(payload)
            adapter = RasAdapter(policy)
            if operation == "project_units":
                result = adapter.project_units(request)
            elif operation == "plan_description":
                result = adapter.plan_description(request)
            elif operation == "project_metadata":
                result = adapter.metadata(request, "project")
            elif operation == "plan_configuration":
                result = adapter.metadata(request, "plan")
            else:
                raise PolicyError("Unsupported information operation")
            connection.send((True, result.model_dump()))
    except Exception as exc:
        message = str(exc)[:600] if isinstance(exc, PolicyError) else "Text read failed; check permissions, format and installed API."
        connection.send((False, message))
    finally:
        connection.close()


def _stop(process):
    if process.pid is not None:
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
    process.close()


def execute(policy: ReadPolicy, operation: str, request: Request) -> Result:
    """At most two child queries; terminate work at the caller's time budget."""
    if not _slots.acquire(blocking=False):
        raise PolicyError("Information workers are busy; retry one bounded request")
    # Every allocation and cleanup is inside the semaphore-owning scope. Even
    # context/Pipe/process allocation failures must release the worker slot.
    with ExitStack() as cleanup:
        cleanup.callback(_slots.release)
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        cleanup.callback(parent.close)
        cleanup.callback(child.close)
        temp_root = Path(tempfile.gettempdir()).resolve()
        if any(temp_root == root or temp_root.is_relative_to(root) for root in policy.roots):
            raise PolicyError("Configure private temporary storage outside approved project roots")
        scratch = cleanup.enter_context(tempfile.TemporaryDirectory(prefix="ras-mcp-worker-"))
        process = context.Process(target=_query, args=(child, policy, operation,
                                  request.model_dump(), scratch), daemon=True)
        cleanup.callback(_stop, process)
        process.start()
        child.close()
        if not parent.poll(request.max_seconds):
            raise PolicyError("Information query exceeded time budget; use a scoped Python workflow")
        try:
            success, payload = parent.recv()
        except EOFError as exc:
            raise PolicyError("Information worker exited without a result; check installed dependencies") from exc
        if not success:
            raise PolicyError(payload)
        return Result.model_validate(payload)
