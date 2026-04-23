NAME = "CreateProcess"
DESCRIPTION = "Execute a command using kernel32!CreateProcessA with redirected handles"
PARAMS = [
    {"name":"command_line", "description":"Command to run", "type":"str"},
    {"name":"h_pipe", "description":"Handle for stdout redirection", "type":"hex", "optional":True, "default":0x0},
    {"name":"show_window", "description":"Value for wShowWindow in SI struct.", "type":"hex", "optional":True, "default":0x1},
]
DEPENDENCIES = []
DEFAULT = True

def build_si_struct(buffer_add, flags, flags_data):
    #printf"Creating STARTUP_INFORMATION_A structure. buffer_add={hex(buffer_add)}, flags={hex(flags)}, h_pipe={hex(h_pipe)}")
    import struct
    # hStdOutput = h_pipe, hStdError = h_pipe
    si_data = bytearray(104)
    struct.pack_into('<I', si_data, 0, 104)      # cb
    struct.pack_into('<I', si_data, 60, flags)   # dwFlags
    for i in range(len(flags_data)):
        flag_offset, flag_size, flag_bytes = flags_data[i]
        si_data[flag_offset:flag_offset+flag_size] = flag_bytes
    return si_data, buffer_add+104

def CreateProcessA(agent_id, command_line, h_flags, h_flags_data):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_rtl, align_up

    agent = Agent.by_id(agent_id)
    # Resolve kernel32!CreateProcessA address
    func_addr = Syscall.sys(agent.id, "CreateProcessA")
    scratchpad = agent.scratchpad

    # Memory Layout in p_private:
    # 0x0: PROCESS_INFORMATION Struct (24 bytes)
    # 0x18: STARTUPINFOA Struct (104 bytes)
    # 0x80: Command Line String (Variable)
    
    
    process_information_data, startup_info_ptr = build_ptr(scratchpad, b"\x00"*24)
    si_data, cmdline_ptr = build_si_struct(startup_info_ptr, h_flags, h_flags_data)
    cmdline_ptr = align_up(cmdline_ptr, 8)
    cmdline_data, next_ptr = build_ptr(cmdline_ptr, command_line.encode())
    


    # 10 Parameters for CreateProcessA
    params = [
        0,              # P1: lpApplicationName (NULL)
        cmdline_ptr,     # P2: lpCommandLine
        0,              # P3: lpProcessAttributes
        0,              # P4: lpThreadAttributes
        1,              # P5: bInheritHandles (TRUE)
        0,              # P6: dwCreationFlags
        0,              # P7: lpEnvironment
        0,              # P8: lpCurrentDirectory
        startup_info_ptr, # P9: lpStartupInfo
        scratchpad     # P10: lpProcessInformation
    ]

    shellcode = push_rtl(func_addr, params, agent.debug)
    data = process_information_data + si_data + cmdline_data
    param_names = [
    "lpApplicationName",
    "lpCommandLine",
    "lpProcessAttributes",
    "lpThreadAttributes",
    "bInheritHandles",
    "dwCreationFlags",
    "lpEnvironment",
    "lpCurrentDirectory",
    "lpStartupInfo",
    "lpProcessInformation",
    ]
    '''
    print"=== CreateProcess Parameters ===")
    for name, value in zip(param_names, params):
        if isinstance(value, int):
            #printf"{name:<25} = 0x{value:016X} ({value})")
        else:
            #printf"{name:<25} = {value}")
    '''
    return data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    import struct
    command = f"{args[0]}"
    h_pipe = args[1]
    wShowWindow = args[2]
    print(h_pipe)
    print(wShowWindow)
    # 2. Generate and write the function logic
    flag_data = [
        (68, 2, int.to_bytes(wShowWindow, 2, 'little')),
        (88, 8, int.to_bytes(h_pipe, 8, 'little')),
        (96, 8, int.to_bytes(h_pipe, 8, 'little'))
    ]
    data, shellcode = CreateProcessA(agent_id, command, 0x100 | 0x1 ,flag_data)
    write_scratchpad(agent_id, data)
    # 3. Execute CreateProcessA
    ret_val = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    # 4. Extract Process info if successful (BOOL 1 is success)
    h_proc, h_thread = 0, 0
    #printf"CreateProcessA = {ret_val}")
    if ret_val != 0:
        pi_raw = read_scratchpad(agent_id, 16)
        h_proc = int.from_bytes(pi_raw[:8], 'little')
        h_thread = int.from_bytes(pi_raw[8:16], 'little')

    if ret_val != 0:
        ret_val = 0
    else:
        ret_val = -1
    return {
        "retval": ret_val,
        "PROCESS_HANDLE": h_proc,
        "THREAD_HANDLE": h_thread
    }