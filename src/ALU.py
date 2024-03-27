from dataclasses import dataclass
from collections import deque

from IntQ import IntQEntry


@dataclass
class ALUEntry:
    dest: int
    pc: int
    result: int
    exception: bool

class ALU:
    width: int = 4

    def __init__(self) -> None:
        self.ex12ex2: deque[tuple[ALUEntry]] = deque()
    
    def ex1(self, job: tuple[IntQEntry]) -> None:
        def compute(entry: IntQEntry) -> ALUEntry:
            result: int = 0
            exception: bool = False
            if entry.op == 'add' or entry.op == 'addi':
                result = entry.aValue + entry.bValue
            elif entry.op == 'sub':
                result = entry.aValue - entry.bValue
            elif entry.op == 'mulu':
                result = entry.aValue * entry.bValue
            elif entry.op == 'divu':
                if entry.bValue == 0:
                    exception = True
                else:
                    result = entry.aValue // entry.bValue
            elif entry.op == 'remu':
                if entry.bValue == 0:
                    exception = True
                else:
                    result = entry.aValue % entry.bValue
            return ALUEntry(dest=entry.dest,
                            pc=entry.pc,
                            result=result,
                            exception=exception)
        self.ex12ex2.append(tuple(map(compute, job)))

    def ex2(self) -> tuple[ALUEntry]:
        return self.ex12ex2.popleft()