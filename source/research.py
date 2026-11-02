import sys,struct,re,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from memory import Process

p=Process(int(sys.argv[1]));module=next(x for x in p.modules() if x['name']=='RelicCardinal.exe');base=module['base']
cs=Cs(CS_ARCH_X86,CS_MODE_64)
def dis(rva,size=320):
    print('\nFUNCTION',hex(rva))
    for ins in cs.disasm(p.read(base+rva,size),base+rva):
        print(hex(ins.address-base),ins.mnemonic,ins.op_str)
        if ins.mnemonic=='ret':break
if sys.argv[2]=='dis':
    for a in sys.argv[3:]:dis(int(a,16))
elif sys.argv[2]=='bindings':
    b=p.read(base,module['size']);names=sys.argv[3:];targets={n:b.find(n.encode()+b'\0') for n in names};found={}
    for mt in re.finditer(rb'[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]',b[:0x580f000]):
        i=mt.start();t=i+7+struct.unpack_from('<i',b,i+3)[0]
        for name,off in targets.items():
            if off>=0 and -16<=t-off<=0:
                for ins in cs.disasm(b[i:i+40],base+i):
                    if ins.mnemonic=='lea' and ins.op_str.startswith('r9, [rip'):
                        d=struct.unpack('<i',ins.bytes[-4:])[0];found[name]=ins.address+ins.size+d-base
    print(json.dumps(found,indent=2));Path('bindings.json').write_text(json.dumps(found,indent=2))
    for n,rva in found.items():print('\n',n);dis(rva)
p.close()
