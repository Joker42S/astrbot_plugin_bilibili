from dataclasses import dataclass, field
from typing import List, Dict, Any

from .constant import RECENT_DYNAMIC_CACHE


def _as_str_list(values) -> List[str]:
    return [str(v) for v in values or []]


@dataclass
class Subscription:
    uid: int
    last: str = ""
    is_live: bool = False
    filter_types: List[str] = field(default_factory=list)
    filter_regex: List[str] = field(default_factory=list)
    recent_ids: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        uid = data.get("uid")
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            uid_int = 0
        last = str(data.get("last", "") or "")
        recent_ids = _as_str_list(data.get("recent_ids", []))
        instance = cls(
            uid=uid_int,
            last=last,
            is_live=bool(data.get("is_live", False)),
            filter_types=_as_str_list(data.get("filter_types", [])),
            filter_regex=_as_str_list(data.get("filter_regex", [])),
            recent_ids=recent_ids,
        )
        instance.ensure_cache_limit()
        return instance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "last": self.last,
            "is_live": self.is_live,
            "filter_types": list(self.filter_types),
            "filter_regex": list(self.filter_regex),
            "recent_ids": list(self.recent_ids),
        }

    def record_dynamic(self, dyn_id: str) -> None:
        dyn_id = str(dyn_id or "")
        if not dyn_id:
            return
        if dyn_id in self.recent_ids:
            self.recent_ids.remove(dyn_id)
        self.last = dyn_id
        self.recent_ids.insert(0, dyn_id)
        self.ensure_cache_limit()

    def ensure_cache_limit(self) -> None:
        if len(self.recent_ids) > RECENT_DYNAMIC_CACHE:
            del self.recent_ids[RECENT_DYNAMIC_CACHE:]

    def is_known(self, dyn_id: str) -> bool:
        dyn_id = str(dyn_id or "")
        if not dyn_id:
            return False
        return dyn_id == self.last or dyn_id in self.recent_ids
