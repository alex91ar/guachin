NAME = "ControlService"
DESCRIPTION = "Sends a control code to a service (e.g., Stop, Pause, Continue)."
PARAMS = [
    {"name": "h_service", "description": "Handle to the service (from OpenServiceW)", "type": "hex"},
    {"name": "dwControl", "description": "Control code (1=STOP, 2=PAUSE, 3=CONTINUE)", "type": "int", "optional": True, "default": 1}
]
DEPENDENCIES = []
DEFAULT = True

def ControlService_Payload(agent_id, h_service, dwControl):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl
    
    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "ControlService")
    scratchpad = agent.scratchpad
    
    # Signature:
    # BOOL ControlService(
    #   SC_HANDLE           hService,
    #   DWORD               dwControl,
    #   LPSERVICE_STATUS    lpServiceStatus (Pointer to receive latest status)
    # );
    
    # We use the scratchpad to receive the SERVICE_STATUS structure (28 bytes)
    params = [
        h_service,   # hService
        dwControl,   # dwControl (1 for SERVICE_CONTROL_STOP)
        scratchpad   # lpServiceStatus
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return b"", shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, read_scratchpad
    import struct
    
    h_service = args[0]
    control_code = args[1]

    data, shellcode = ControlService_Payload(agent_id, h_service, control_code)
    
    response = send_and_wait(agent_id, shellcode)
    success = int.from_bytes(response, 'little')

    # Read back the SERVICE_STATUS structure from scratchpad
    # Offset 4 is dwCurrentState
    status_blob = read_scratchpad(agent_id, 28)
    current_state = struct.unpack("<I", status_blob[4:8])[0] if success else 0

    return {
        "retval": 0 if success != 0 else -1,
        "status": "Accepted" if success != 0 else "Failed",
        "last_state": current_state # 3 = STOP_PENDING, 1 = STOPPED
    }