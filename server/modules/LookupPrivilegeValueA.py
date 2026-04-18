NAME = "LookupPrivilegeValueA"
DESCRIPTION = "Retrieves the LUID for a privilege name (e.g., SeDebugPrivilege) on a specific system."
PARAMS = [
    {"name": "privilege_name", "description": "The name of the privilege (Unicode)", "type": "str"},
]
DEPENDENCIES = []
DEFAULT = True

def LookupPrivilegeValueW_Payload(agent_id, privilege_name):
    """
    Generates shellcode to call LookupPrivilegeValueW.
    Signature: BOOL LookupPrivilegeValueW(LPCWSTR lpSystemName, LPCWSTR lpName, PLUID lpLuid);
    """
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr, align_up
    import struct

    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    func_addr = Syscall.sys(agent.id, "LookupPrivilegeValueA")

    # Memory Layout in Scratchpad:
    # 0x00: LUID Result (8 bytes)
    # 0x08: Privilege Name String (Variable, Null-terminated Unicode)

    # 1. Reserve 8 bytes for the LUID output
    luid_data, name_ptr = build_ptr(scratchpad, b"\x00" * 8)
    
    # 2. Build the Null-terminated Unicode String for the privilege name
    name_encoded = privilege_name.encode('utf-8') + b'\x00'
    name_data, next_ptr = build_ptr(name_ptr, name_encoded)

    # x64 Calling Convention: RCX, RDX, R8
    params = [
        0,          # RCX: lpSystemName (NULL for local system)
        name_ptr,   # RDX: lpName (Pointer to the Unicode string)
        scratchpad  # R8:  lpLuid (Pointer to the 8-byte buffer at the start of scratchpad)
    ]

    shellcode = push_rtl(func_addr, params, agent.debug)
    full_data = luid_data + name_data
    
    return full_data, shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, read_scratchpad, write_scratchpad
    import struct

    try:
        # 1. Parse Arguments
        privilege_name = args[0]

        # 2. Generate and write the data/shellcode
        data, shellcode = LookupPrivilegeValueW_Payload(agent_id, privilege_name)
        write_scratchpad(agent_id, data)

        # 3. Execute
        response_bytes = send_and_wait(agent_id, shellcode)
        
        # BOOL return: 1 is success, 0 is failure
        success_val = int.from_bytes(response_bytes, 'little')

        luid_low = 0
        luid_high = 0
        if success_val != 0:
            # 4. Read the 8-byte LUID structure from the start of the scratchpad
            # LUID is two 32-bit integers: LowPart and HighPart
            luid_raw = read_scratchpad(agent_id, 8)
            luid_low = int.from_bytes(luid_raw[:4], 'little')
            luid_high = int.from_bytes(luid_raw[4:8], 'little')

        if success_val == 0:
            return {
                "retval": -1, 
                "message": "LookupPrivilegeValueW returned FALSE. Verify the privilege name string."
            }

        return {
            "retval": 0,
            "privilege": privilege_name,
            "luid_low": hex(luid_low),
            "luid_high": hex(luid_high),
            "luid_full_hex": hex(int.from_bytes(luid_raw, 'little'))
        }

    except Exception as e:
        return {"reval": -1, "message": str(e)}