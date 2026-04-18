NAME = "GetLastError"
DESCRIPTION = "Gets last error"
PARAMS = [
]
# Requires memory management for storing the strings
DEPENDENCIES = []
DEFAULT = True

def getlasterror(agent_id):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr, align_up# Using our library call service
    import struct

    agent = Agent.by_id(agent_id)
    # Resolve user32!MessageBoxA address (Note: your agent must load user32.dll if not present)
    func_addr = Syscall.sys(agent.id, "GetLastError")
    
    # Memory Layout in p_private:
    # 0x00: Message Text String
    # 0x100: Message Title String

    # 4 Parameters for MessageBoxA (x64 ABI)
    params = [
    ]

    # Generate the library call shellcode
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    # Combine the data for the private buffer
    
    #printf"MessageBoxA(Text='{text}', Title='{title}', pText={hex(scratchpad)}, pTitle={hex(title_ptr)})")
    return shellcode

def getlasterror_internal(agent_id):
    from services.orders import write_scratchpad, send_and_wait

    # 2. Generate and write the function logic
    shellcode = getlasterror(agent_id)
    
    # 3. Execute the call
    # Note: THIS WILL BLOCK your agent until the user clicks "OK" !
    ret_val = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')

    return {"retval": ret_val}

def function(agent_id, args):

    result = getlasterror_internal(agent_id)
    return result