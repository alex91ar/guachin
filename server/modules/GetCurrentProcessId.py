NAME = "GetCurrentProcessId"
DESCRIPTION = "Get the current process id."
PARAMS = [
]
DEFAULT = True

def getCurrentProcessId():
    shellcode = b"\x65\x48\x8B\x04\x25\x30\x00\x00\x00" #mov rax, qword ptr gs:[0x0000000000000030]
    shellcode += b"\x8B\x40\x40" #mov eax, dword ptr ds:[rax+0x40]
    shellcode += b"\xC3" # ret
    shellcode += b"\xCC*4" # padding
    return shellcode

def function(agent_id, args):
    from services.orders import send_and_wait
    shellcode = getCurrentProcessId()
    retval = send_and_wait(agent_id, shellcode)
    if retval != 0:
        return {"retval":0, "pid":hex(int.from_bytes(retval,'little'))}
    else:
        return {"retval":-1}