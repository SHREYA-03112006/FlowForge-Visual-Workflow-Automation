import re

from ..base import BaseNode, NodeConfigError, NodeResult, NodeRun, as_dict, as_json_value, field_spec
from ..registry import register

_MISSING = object()


def get_path(data, path: str):
    cur = data
    for part in [p for p in re.sub(r"\[(\d+)\]", r".\1", path).split(".") if p]:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return _MISSING
    return cur


@register
class JsonExtractNode(BaseNode):
    type = "json_extract"
    category = "transform"
    label = "Extract JSON Fields"
    description = "Pull values out of JSON. Use 'path' for one value ({value}) or 'fields' to build a new object."
    fields = [
        field_spec("source", "JSON data", required=True, placeholder="{{n2.output.body}}"),
        field_spec("path", "Path", placeholder="user.address.city  or  items[0].name"),
        field_spec("fields", "Fields (JSON map)", "json", placeholder='{"city": "user.address.city"}'),
        field_spec("default", "Default if missing", help="Used when a path does not exist; otherwise the node fails."),
    ]

    async def execute(self, config, run: NodeRun) -> NodeResult:
        data = as_json_value(config.get("source"))
        has_default = config.get("default") not in (None, "")
        default = config.get("default")

        def fetch(path: str):
            v = get_path(data, path)
            if v is _MISSING:
                if has_default:
                    return default
                raise NodeConfigError(f"Path '{path}' not found in data")
            return v

        fields = config.get("fields")
        if fields not in (None, "", {}):
            mapping = as_dict(fields, "Fields")
            return NodeResult(output={name: fetch(str(p)) for name, p in mapping.items()},
                              message=f"Extracted {len(mapping)} field(s)")
        path = config.get("path")
        if path in (None, ""):
            raise NodeConfigError("Provide either 'path' or 'fields'")
        return NodeResult(output={"value": fetch(str(path))}, message=f"Extracted '{path}'")
