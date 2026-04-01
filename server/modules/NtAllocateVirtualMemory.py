NAME = "NtAllocateVirtualMemory"
DESCRIPTION = "Allocate memory in the target agent"
PARAMS = [
    {"name":"size", "description":"Size of allocated memory", "type":"hex"},
    {"name":"protection", "description":"Protection constant", "type":"hex"}
]

def NtAllocateVirtualMemory(agent_id, size, protection):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall, build_ptr
    import struct
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtAllocateVirtualMemory")
    scratchpad = agent.scratchpad
    ProcessHandle = 0xFFFFFFFFFFFFFFFF
    BaseAddress_data, RegionSize_ptr = build_ptr(scratchpad, b"\x00\x00\x00\x00\x00\x00\x00\x00")
    zero_bits = 0
    RegionSize_data, next_ptr = build_ptr(RegionSize_ptr, struct.pack('<Q', size))
    AllocationType = 0x3000
    data = BaseAddress_data + RegionSize_data
    print(
        f"NtAllocateVirtualMemory("
        f"ProcessHandle={hex(ProcessHandle)}, "
        f"BaseAddress={hex(scratchpad)}, "
        f"ZeroBits={zero_bits}, "
        f"RegionSizePtr={hex(RegionSize_ptr)}, "
        f"RegionSize={size}, "
        f"AllocationType={hex(AllocationType)}, "
        f"Protection={hex(protection)}"
        f")"
    )

    return (data, push_syscall(syscall, [ProcessHandle, scratchpad, zero_bits, RegionSize_ptr, AllocationType, protection], agent.debug))


def allocate_memory(agent_id, size, protection):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    data, shellcode = NtAllocateVirtualMemory(agent_id, size, protection)
    write_scratchpad(agent_id, data)
    response_data = int.from_bytes(send_and_wait(agent_id, shellcode), byteorder='little')
    scratchpad = read_scratchpad(agent_id, 8)
    base_address = int.from_bytes(scratchpad[:8], byteorder='little')
    print(f"Response from NtAllocateVirtualMemory = {hex(response_data)}. base_address = {hex(base_address)}")
    return response_data, base_address # retparams[0] contains BaseAddress

def function(agent_id, args):
    retval, allocated_memory = allocate_memory(agent_id, args[0], args[1])
    return {"retval":retval, "allocated_memory":allocated_memory}