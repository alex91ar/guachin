NAME = "NtWaitForSingleObject"
DESCRIPTION = "Wait for an object (like a process) to enter a signaled state"
PARAMS = [
    {"name":"handle", "description":"Handle to the object", "type":"hex"},
    {"name":"timeout_ms", "description":"Timeout in milliseconds (-1 for infinite)", "type":"int"}
]
DEFAULT = True

def NtWaitForSingleObject(agent_id, handle, timeout_ms=-1):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    import struct

    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtWaitForSingleObject") # Syscall 0x04
    scratchpad = agent.scratchpad

    # 1. Handle Timeout Logic
    # Windows native timeouts are relative if negative and in 100ns units.
    # ms * -10000 = relative 100ns units.
    if timeout_ms == -1:
        # Infinite Wait: Pass a NULL pointer for the timeout parameter
        p_timeout = 0x0
        timeout_data = b""
    else:
        timeout_val = timeout_ms * -10000
        timeout_data, next_ptr = build_ptr(scratchpad, struct.pack('<q', timeout_val))
        p_timeout = scratchpad

    # 3 Parameters for x64 syscall: R10, RDX, R8
    params = [
        handle,    # P1: R10
        0,         # P2: RDX (Alertable = FALSE)
        p_timeout  # P3: R8  (&Timeout)
    ]

    shellcode = push_syscall(syscall, params, agent.debug)
    
    #printf"NtWaitForSingleObject(Handle={hex(handle)}, Timeout={timeout_ms}ms)")
    return timeout_data, shellcode

def waitForSingleObject(agent_id, handle, timeout_ms):
    from services.orders import send_and_wait, write_scratchpad
    
    data, shellcode = NtWaitForSingleObject(agent_id, handle, timeout_ms)
    
    # Write the timeout structure to scratchpad if we aren't waiting infinitely
    if data:
        write_scratchpad(agent_id, data)
        
    # SYSCALL EXECUTION
    # This call will block on the agent until the object is signaled OR timeout occurs
    response_data = int.from_bytes(send_and_wait(agent_id, shellcode), byteorder='little')
    
    #printf"Response from NtWaitForSingleObject = {hex(response_data)}")
    return response_data

def function(agent_id, args):
    timeout = args[1]
    retval = waitForSingleObject(agent_id, args[0], timeout)
    return {"retval": retval}