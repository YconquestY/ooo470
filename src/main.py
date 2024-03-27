import sys
import json

from OoO470 import OoO470

if __name__ == '__main__':
    inPath = sys.argv[1]
    outPath = sys.argv[2]

    with open(inPath, 'r') as fin:
        instructions: list[str] = json.load(fin)
    
    ooo470 = OoO470(instructions=instructions)

    stop = False
    log: list = []
    while not stop:
        stop = ooo470.next()
        log.append(ooo470.dump())
    
    with open(outPath, 'w') as fout:
        json.dump(log, fout, indent=4)
