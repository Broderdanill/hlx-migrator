import json
from deepdiff import DeepDiff
from .cache import get_cached_objects, normalize


def compare_environments(source: str, target: str, object_type: str = "form", ignore_keys: set | list | None = None, ignore_order: bool = True) -> dict:
    ignore_keys = set(ignore_keys or [])
    src = {o.object_name: json.loads(o.json_data) for o in get_cached_objects(source, object_type)}
    tgt = {o.object_name: json.loads(o.json_data) for o in get_cached_objects(target, object_type)}
    names = sorted(set(src) | set(tgt))
    result = {"source": source, "target": target, "object_type": object_type, "summary": {"equal": 0, "different": 0, "missing_in_source": 0, "missing_in_target": 0}, "objects": []}
    for name in names:
        if name not in src:
            result["summary"]["missing_in_source"] += 1
            result["objects"].append({"name": name, "status": "missing_in_source"})
            continue
        if name not in tgt:
            result["summary"]["missing_in_target"] += 1
            result["objects"].append({"name": name, "status": "missing_in_target"})
            continue
        diff = DeepDiff(normalize(src[name], ignore_keys), normalize(tgt[name], ignore_keys), ignore_order=ignore_order).to_json()
        diff_obj = json.loads(diff)
        if diff_obj:
            result["summary"]["different"] += 1
            result["objects"].append({"name": name, "status": "different", "diff": diff_obj})
        else:
            result["summary"]["equal"] += 1
            result["objects"].append({"name": name, "status": "equal"})
    return result
