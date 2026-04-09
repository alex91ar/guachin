NAME = "execnative"
DESCRIPTION = "Execute a process using ntdll!NtCreateUserProcess (Modern Native Spawn)"
PARAMS = [
    {"name":"path", "description":"Native path to EXE (e.g. \\??\\C:\\Windows\\System32\\calc.exe)", "type":"str"},
    {"name":"args", "description":"Command line arguments (e.g. /q)", "type":"str"}
]

# We use 5 core ntdll dependencies for this chain
DEPENDENCIES = [
    "NtAllocateVirtualMemory",      # To hold RTL_USER_PROCESS_PARAMETERS
    "RtlCreateProcessParametersEx", # To build the parameter block
    "NtCreateUserProcess",          # The core modern process creator
    "NtClose",                      # Cleanup
    "NtFreeVirtualMemory"           # Cleanup
]

def function(agent_id, args):
    from services.orders import send_and_wait, read_from_agent
    import struct

    exe_path = args[0] if args[0].startswith("\\??\\") else "\\??\\" + args[0]
    cmd_args = args[1] if len(args) > 1 else ""
    full_cmd = f"{exe_path} {cmd_args}".strip()

    # 1. CREATE PROCESS PARAMETERS (RtlCreateProcessParametersEx)
    # This initializes the structure containing the command line and environment.
    # We pass 0x01 (RTL_USER_PROCESS_PARAMETERS_NORMALIZED) to ensure pointers are valid.
    params_ret = RtlCreateProcessParametersEx(agent_id, [exe_path, full_cmd, 0x01])
    if params_ret["retval"] != 0:
        return {"retval": f"Failed to create process parameters: {hex(params_ret['retval'])}"}
    
    p_process_params = params_ret["pProcessParams"]

    # 2. EXECUTE THE PROCESS (NtCreateUserProcess)
    # Params:
    # 1. PHANDLE ProcessHandle (Returned)
    # 2. PHANDLE ThreadHandle (Returned)
    # 3. ACCESS_MASK ProcessDesiredAccess (0x1F0FFF)
    # 4. ACCESS_MASK ThreadDesiredAccess (0x1FFFFF)
    # 5. POBJECT_ATTRIBUTES ProcessObjectAttributes (NULL)
    # 6. POBJECT_ATTRIBUTES ThreadObjectAttributes (NULL)
    # 7. ULONG ProcessFlags (0)
    # 8. ULONG ThreadFlags (0)
    # 9. PRTL_USER_PROCESS_PARAMETERS ProcessParameters (The block we just created)
    # 10. PVOID CreateInfo (NULL or Pointers to PS_CREATE_INFO)
    # 11. PVOID AttributeList (NULL or Pointers to PS_ATTRIBUTE_LIST)
    
    # In this wrapper, we assume the agent handles the complex AttributeList for SEC_IMAGE
    proc_ret = NtCreateUserProcess(agent_id, [
        p_process_params,
        exe_path,           # ImagePath
        0x0                # InheritHandles
    ])

    if proc_ret["retval"] == 0:
        h_process = proc_ret["PROCESS_HANDLE"]
        h_thread  = proc_ret["THREAD_HANDLE"]
        
        # Cleanup thread/process handles immediately if we don't need to track them
        NtClose(agent_id, [h_process])
        NtClose(agent_id, [h_thread])
        result_msg = "Success"
    else:
        result_msg = f"NtCreateUserProcess failed: {hex(proc_ret['retval'])}"

    # 3. CLEANUP PARAMETER BLOCK
    # We must free the memory allocated for the process parameters in the agent
    NtFreeVirtualMemory(agent_id, [p_process_params, 0]) # MEM_RELEASE

    return {
        "retval": result_msg,
        "Path": exe_path,
        "Command": full_cmd,
        "NTSTATUS": hex(proc_ret["retval"])
    }