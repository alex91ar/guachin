NAME = "MessageBox"
DESCRIPTION = "Trigger a graphical message box on the target agent"
PARAMS = [
    {"name":"text", "description":"Message text", "type":"str"},
    {"name":"title", "description":"Message box title", "type":"str"},
]
# Requires memory management for storing the strings
DEPENDENCIES = []
DEFAULT = True

def MessageBoxA(agent_id, text, title):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr, align_up# Using our library call service
    import struct

    agent = Agent.by_id(agent_id)
    # Resolve user32!MessageBoxA address (Note: your agent must load user32.dll if not present)
    func_addr = Syscall.sys(agent.id, "MessageBoxA")
    
    # Memory Layout in p_private:
    # 0x00: Message Text String
    # 0x100: Message Title String
    scratchpad = agent.scratchpad

    # 1. Prepare String Data (ANSI)
    text_bytes = text.encode('ascii')+b'\x00'
    title_bytes = title.encode('ascii') + b'\x00'
    text_data, title_ptr = build_ptr(scratchpad, text_bytes)
    title_data, next_ptr = build_ptr(title_ptr, title_bytes)
    # 4 Parameters for MessageBoxA (x64 ABI)
    params = [
        0,       # P1: hWnd (NULL)
        scratchpad,  # P2: lpText
        title_ptr, # P3: lpCaption
        0x40     # P4: uType (MB_OK | MB_ICONINFORMATION)
    ]

    # Generate the library call shellcode
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    # Combine the data for the private buffer
    data = text_data + title_data
    
    #printf"MessageBoxA(Text='{text}', Title='{title}', pText={hex(scratchpad)}, pTitle={hex(title_ptr)})")
    return data, shellcode

def showMessageBox(agent_id, text, title):
    from services.orders import write_scratchpad, send_and_wait

    # 2. Generate and write the function logic
    data, shellcode = MessageBoxA(agent_id, text, title)
    #printdata)
    write_scratchpad(agent_id, data)
    
    # 3. Execute the call
    # Note: THIS WILL BLOCK your agent until the user clicks "OK" !
    ret_val = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')

    return {"Clicked": ret_val}

def function(agent_id, args):
    text = args[0]
    title = args[1]

    result = showMessageBox(agent_id, text, title)
    return result