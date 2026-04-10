NAME = "SetHandleInformation"
DESCRIPTION = "Modify properties of a handle (e.g., enable inheritance)"
PARAMS = [
    {"name":"handle", "description":"The handle to modify", "type":"int"},
    {"name":"mask", "description":"The flags to change (e.g. 1 for Inherit)", "type":"hex"},
    {"name":"flags", "description":"The new value (e.g. 1 to enable)", "type":"hex"},
]
DEPENDENCIES = []

def SetHandleInformation(agent_id, h_object, mask, flags):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl # Library call service
    import struct

    agent = Agent.by_id(agent_id)
    # Resolve kernel32!SetHandleInformation
    func_addr = Syscall.sys(agent.id, "SetHandleInformation")
    
    # x64 ABI: RCX, RDX, R8
    params = [
        h_object, # P1: hObject
        mask,     # P2: dwMask (HANDLE_FLAG_INHERIT = 0x01)
        flags     # P3: dwFlags
    ]

    # Generate the library call shellcode
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    # This call does not require scratchpad data for inputs, only for the Return Value
    data = b"" 
    
    #printf"SetHandleInformation(Handle={hex(h_object)}, Mask={hex(mask)}, Flags={hex(flags)})")
    return data, shellcode

def updateHandleInheritance(agent_id, h_object, mask, flags):
    from services.orders import send_and_wait

    
    # 1. Generate the logic
    data, shellcode = SetHandleInformation(agent_id, h_object, mask, flags)
    
    # 2. Execute the library call
    # Returns non-zero on success
    success = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    #printf"SetHandleInformation Success: {bool(success)}")
    return bool(success)

def function(agent_id, args):
    # args: [handle, (optional) mask, (optional) flags]
    h_obj = args[0]
    mask = args[1]
    flags = args[2]
    
    success = updateHandleInheritance(agent_id, h_obj, mask, flags)
    return {"retval": success}