from dataclasses import dataclass


@dataclass
class IntQEntry:
    dest: int # physical destination register
    op: str
    pc: int

    aReady: bool
    bReady: bool

    aRegTag: int = 0 # physical source register
    bRegTag: int = 0 # physical source register

    aValue: int = 0
    bValue: int = 0

''' bypassing queue '''
class IntQ:
    capacity: int = 32

    def __init__(self) -> None:
        self.buffer: list[IntQEntry] = [] # strictly speaking, not a queue
    
    def __len__(self) -> int:
        return len(self.buffer)
    
    def available(self, size = 4) -> bool:
        return self.capacity - len(self) >= size
    
    def __getitem__(self, idx: int) -> IntQEntry:
        return self.buffer[idx]

    def __delitem__(self, idx: int) -> None:
        del self.buffer[idx]
    
    def append(self, entry: IntQEntry) -> None:
        self.buffer.append(entry)
    
    def dump(self) -> list[dict]:
        def entry2dict(entry: IntQEntry) -> dict:
            return {'DestRegister': entry.dest,
                    
                    'OpAIsReady': entry.aReady,
                    'OpARegTag': entry.aRegTag,
                    'OpAValue': entry.aValue,

                    'OpBIsReady': entry.bReady,
                    'OpBRegTag': entry.bRegTag,
                    'OpBValue': entry.bValue,
                    
                    'OpCode': entry.op,
                    'PC': entry.pc}
        return list(map(entry2dict, self.buffer))
