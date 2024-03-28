from collections import deque
from typing      import Any
from copy        import deepcopy

from ALU        import *
from ActiveList import *
from DIR        import *
from FreeList   import *
from IntQ       import *

class OoO470:
    fetch_width: int =  4
    num_ar     : int = 32
    num_pr     : int = 64
    exceptionPC: int = 0x10000

    def __init__(self, instructions: list[str]) -> None:
        self.iCache: list[str] = instructions # instructions

        self.pc : int = 0
        # F&D
        self.dir: DIR = DIR()
        # R&D
        self.freeList: FreeList = FreeList()
        self.regMap: list[int] = list(range(self.num_ar)) # architectural-physical register map
        self.busy: list[bool] = [False,] * self.num_pr    # busy bit table
        self.prf = [0,] * self.num_pr                     # physical RF
        self.iq: IntQ = IntQ()
        # I
        self.i2ex1: deque[tuple[IntQEntry]] = deque()
        # EX (2 stages)
        self.alu = ALU()
        self.ex22c: deque[tuple[ALUEntry]] = deque()
        # C
        
        self.activeList: ActiveList = ActiveList()
        self.bypass: tuple[ALUEntry] = (None,) * ALU.width # bypassing
        # exception recovery
        self.exception: bool = False # exception mode buffer: 1-cycle delay
        self.halt     : bool = False # halt execution after exception recovery

        self.epc  : int  = 0
        self.eflag: bool = False
    
    def next(self) -> bool:
        ''' pipeline advances
            total order: EX2 < C < EX1 < I < R&D < F&D
        '''        
        if not self.eflag:
            # EX2
            print('EX2', end=' ')
            try:
                aluResult: tuple[ALUEntry] = self.alu.ex2()
            except IndexError: # empty FIFO
                pass
            else:
                self.ex22c.append(aluResult)
                self.bypass = aluResult # bypassing
            # C
            print('C', end=' ')
            # commit
            num_commit: int = 0
            pcOfInstrToCommit: list[int] = []
            for pc in self.activeList.keys(): # key in program (ascending) order
                if num_commit >= 4:
                    break

                if self.activeList[pc].exception:
                    print('RESET')

                    self.eflag = True
                    self.pc = self.exceptionPC
                    self.epc = pc

                    self.dir.clear()
                    self.iq.clear()
                    self.alu.clear()
                    # commit non-faulting instructions
                    for pc in pcOfInstrToCommit:
                        del self.activeList[pc]
                    
                    return self.halt
                elif self.activeList[pc].done:
                    pcOfInstrToCommit.append(pc)
                    self.freeList.append(self.activeList[pc].oldDest) # update free list
                    num_commit += 1
                else: # incomplete instruction
                    break
            # delete active list entry
            for pc in pcOfInstrToCommit:
                del self.activeList[pc]
            
            # update free list
            try:
                instrToCommit: tuple[ALUEntry] = self.ex22c.popleft()
            except IndexError: # empty FIFO
                pass
            else:
                for entry in instrToCommit:
                    if entry is not None:
                        if entry.pc in self.activeList:
                            self.activeList[entry.pc].done = True
                            self.activeList[entry.pc].exception = entry.exception
                        else:
                            raise KeyError('instruction not in active list')
            # EX1
            print('EX1', end=' ')
            try:
                aluIn: tuple[IntQEntry] = self.i2ex1.popleft()
            except IndexError: # empty FIFO
                pass
            else:
                self.alu.ex1(aluIn)
            # I
            print('I', end=' ')
            # First update integer queue with bypassed results, then issue
            # instructions. This way, issue stage forwarding can be omitted.
            for idx in range(len(self.iq)):
                for result in self.bypass:
                    if (result is not None) and (not result.exception):
                        if (not self.iq[idx].aReady) and self.iq[idx].aRegTag == result.dest:
                            self.iq[idx].aValue = result.result
                            self.iq[idx].aRegTag = 0
                            self.iq[idx].aReady = True
                        if (not self.iq[idx].bReady) and self.iq[idx].bRegTag == result.dest:
                            self.iq[idx].bValue = result.result
                            self.iq[idx].bRegTag = 0
                            self.iq[idx].bReady = True
            # find instructions to issue
            instrToIssue   : list[IntQEntry] = []
            instrToIssueIdx: list[int]       = []
            num_issue = 0
            for idx in range(len(self.iq)): # Instruction with smaller PC has smaller index.
                if num_issue >= 4:
                    break

                if self.iq[idx].aReady and self.iq[idx].bReady:
                    instrToIssue.append(self.iq[idx])
                    instrToIssueIdx.append(idx)
                    num_issue += 1
            # make sure `instrToIssue` has exactly 4 elements
            while len(instrToIssue) < 4:
                instrToIssue.append(None)
            self.i2ex1.append(tuple(instrToIssue))
            # clear issued instructions from integer queue
            for idx in sorted(instrToIssueIdx, reverse=True): # indices in descending order! 
                del self.iq.buffer[idx]
            # R&D
            print('R&D', end=' ')
            # First update busy bit table and physical RF with bypassed results.
            # This way, operand forwarding can be omitted.
            for result in self.bypass:
                if (result is not None) and (not result.exception):
                    self.prf[result.dest] = result.result
                    self.busy[result.dest] = False
            # check free list, active list, and integer queue for enough entries
            numInstrToRename = len(self.dir)
            if self.freeList.available(numInstrToRename)   and \
               self.activeList.available(numInstrToRename) and \
               self.iq.available(numInstrToRename):
                for _ in range(numInstrToRename):     # DIR is cleared
                    decodedInstr = self.dir.popleft() #     when all instructions are popped.
                    # rename
                    new: int = self.freeList.popleft() # get free register from free list
                    self.busy[new] = True              # update busy bit table
                    # update active list
                    # Attention: update active list before register map
                    # This is because `oldDest` field of active list entry is the
                    # corresponding register map entry. If register map were
                    # updated first, such information would be lost.
                    #
                    # Attention: instructions are appended to active list in
                    #            program order.
                    self.activeList[decodedInstr.pc] = ActiveListEntry(done=False,
                                                                       exception=False,
                                                                       logicalDest=decodedInstr.dest,
                                                                       oldDest=self.regMap[decodedInstr.dest])
                    # dispatch
                    # Attention: update integer queue before register map
                    # This is because `aRegTag` and `bRegTag` fields of integer
                    # queue entry are the corresponding register map entries.
                    # If register map were updated first, operands not yet
                    # available would refer to new physical registers. This is
                    # problematic for accumulation, e.g.,
                    #     add x4, x4, 1
                    #
                    # For a register operand, there are 2 possibilities:
                    # 1. already in RF, either available long ago or forwarded just now
                    # 2. not yet available
                    prsA = self.regMap[decodedInstr.aRegTag] # operand A
                    immB = decodedInstr.op == 'addi'         # operand B
                    prsB = None if immB else self.regMap[decodedInstr.bRegTag]
                    self.iq.append(IntQEntry(
                        dest=new,
                        op=decodedInstr.op,
                        pc=decodedInstr.pc,
                        aReady=(False if self.busy[prsA] else True),
                        aRegTag=(prsA if self.busy[prsA] else 0),
                        aValue=(0 if self.busy[prsA] else self.prf[prsA]),
                        bReady=(True if immB
                                     else (False if self.busy[prsB] else True)),
                        bRegTag=(0 if immB else (prsB if self.busy[prsB] else 0)),
                        bValue=(decodedInstr.bValue if immB
                                                    else (0 if self.busy[prsB]
                                                            else self.prf[prsB]))
                    ))
                    self.regMap[decodedInstr.dest] = new # update register map
            #else: # do nothing
            #    pass

            # F&D
            print('F&D')
            if self.dir.available():
                if self.pc >= len(self.iCache): # end of program
                    return len(self.activeList) == 0
                else:
                    for i in range(self.pc, min(self.pc + self.fetch_width,
                                                len(self.iCache))): # near program end: only case where < 4 instructions fetched
                        self.dir.append(self.predecode(i))
                self.pc = min(self.pc + self.fetch_width, # update PC
                              len(self.iCache))
        # exception mode
        else:
            if self.eflag and (not self.halt):
                # roll back instructions
                print('ROLLBACK')
                pcOfInstrToRollback: tuple[int] = self.activeList.lastKeys(min(self.fetch_width, # reverse program order
                                                                            len(self.activeList)))
                for lastPC in pcOfInstrToRollback: 
                    lastInstr = self.activeList[lastPC]

                    releasedPR = self.regMap[lastInstr.logicalDest]
                    self.regMap[lastInstr.logicalDest] = lastInstr.oldDest # roll back register map
                    self.busy[releasedPR] = False                          # roll back busy bit table
                    self.freeList.append(releasedPR)                       # roll back free list
                # roll back active list
                for lastPC in pcOfInstrToRollback:
                    del self.activeList[lastPC]
            
            if len(self.activeList) == 0:
                if self.halt: # exception recovered last cycle
                    print()
                    self.eflag = False
                    return True
                else: # exception just recovered this cycle
                    self.halt = True
                    return False
            else:
                return False

    def predecode(self, idx: int) -> DIREntry:
        ''' predecode instruction '''
        instruction = self.iCache[idx]
        op, regs = instruction.split(' ', 1)
        dest, aRegTag, bRegTag = map(lambda x : x.strip(),
                                     regs.split(','))
        isAddi = op == 'addi'
        return DIREntry(dest=int(dest[1: ]),
                        op=op,
                        pc=idx,
                        aRegTag=int(aRegTag[1: ]),
                        bRegTag=(None if isAddi else int(bRegTag[1: ])),
                        bValue=(int(bRegTag) if isAddi else None))
    def dump(self) -> dict[str, Any]:
        ''' dump internal state '''
        def unsign(x: int) -> int:
            return x % (1 << 64) if x < 0 else x # Why does it work?

        return {"ActiveList": self.activeList.dump(),
                "BusyBitTable": deepcopy(self.busy),
                "DecodedPCs": self.dir.dump(),
                "Exception": self.eflag,
                "ExceptionPC": self.epc,
                "FreeList": self.freeList.dump(),
                "IntegerQueue": self.iq.dump(),
                "PC": self.pc,
                "PhysicalRegisterFile": list(map(unsign, deepcopy(self.prf))),
                "RegisterMapTable": deepcopy(self.regMap)}
