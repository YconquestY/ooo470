from dataclasses import dataclass
from collections import OrderedDict


@dataclass
class ActiveListEntry:
    done: bool
    exception: bool
    logicalDest: int
    oldDest: int
    # PC as key of active list entry

''' bypassing queue '''
class ActiveList:
    capacity: int = 32

    def __init__(self) -> None:
        self.active: OrderedDict[int, ActiveListEntry] = OrderedDict()
    
    def __len__(self) -> int:
        return len(self.active)
    
    def available(self, size = 4) -> bool:
        return self.capacity - len(self) >= size
    
    def __getitem__(self, key: int) -> ActiveListEntry:
        return self.active[key]
    
    def __setitem__(self, key: int, entry: ActiveListEntry) -> None:
        self.active[key] = entry
    
    def __delitem__(self, key: int) -> None:
        del self.active[key]
    
    def pop(self, key: int) -> ActiveListEntry:
        return self.active.pop(key)
    
    def __contains__(self, key: int) -> bool:
        return key in self.active
    
    def keys(self) -> list[int]:
        return list(self.active.keys())
    
    def firstKey(self) -> int:
        return next(iter(self.active))
    
    def lastKeys(self, size) -> tuple[int]:
        return tuple(self.active.keys())[-1:-size-1:-1] # reverse program order
    
    def dump(self) -> list[dict]:
        def entry2dict(key: int) -> dict:
            entry = self.active[key]
            return {'Done': entry.done,
                    'Exception': entry.exception,
                    'LogicalDestination': entry.logicalDest,
                    'OldDestination': entry.oldDest,
                    'PC': key}
        return [entry2dict(key) for key in self.active]
