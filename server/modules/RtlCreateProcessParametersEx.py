NAME = "RtlCreateProcessParametersEx"
DESCRIPTION = "Initialize process parameters with private memory allocation"
PARAMS = [
    {"name":"image_path", "description":"NT path to binary", "type":"str"},
    {"name":"command_line", "description":"Full command line", "type":"str"},
    {"name":"h_output_pipe", "description":"Handle for redirection", "type":"hex"},
]
# Requires memory management dependencies
DEPENDENCIES = ["NtAllocateVirtualMemory", "NtFreeVirtualMemory", "RtlInitUnicodeString"]

def RtlCreateProcessParametersEx(agent_id, image_path, command_line):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_rtl, build_unicode_string
    import struct
    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "RtlCreateProcessParametersEx")
    scratchpad = agent.scratchpad

    ProcessParams_data, image_path_ptr = build_ptr(scratchpad, b"\x00"*8)
    image_path_data, command_line_ptr = build_unicode_string(image_path_ptr, image_path)
    command_line_data, desktopinfo_ptr = build_unicode_string(command_line_ptr, command_line)
    desktopinfo_Data, next_ptr  = build_unicode_string(command_line_ptr, "Winsta0\\Default")
    # 11 Parameters for     
    params = [
        scratchpad,      # P1: RCX (&pProcessParams)
        image_path_ptr,     # P2: RDX (Pointer to ImagePathName struct)
        0,               # P3: R8
        0,               # P4: R9
        command_line_ptr,     # P5: [RSP+0x28] (Pointer to CommandLine struct)
        0, 0, desktopinfo_ptr, 0, 0,
        0x01             # P11: RTL_USER_PROC_PARAMS_NORMALIZED
    ]

    shellcode = push_rtl(func_addr, params, agent.debug)
    
    # The actual data blob to write to the agent
    # We combine the scratchpad data and our private allocation data
    payload = ProcessParams_data + image_path_data + command_line_data + desktopinfo_Data
    '''
    #print
    f"RtlCreateProcessParametersEx(\n"
    f"  P1  pProcessParameters = {hex(scratchpad)},\n"
    f"  P2  ImagePathName      = {hex(image_path_ptr)},\n"
    f"  P3  DllPath            = {hex(0)},\n"
    f"  P4  CurrentDirectory   = {hex(0)},\n"
    f"  P5  CommandLine        = {hex(command_line_ptr)},\n"
    f"  P6  Environment        = {hex(0)},\n"
    f"  P7  WindowTitle        = {hex(0)},\n"
    f"  P8  DesktopInfo        = {hex(desktopinfo_ptr)},\n"
    f"  P9  ShellInfo          = {hex(0)},\n"
    f"  P10 RuntimeData        = {hex(0)},\n"
    f"  P11 Flags              = {hex(0x01)}\n"
    f")"
    )
    '''
    return payload, shellcode

def initProcessParams(agent_id, image_path, command_line, h_pipe):
    from services.orders import write_scratchpad, write_to_agent, send_and_wait, read_scratchpad
    import struct
    
    # 2. Generate and write the function logic
    data, shellcode = RtlCreateProcessParametersEx(agent_id, image_path, command_line)
    
    # Write the scratchpad pointer AND the private memory data
    write_scratchpad(agent_id, data) # Write &pParams back to scratchpad
    
    # 3. Execute
    response_retval = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # 4. Retrieve pProcessParams and Patch Output Pipes
    p_params_raw = read_scratchpad(agent_id, 8)
    p_params = int.from_bytes(p_params_raw, 'little')
    if response_retval == 0:
        h_pipe_bytes = struct.pack('<Q', h_pipe)
        write_to_agent(agent_id, p_params + 0x28, h_pipe_bytes) # StdOutput
        write_to_agent(agent_id, p_params + 0x30, h_pipe_bytes) # StdError
    #printf"RtlCreateProcessParametersEx status = {hex(response_retval)}, p_param = {p_params}")
    return response_retval, p_params

def function(agent_id, args):
    from services.binary import align_up
    image_path= args[0]
    command_line = args[1]
    h_pipe = args[2]
    retval, p_params = initProcessParams(agent_id, image_path, command_line, h_pipe)
    return {"retval": retval, "pProcessParams": p_params}