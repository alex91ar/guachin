NAME = "RtlCreateProcessParametersEx"
DESCRIPTION = "Initialize process parameters with private memory allocation"
PARAMS = [
    {"name":"image_path", "description":"NT path to binary", "type":"str"},
    {"name":"command_line", "description":"Full command line", "type":"str"},
    {"name":"h_output_pipe", "description":"Handle for redirection", "type":"hex"},
]
# Requires memory management dependencies
DEPENDENCIES = ["NtAllocateVirtualMemory", "NtFreeVirtualMemory", "RtlInitUnicodeString"]

def RtlCreateProcessParametersEx(agent_id, image_path_ptr, command_line_ptr):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, build_unicode_string, push_rtl
    import struct

    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "RtlCreateProcessParametersEx")
    scratchpad = agent.scratchpad # We still use scratchpad for the output &pParams

    # Place strings/structs in our PRIVATE allocated memory
    # 1. ImagePathName (UNICODE_STRING struct + string)
    
    # &pProcessParams (8 bytes) stays on scratchpad so we can read it back easily
    p_params_data, _ = build_ptr(scratchpad, b"\x00" * 8)

    # 11 Parameters for RtlCreateProcessParametersEx
    params = [
        scratchpad,      # P1: RCX (&pProcessParams)
        image_path_ptr,     # P2: RDX (Pointer to ImagePathName struct)
        0,               # P3: R8
        0,               # P4: R9
        command_line_ptr,     # P5: [RSP+0x28] (Pointer to CommandLine struct)
        0, 0, 0, 0, 0,
        0x01             # P11: RTL_USER_PROC_PARAMS_NORMALIZED
    ]

    shellcode = push_rtl(func_addr, params)
    
    # The actual data blob to write to the agent
    # We combine the scratchpad data and our private allocation data
    payload = p_params_data
    print(
    f"RtlCreateProcessParametersEx(\n"
    f"  P1  pProcessParameters = {hex(scratchpad)},\n"
    f"  P2  ImagePathName      = {hex(image_path_ptr)},\n"
    f"  P3  DllPath            = {hex(0)},\n"
    f"  P4  CurrentDirectory   = {hex(0)},\n"
    f"  P5  CommandLine        = {hex(command_line_ptr)},\n"
    f"  P6  Environment        = {hex(0)},\n"
    f"  P7  WindowTitle        = {hex(0)},\n"
    f"  P8  DesktopInfo        = {hex(0)},\n"
    f"  P9  ShellInfo          = {hex(0)},\n"
    f"  P10 RuntimeData        = {hex(0)},\n"
    f"  P11 Flags              = {hex(0x01)}\n"
    f")"
    )
    return payload, shellcode

def initProcessParams(agent_id, image_path_ptr, command_line_ptr, h_pipe):
    from services.orders import write_scratchpad, write_to_agent, send_and_wait, read_scratchpad
    import struct
    
    # 2. Generate and write the function logic
    data, shellcode = RtlCreateProcessParametersEx(agent_id, image_path_ptr, command_line_ptr)
    
    # Write the scratchpad pointer AND the private memory data
    write_scratchpad(agent_id, data[:8]) # Write &pParams back to scratchpad
    
    # 3. Execute
    response_ntstatus = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # 4. Retrieve pProcessParams and Patch Output Pipes
    p_params_raw = read_scratchpad(agent_id, 8)
    p_params = int.from_bytes(p_params_raw, 'little')
    
    if response_ntstatus == 0:
        h_pipe_bytes = struct.pack('<Q', h_pipe)
        write_to_agent(agent_id, p_params + 0x28, h_pipe_bytes) # StdOutput
        write_to_agent(agent_id, p_params + 0x30, h_pipe_bytes) # StdError

    return response_ntstatus, p_params

def function(agent_id, args, dependencies=[]):
    from services.binary import align_up
    NtAlloc = dependencies[0]
    NtFree  = dependencies[1]
    initUnicodeString = dependencies[2]
    image_path= args[0]
    command_line = args[1]
    h_pipe = args[2]
    # 1. ALLOCATE PRIVATE MEMORY (approx 2KB)
    mem_size = 2048
    alloc_ret = NtAlloc(agent_id, [mem_size, 0x04]) # PAGE_READWRITE
    if alloc_ret["NTSTATUS"] != 0:
        return {"NTSTATUS": alloc_ret["NTSTATUS"], "pProcessParams": 0}
    p_private = alloc_ret["allocated_memory"]
    init_ret = initUnicodeString(agent_id, [p_private, image_path])
    if init_ret["OUTLEN"] == 0:
        #NtFree(agent_id, [p_private, mem_size])
        return {"OUTLEN": init_ret["OUTLEN"], "pProcessParams": 0} 
    image_path_ptr = init_ret["buffer"]
    new_alloc = align_up(init_ret["OUTLEN"]+16, 8)
    init_ret = initUnicodeString(agent_id, [image_path_ptr+new_alloc, command_line])
    if init_ret["OUTLEN"] == 0:
        #NtFree(agent_id, [p_private, mem_size])
        return {"OUTLEN": init_ret["OUTLEN"], "pProcessParams": 0} 
    command_line_ptr = init_ret["buffer"]
    ntstatus, p_params = initProcessParams(agent_id, image_path_ptr, command_line_ptr, h_pipe)
    #NtFree(agent_id, [p_private, mem_size])
    return {"NTSTATUS": ntstatus, "pProcessParams": p_params}