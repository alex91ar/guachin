import struct

def generate_x64_push_syscall(syscall_number, params):
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
            # MOV RAX, imm64
            bytecode.extend(b'\x48\xb8')
            bytecode.extend(struct.pack('<Q', param))
            # PUSH RAX
            bytecode.extend(b'\x50')

    # 2. ALLOCATE SHADOW SPACE (0x20 bytes) LAST
    # This pushes RSP down, placing the parameters we just pushed 
    # exactly at [RSP + 0x20] and [RSP + 0x28].
    bytecode.extend(b'\x48\x83\xec\x20')

    # 3. Load Parameters 1-4 into Registers (RCX, RDX, R8, R9)
    regs = [b'\x48\xb9', b'\x48\xba', b'\x49\xb8', b'\x49\xb9']
    for i in range(min(len(params), 4)):
        bytecode.extend(regs[i])
        bytecode.extend(struct.pack('<Q', params[i]))

    # 4. Set Syscall Number (MOV EAX, syscall_id)
    bytecode.extend(b"\x49\x89\xca")
    bytecode.extend(b'\xb8')
    bytecode.extend(struct.pack('<I', syscall_number))

    # 5. Syscall Instruction
    bytecode.extend(b'\x0f\x05')
    bytecode.extend(b"\x48\x83\xc4\x20")
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
    # 6. Ret
    bytecode.extend(b'\xcc')

    return bytes(bytecode)