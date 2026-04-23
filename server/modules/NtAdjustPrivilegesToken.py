NAME = "NtAdjustPrivilegesToken"
DESCRIPTION = "Enables or disables privileges in the specified access token."
PARAMS = [
    {"name": "h_token", "description": "Handle to the access token", "type": "hex"},
    {"name": "luid_low", "description": "LUID LowPart (hex)", "type": "hex"},
    {"name": "luid_high", "description": "LUID HighPart (hex)", "type": "hex"},
    {"name": "enable", "description": "True to enable, False to disable", "type": "str", "optional": True, "default": True},
]
DEPENDENCIES = []
DEFAULT = True

def AdjustTokenPrivileges_Payload(agent_id, h_token, luid_low, luid_high, enable):
    """
    Generates shellcode to call AdjustTokenPrivileges.
    Signature: BOOL AdjustTokenPrivileges(HANDLE TokenHandle, BOOL DisableAllPrivileges, PTOKEN_PRIVILEGES NewState, DWORD BufferLength, PTOKEN_PRIVILEGES PreviousState, PDWORD ReturnLength);
    """
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall, build_ptr
    import struct

    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    func_addr = Syscall.sys(agent.id, "NtAdjustPrivilegesToken")

    # 1. Build TOKEN_PRIVILEGES structure in the scratchpad
    # Structure:
    #   DWORD PrivilegeCount (4 bytes)
    #   LUID Luid (8 bytes)
    #   DWORD Attributes (4 bytes)
    # Total: 16 bytes
    
    attributes = 0x00000002 if enable else 0x00000004 # SE_PRIVILEGE_ENABLED or SE_PRIVILEGE_REMOVED (usually 0 to disable)
    if not enable:
        attributes = 0 # 0 effectively disables the privilege
        
    tp_data = struct.pack('<I', 1)                    # PrivilegeCount = 1
    tp_data += struct.pack('<I', luid_low)            # LUID LowPart
    tp_data += struct.pack('<I', luid_high)           # LUID HighPart
    tp_data += struct.pack('<I', attributes)          # Attributes

    # Write TP struct to scratchpad
    tp_data_blob, next_ptr = build_ptr(scratchpad, tp_data)

    # x64 Calling Convention: RCX, RDX, R8, R9, [RSP+0x20], [RSP+0x28]
    params = [
        h_token,      # RCX: TokenHandle
        0,            # RDX: DisableAllPrivileges (FALSE)
        scratchpad,   # R8:  NewState (Pointer to TP structure)
        16,           # R9:  BufferLength (Size of NewState)
        0,            # P5:  PreviousState (NULL)
        0             # P6:  ReturnLength (NULL)
    ]

    shellcode = push_syscall(func_addr, params, agent.debug)
    
    return tp_data_blob, shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, write_scratchpad
    import struct

    # 1. Parse Arguments
    h_token = args[0]
    luid_low = args[1]
    luid_high = args[2]
    enable = args[3]
    if enable == "True" or enable == "true" or enable == "1":
        enable = True
    else:
        enable = False
    print(f"{h_token}, {luid_high}, {luid_low}, {enable}")

    # 2. Generate and write the TP struct/shellcode
    data, shellcode = AdjustTokenPrivileges_Payload(agent_id, h_token, luid_low, luid_high, enable)
    write_scratchpad(agent_id, data)

    # 3. Execute
    response_bytes = send_and_wait(agent_id, shellcode)
    
    # BOOL return: 1 is success, 0 is failure
    success_val = int.from_bytes(response_bytes, 'little')

    # AdjustTokenPrivileges is tricky: even if it returns TRUE, you must check GetLastError
    # because it might succeed "partially" (e.g., if the privilege isn't held by the token).
    # In this framework, success_val reflects the direct BOOL return.

    if success_val != 0:
        return {
            "success": -1, 
            "error": "AdjustTokenPrivileges returned FALSE. Check if the token has the privilege assigned."
        }

    return {
        "retval": 0,
        "h_token": hex(h_token),
        "operation": "Enabled" if enable else "Disabled",
        "luid_high": f"{hex(luid_high)}:{hex(luid_low)}"
    }