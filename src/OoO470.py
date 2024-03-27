from collections import deque
from typing      import Any

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
        self.exception: bool = False # exception mode

        self.epc  : int  = 0
        self.eflag: bool = False
    
    def next(self) -> None:
        ''' pipeline advances
            total order: EX2 < C < EX1 < I < R&D < F&D
        '''
        if not self.exception:
            # EX2
            try:
                aluResult: tuple[ALUEntry] = self.alu.ex2()
            except IndexError: # empty FIFO
                pass
            else:
                self.ex22c.append(aluResult)
                self.bypass = aluResult # bypassing
            # C
            try:
                instrToCommit: tuple[ALUEntry] = self.ex22c.popleft()
            except IndexError: # empty FIFO
                pass
            else:
                # update free list
                for entry in instrToCommit:
                    if entry is not None:
                        if entry.pc in self.activeList:
                            self.activeList[entry.pc].done = True
                            self.activeList[entry.pc].exception = entry.exception
                        else:
                            raise KeyError('instruction not in active list')
                # commit
                num_commit: int = 0
                pcOfInstrToCommit: list[int] = []
                for pc in self.activeList: # key in program (ascending) order
                    if num_commit >= 4:
                        break

                    if self.activeList[pc].exception:
                        self.exception = True
                        break
                    elif self.activeList[pc].done:
                        pcOfInstrToCommit.append(pc)
                        self.freeList.append(self.activeList[pc].oldDest) # update free list
                        num_commit += 1
                    else: # incomplete instruction
                        break
                # delete active list entry
                for pc in pcOfInstrToCommit:
                    del self.activeList[pc]
            # EX1
            try:
                aluIn: tuple[IntQEntry] = self.i2ex1.popleft()
            except IndexError: # empty FIFO
                pass
            else:
                self.alu.ex1(aluIn)
            # I
            # First update integer queue with bypassed results, then issue
            # instructions. This way, issue stage forwarding can be omitted.
            for idx in range(len(self.iq)):
                for result in self.bypass:
                    if (result is not None) and (not result.exception):
                        if (not self.iq[idx].aReady) and self.iq[idx].aRegTag == result.dest:
                            self.iq[idx].aValue = result.result
                            self.iq[idx].aReady = True
                        if (not self.iq[idx].bReady) and self.iq[idx].bRegTag == result.dest:
                            self.iq[idx].bValue = result.result
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
                    # corresponding register map entry. If register map was updated
                    # first, such information would be lost.
                    #
                    # Attention: instructions are appended to active list in
                    #            program order.
                    self.activeList[decodedInstr.pc] = ActiveListEntry(done=False,
                                                                       exception=False,
                                                                       logicalDest=decodedInstr.dest,
                                                                       oldDest=self.regMap[decodedInstr.dest])
                    self.regMap[decodedInstr.dest] = new # update register map
                    # dispatch
                    # For a register operand, there are 2 possibilities:
                    # 1. already in RF, either available long ago or forwarded just now
                    # 2. not yet available
                    prsA = self.regMap[decodedInstr.aRegTag] # operand A
                    immB = decodedInstr.bRegTag == None      # operand B
                    self.iq.append(IntQEntry(
                        dest=new,
                        op=decodedInstr.op,
                        pc=decodedInstr.pc,
                        aReady=(False if self.busy[prsA] else True),
                        aRegTag=prsA,
                        aValue=(0 if self.busy[prsA] else self.prf[prsA]),
                        bReady=(True if immB
                                    else (False if self.busy[decodedInstr.bRegTag]
                                                else True)),
                        bRegTag=(None if immB else decodedInstr.bRegTag),
                        bValue=(decodedInstr.bValue if immB
                                                    else (0 if self.busy[decodedInstr.bRegTag]
                                                            else self.prf[decodedInstr.bRegTag]))))
            #else: # do nothing
            #    pass

            # F&D
            if self.dir.available():
                if self.pc >= len(self.iCache): # end of program
                    return
                else:
                    for i in range(self.pc, min(self.pc + self.fetch_width,
                                                len(self.iCache))): # near program end: only case where < 4 instructions fetched
                        self.dir.append(self.predecode(i))
            self.pc = min(self.pc + self.fetch_width, # update PC
                        len(self.iCache))
        # exception mode
        else:
            # Attention: update `eflag` after updating `pc` and `epc` and after
            #            clearing `dir`
            # This is because `pc` and `epc` are updated only once and that
            # `dir` is cleared only once.
            # During the cycle when an exception occurs, none of `pc`, `epc`,
            # and `eflag` shall be logged as in exception mode.
            if not self.eflag:
                self.pc = self.exceptionPC
                self.epc = self.activeList.firstKey()
                self.dir.clear() # clear DIR in the first cycle of exception mode
            self.eflag = True
            # roll back instructions
            pcOfInstrToRollback: list[int] = []
            for _ in range(min(self.fetch_width,
                               len(self.activeList))):
                lastPC = self.activeList.lastKey() # reverse program order
                lastInstr = self.activeList[lastPC]

                releasedPR = self.regMap[lastInstr.logicalDest]
                self.regMap[lastInstr.logicalDest] = lastInstr.oldDest # roll back register map
                self.busy[releasedPR] = False                          # roll back busy bit table
                self.freeList.append(releasedPR)                       # roll back free list

                pcOfInstrToRollback.append(lastPC)
            # roll back active list
            for pc in pcOfInstrToRollback:
                del self.activeList[pc]

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
        return {"ActiveList": self.activeList.dump(),
                "BusyBitTable": self.busy,
                "DecodedPCs": self.dir.dump(),
                "Exception": self.eflag,
                "ExceptionPC": self.epc,
                "FreeList": self.freeList.dump(),
                "IntegerQueue": self.iq.dump(),
                "PC": self.pc,
                "PhysicalRegisterFile": self.prf,
                "RegisterMapTable": self.regMap}