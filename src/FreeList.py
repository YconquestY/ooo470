from collections import deque


''' bypassing queue '''
class FreeList:
    capacity: int = 32
    num_ar  : int = 32
    num_pr  : int = 64

    def __init__(self) -> None:
        self.free = deque(range(self.num_ar,
                                self.num_pr))
    def __len__(self) -> int:
        return len(self.free)
    
    def available(self, size = 4) -> bool:
        return self.capacity - len(self) >= size
    
    def popleft(self) -> int:
        return self.free.popleft()
    
    def append(self, pr: int) -> None:
        self.free.append(pr)
    
    def dump(self) -> list[int]:
        return list(self.free)
