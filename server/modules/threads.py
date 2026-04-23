NAME = "threads"
DESCRIPTION = "Enumerate threads from ntdll!NtQuerySystemInformation(SystemProcessInformation)."
PARAMS = [
]

DEPENDENCIES = ["NtQuerySystemInformation"]
DEFAULT = True


def normalize_raw_buffer(raw_buffer):
    if raw_buffer is None:
        raise ValueError("raw_buffer is None")

    if isinstance(raw_buffer, (bytes, bytearray)):
        return bytes(raw_buffer)

    if isinstance(raw_buffer, list):
        return bytes(raw_buffer)

    if isinstance(raw_buffer, str):
        return bytes.fromhex(raw_buffer)

    raise TypeError(f"Unsupported raw_buffer type: {type(raw_buffer).__name__}")


def parse_system_thread_information(blob, offset, count):
    import struct

    # SYSTEM_THREAD_INFORMATION / SYSTEM_EXTENDED_THREAD_INFORMATION
    # thread array in SystemProcessInformation uses 0x50-byte thread entries on x64
    fmt = (
        "<"
        "q"   # KernelTime
        "q"   # UserTime
        "q"   # CreateTime
        "I"   # WaitTime
        "4x"  # align next pointer/handle fields
        "Q"   # StartAddress
        "Q"   # ClientId.UniqueProcess
        "Q"   # ClientId.UniqueThread
        "i"   # Priority
        "i"   # BasePriority
        "I"   # ContextSwitches
        "I"   # ThreadState
        "I"   # WaitReason
        "4x"  # tail padding
    )
    thread_size = struct.calcsize(fmt)

    threads = []
    current_offset = offset

    for _ in range(count):
        if current_offset + thread_size > len(blob):
            break

        fields = struct.unpack_from(fmt, blob, current_offset)

        threads.append({
            "kernel_time": fields[0],
            "user_time": fields[1],
            "create_time": fields[2],
            "wait_time": fields[3],
            "start_address": hex(fields[4]),
            "pid": fields[5],
            "tid": fields[6],
            "priority": fields[7],
            "base_priority": fields[8],
            "context_switches": fields[9],
            "thread_state": fields[10],
            "wait_reason": fields[11],
            "entry_offset": current_offset,
        })

        current_offset += thread_size

    return threads


def function(agent_id, args):
    import struct

    SYSTEM_PROCESS_INFORMATION_CLASS = 5
    filter_pid = None

    ret = NtQuerySystemInformation(agent_id, [SYSTEM_PROCESS_INFORMATION_CLASS])

    if not ret:
        return {"retval": -1, "message": "NtQuerySystemInformation returned no result"}

    if ret.get("retval") != 0:
        return {"retval": -1, "message": f"NtQuerySystemInformation failed {ret.get('retval')}"}

    try:
        blob = normalize_raw_buffer(ret.get("raw_buffer"))
    except Exception as e:
        return {"retval": -1, "message": f"Failed to normalize raw_buffer: {e}"}

    # x64 SYSTEM_PROCESS_INFORMATION fixed header
    # This matches the layout you've been parsing earlier.
    process_fmt = (
        "<"
        "I"      # NextEntryOffset
        "I"      # NumberOfThreads
        "48s"    # Reserved1
        "H"      # ImageName.Length
        "H"      # ImageName.MaximumLength
        "4x"     # align Buffer
        "Q"      # ImageName.Buffer
        "i"      # BasePriority
        "4x"     # align UniqueProcessId
        "Q"      # UniqueProcessId
        "Q"      # InheritedFromUniqueProcessId
        "I"      # HandleCount
        "I"      # SessionId
        "Q"      # Reserved3
        "Q"      # PeakVirtualSize
        "Q"      # VirtualSize
        "I"      # Reserved4
        "4x"     # align next SIZE_T
        "Q"      # PeakWorkingSetSize
        "Q"      # WorkingSetSize
        "Q"      # Reserved5
        "Q"      # QuotaPagedPoolUsage
        "Q"      # Reserved6
        "Q"      # QuotaNonPagedPoolUsage
        "Q"      # PagefileUsage
        "Q"      # PeakPagefileUsage
        "Q"      # PrivatePageCount
        "6q"     # Reserved7[6]
    )
    process_header_size = struct.calcsize(process_fmt)

    all_process_threads = []
    offset = 0

    while True:
        if offset + process_header_size > len(blob):
            break

        try:
            fields = struct.unpack_from(process_fmt, blob, offset)
        except Exception as e:
            return {
                "retval": -1,
                "message": f"Failed to unpack process entry at offset {offset}: {e}"
            }

        next_entry_offset = fields[0]
        number_of_threads = fields[1]
        pid = fields[7]
        parent_pid = fields[8]

        if filter_pid is None or pid == filter_pid:
            thread_start_offset = offset + process_header_size
            threads = parse_system_thread_information(blob, thread_start_offset, number_of_threads)

            all_process_threads.append({
                "pid": pid,
                "parent_pid": parent_pid,
                "thread_count": len(threads),
                "threads": threads
            })

        if next_entry_offset == 0:
            break

        if next_entry_offset < process_header_size:
            return {
                "retval": -1,
                "message": f"Corrupt NextEntryOffset {next_entry_offset} at offset {offset}"
            }

        offset += next_entry_offset

    return {
        "retval": 0,
        "process_count": len(all_process_threads),
        "total_threads": sum(item["thread_count"] for item in all_process_threads),
        "data": all_process_threads
    }