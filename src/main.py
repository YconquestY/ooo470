import sys
import json

from OoO470 import OoO470

if __name__ == '__main__':
    inPath = sys.argv[1]
    outPath = sys.argv[2]

    with open(inPath, 'r') as fin:
        instructions: list[str] = json.load(fin)
    
    cycle: int = 0
    log: list = []
    ooo470 = OoO470(instructions=instructions)
    print('cycle', format(cycle, '02d'))
    log.append(ooo470.dump())

    stop = False
    
    while not stop:
        cycle += 1
        print('cycle', format(cycle, '02d'), end=' ')
        stop = ooo470.next()
        log.append(ooo470.dump())

        if cycle == 100:
            break
    
    with open(outPath, 'w') as fout:
        json.dump(log, fout, indent=4)
