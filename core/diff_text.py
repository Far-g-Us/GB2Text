from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChangedPair:
    key: str
    old_text: str
    new_text: str


@dataclass(frozen=True)
class DiffReport:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[ChangedPair] = field(default_factory=list)


def text_segments_compare(texts1: Mapping[str, str], texts2: Mapping[str, str]) -> DiffReport:
    if not isinstance(texts1, Mapping) or not isinstance(texts2, Mapping):
        raise TypeError("texts1 и texts2 должны быть Mapping[str, str]")
    for mapping in (texts1, texts2):
        for key, value in mapping.items():
            if not isinstance(key, str):
                raise TypeError("ключи сегментов должны быть str")
            if not isinstance(value, str):
                raise TypeError("тексты сегментов должны быть str")
    keys1 = set(texts1.keys())
    keys2 = set(texts2.keys())
    added = sorted(keys2 - keys1)
    removed = sorted(keys1 - keys2)
    changed = [
        ChangedPair(key, texts1[key], texts2[key]) for key in sorted(keys1 & keys2) if texts1[key] != texts2[key]
    ]
    return DiffReport(added=added, removed=removed, changed=changed)
