import asyncio
from pathlib import Path

from ...config import settings
from ..base import BaseNode, NodeConfigError, NodeResult, NodeRun, field_spec
from ..registry import register


def _safe_path(raw: str) -> Path:
    """Resolve a user path inside settings.output_dir (a leading 'outputs/' is accepted)."""
    out_dir = settings.output_dir.resolve()
    p = Path(raw.strip())
    if p.is_absolute() or raw.strip().startswith(("~", "\\")):
        raise NodeConfigError("Absolute paths are not allowed")
    if p.parts and p.parts[0] == "outputs":
        p = Path(*p.parts[1:]) if len(p.parts) > 1 else Path("output.txt")
    target = (out_dir / p).resolve()
    if not target.is_relative_to(out_dir):
        raise NodeConfigError(f"Path must stay inside the outputs folder ({out_dir})")
    return target


@register
class WriteFileNode(BaseNode):
    type = "write_file"
    category = "action"
    label = "Write File"
    description = "Write or append text to a file inside the outputs/ folder."
    fields = [
        field_spec("path", "File path", required=True, placeholder="outputs/result.txt"),
        field_spec("content", "Content", "textarea"),
        field_spec("mode", "Mode", "select", default="write", options=["write", "append"]),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        target = _safe_path(str(config["path"]))
        mode = str(config.get("mode") or "write").lower()
        if mode not in ("write", "append"):
            raise NodeConfigError("Mode must be 'write' or 'append'")
        content = config.get("content")
        content = "" if content is None else (content if isinstance(content, str) else str(content))

        def _write() -> int:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a" if mode == "append" else "w", encoding="utf-8") as fh:
                if mode == "append" and content and not content.endswith("\n"):
                    fh.write(content + "\n")
                else:
                    fh.write(content)
            return len(content.encode("utf-8"))

        n = await asyncio.to_thread(_write)
        rel = target.relative_to(settings.output_dir.resolve())
        return NodeResult(output={"path": f"outputs/{rel}", "bytes": n, "mode": mode}, message=f"{mode} {n} bytes to outputs/{rel}")
