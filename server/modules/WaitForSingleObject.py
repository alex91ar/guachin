NAME = "WaitForSingleObject"
DESCRIPTION = "Wait for a handle to become signaled on the target agent"
PARAMS = [
    {"name": "handle", "description": "Target handle value", "type": "hex"},
    {"name": "timeout_ms", "description": "Timeout in milliseconds (use 0xFFFFFFFF for INFINITE)", "type": "int"},
]
DEPENDENCIES = []
DEFAULT = True

def WaitForSingleObject(agent_id, handle, timeout_ms):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl

    agent = Agent.by_id(agent_id)

    # Resolve kernel32!WaitForSingleObject
    func_addr = Syscall.sys(agent.id, "WaitForSingleObject")

    # Win64 ABI:
    # RCX = HANDLE hHandle
    # RDX = DWORD  dwMilliseconds
    params = [
        handle,       # P1: hHandle
        timeout_ms    # P2: dwMilliseconds
    ]

    shellcode = push_rtl(func_addr, params, agent.debug)
    '''
    #print
        f"WaitForSingleObject("
        f"Handle={hex(handle)}, "
        f"Timeout={hex(timeout_ms)} ({timeout_ms}), "
        f"Func={hex(func_addr)})"
    )
    '''
    return b"", shellcode


def doWaitForSingleObject(agent_id, handle, timeout_ms):
    from services.orders import write_scratchpad, send_and_wait

    data, shellcode = WaitForSingleObject(agent_id, handle, timeout_ms)

    if data:
        write_scratchpad(agent_id, data)

    ret_val = int.from_bytes(send_and_wait(agent_id, shellcode), "little")

    # Common Win32 return values:
    # 0x00000000 = WAIT_OBJECT_0
    # 0x00000080 = WAIT_ABANDONED
    # 0x00000102 = WAIT_TIMEOUT
    # 0xFFFFFFFF = WAIT_FAILED
    return {"WaitResult": ret_val}


def function(agent_id, args):
    handle = int(args[0])
    timeout_ms = int(args[1])

    result = doWaitForSingleObject(agent_id, handle, timeout_ms)
    return result