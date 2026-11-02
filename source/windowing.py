"""Window placement for the app's own transparent overlay."""
import ctypes as C
from ctypes import wintypes as W

U=C.WinDLL('user32',use_last_error=True)
def bind(name,args,result):
    f=getattr(U,name);f.argtypes=args;f.restype=result;return f
bind('GetClientRect',[W.HWND,C.POINTER(W.RECT)],W.BOOL)
bind('ClientToScreen',[W.HWND,C.POINTER(W.POINT)],W.BOOL)
bind('GetWindowThreadProcessId',[W.HWND,C.POINTER(W.DWORD)],W.DWORD)
bind('IsWindowVisible',[W.HWND],W.BOOL)
bind('IsIconic',[W.HWND],W.BOOL)
bind('IsWindow',[W.HWND],W.BOOL)
bind('GetForegroundWindow',[],W.HWND)
bind('GetAncestor',[W.HWND,W.UINT],W.HWND)
bind('GetWindowLongPtrW',[W.HWND,C.c_int],C.c_ssize_t)
bind('SetWindowLongPtrW',[W.HWND,C.c_int,C.c_ssize_t],C.c_ssize_t)
bind('SetWindowPos',[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT],W.BOOL)
CALLBACK=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
bind('EnumWindows',[CALLBACK,W.LPARAM],W.BOOL)

def dpi_aware():
    try:
        bind('SetProcessDpiAwarenessContext',[C.c_void_p],W.BOOL)(C.c_void_p(-4))
    except AttributeError:U.SetProcessDPIAware()

def game_window(pid):
    found=[]
    @CALLBACK
    def collect(hwnd,_):
        owner=W.DWORD();U.GetWindowThreadProcessId(hwnd,C.byref(owner))
        if owner.value==pid and U.IsWindowVisible(hwnd):
            rect=W.RECT()
            if U.GetClientRect(hwnd,C.byref(rect)) and rect.right>320 and rect.bottom>200:found.append((rect.right*rect.bottom,hwnd))
        return True
    U.EnumWindows(collect,0)
    return max(found)[1] if found else None

def client_rect(hwnd):
    rect=W.RECT();point=W.POINT(0,0)
    if not hwnd or not U.GetClientRect(hwnd,C.byref(rect)) or not U.ClientToScreen(hwnd,C.byref(point)):return None
    return point.x,point.y,rect.right,rect.bottom

def clickthrough(tk_window):
    tk_window.update_idletasks()
    hwnd=U.GetAncestor(tk_window.winfo_id(),2)
    style=U.GetWindowLongPtrW(hwnd,-20)
    U.SetWindowLongPtrW(hwnd,-20,style|0x80000|0x20|0x80|0x08000000)
    return hwnd

def place(hwnd,rect):
    x,y,w,h=rect
    U.SetWindowPos(hwnd,C.c_void_p(-1),x,y,w,h,0x10|0x40)
