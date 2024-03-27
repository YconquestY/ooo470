from dataclasses import dataclass
from collections import deque


@dataclass
class DIREntry:
    dest: int # logical destination register
    op: str
    pc: int

    aRegTag: int # logical source register
    bRegTag: int # logical source register

    bValue: int # immediate

class DIR:
    capacity: int = 4

    def __init__(self) -> None:
        self.decodedInstr: deque[DIREntry] = deque()
    
    def __len__(self) -> int:
        return len(self.decodedInstr)
    
    def available(self) -> bool:
        return len(self) == 0
    
    def append(self, instr: DIREntry) -> None:
        self.decodedInstr.append(instr)
    
    def popleft(self) -> DIREntry:
        return self.decodedInstr.popleft()
    
    def clear(self) -> None:
        self.decodedInstr.clear()
    
    def dump(self) -> list[int]:
        return [instr.pc for instr in self.decodedInstr]
