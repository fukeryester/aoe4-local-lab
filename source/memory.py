"""Read-only, 64-bit Windows process inspection. No target writes or injection."""
import ctypes as C
from ctypes import wintypes as W
import struct

K = C.WinDLL('kernel32', use_last_error=True)
class MODULEENTRY32W(C.Structure):
    _fields_ = [('dwSize',W.DWORD),('th32ModuleID',W.DWORD),('th32ProcessID',W.DWORD),
        ('GlblcntUsage',W.DWORD),('ProccntUsage',W.DWORD),('modBaseAddr',C.c_void_p),
        ('modBaseSize',W.DWORD),('hModule',W.HMODULE),('szModule',W.WCHAR*256),('szExePath',W.WCHAR*260)]
class MBI(C.Structure):
    _fields_ = [('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),('AllocationProtect',W.DWORD),
        ('PartitionId',W.WORD),('RegionSize',C.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]
class PROCESSENTRY32W(C.Structure):
    _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),
        ('th32DefaultHeapID',C.c_size_t),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),
        ('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]
def setup(name,args,result):
    f=getattr(K,name);f.argtypes=args;f.restype=result;return f
setup('OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE)
setup('CloseHandle',[W.HANDLE],W.BOOL)
setup('CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE)
setup('Module32FirstW',[W.HANDLE,C.POINTER(MODULEENTRY32W)],W.BOOL)
setup('Module32NextW',[W.HANDLE,C.POINTER(MODULEENTRY32W)],W.BOOL)
setup('ReadProcessMemory',[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],W.BOOL)
setup('VirtualQueryEx',[W.HANDLE,C.c_void_p,C.POINTER(MBI),C.c_size_t],C.c_size_t)
setup('Process32FirstW',[W.HANDLE,C.POINTER(PROCESSENTRY32W)],W.BOOL)
setup('Process32NextW',[W.HANDLE,C.POINTER(PROCESSENTRY32W)],W.BOOL)

def game_pids():
    h=K.CreateToolhelp32Snapshot(2,0)
    if h==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    try:
        e=PROCESSENTRY32W();e.dwSize=C.sizeof(e);ok=K.Process32FirstW(h,C.byref(e));ids=[]
        while ok:
            if e.szExeFile.lower()=='reliccardinal.exe':ids.append(e.th32ProcessID)
            ok=K.Process32NextW(h,C.byref(e))
        return ids
    finally:K.CloseHandle(h)

class Process:
    def __init__(self,pid):
        self.pid=pid;self.handle=K.OpenProcess(0x410,False,pid)
        if not self.handle:raise C.WinError(C.get_last_error())
        self.bytes_read=0;self.read_calls=0
    def close(self):
        if self.handle:K.CloseHandle(self.handle);self.handle=None
    def read(self,address,size):
        if not 0 < address < 0x7fffffffffff or not 0 <= size <= 256*1024*1024:raise ValueError('Invalid read bounds')
        b=C.create_string_buffer(size);n=C.c_size_t()
        self.read_calls+=1
        ok=K.ReadProcessMemory(self.handle,address,b,size,C.byref(n));self.bytes_read+=n.value
        if not ok or n.value!=size:raise OSError(C.get_last_error(),f'Read failed at {address:#x}, {n.value}/{size}')
        return b.raw
    def u64(self,a):return struct.unpack('<Q',self.read(a,8))[0]
    def u32(self,a):return struct.unpack('<I',self.read(a,4))[0]
    def modules(self):
        h=K.CreateToolhelp32Snapshot(0x18,self.pid)
        if h==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
        try:
            e=MODULEENTRY32W();e.dwSize=C.sizeof(e);ok=K.Module32FirstW(h,C.byref(e));out=[]
            while ok:
                out.append(dict(name=e.szModule,base=e.modBaseAddr,size=e.modBaseSize,path=e.szExePath))
                ok=K.Module32NextW(h,C.byref(e))
            return out
        finally:K.CloseHandle(h)
    def regions(self):
        a=0;m=MBI()
        while K.VirtualQueryEx(self.handle,a,C.byref(m),C.sizeof(m)):
            base=m.BaseAddress or 0;end=base+m.RegionSize
            if end<=a:break
            if m.State==0x1000 and not m.Protect&0x101 and m.Protect&0xee:
                yield base,m.RegionSize,m.Protect,m.Type
            a=end

if __name__=='__main__':
    import sys,json
    p=Process(int(sys.argv[1]));mods=p.modules();m=next(m for m in mods if m['name'].lower()=='reliccardinal.exe')
    print(json.dumps(m));base=m['base'];head=p.read(base,4096);pe=struct.unpack_from('<I',head,0x3c)[0]
    ns=struct.unpack_from('<H',head,pe+6)[0];os=struct.unpack_from('<H',head,pe+20)[0]
    for i in range(ns):
        o=pe+24+os+i*40;name=head[o:o+8].split(b'\0')[0].decode();size,rva=struct.unpack_from('<II',head,o+8)
        try:
            data=p.read(base+rva,size)
            for needle in [b'Entity_GetPosition',b'World_GetAllEntities',b'Player_GetUIColour',b'.?AVEntity@',b'.?AVWorld@',b'.?AVCamera@']:
                a=data.find(needle)
                if a>=0:print(name,needle.decode(),hex(base+rva+a))
            print(name,'read',len(data))
        except OSError as e:print(name,str(e))
    p.close()
