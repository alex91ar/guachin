NAME = "ps"
DESCRIPTION = "Enumerate processes using ntdll!NtQuerySystemInformation."
PARAMS = []

DEPENDENCIES = ["NtQuerySystemInformation"]
DEFAULT = True

def parse_system_process_information(scratchpad, raw_buffer):
    import struct

    if raw_buffer is None:
        raise ValueError("raw_buffer is None")

    if isinstance(raw_buffer, (bytes, bytearray)):
        blob = bytes(raw_buffer)
    elif isinstance(raw_buffer, list):
        blob = bytes(raw_buffer)
    elif isinstance(raw_buffer, str):
        blob = bytes.fromhex(raw_buffer)
    else:
        raise TypeError(f"Unsupported raw_buffer type: {type(raw_buffer).__name__}")

    # Official documented x64 fixed header:
    #
    # ULONG NextEntryOffset;                     4
    # ULONG NumberOfThreads;                    4
    # BYTE  Reserved1[48];                     48
    # UNICODE_STRING ImageName;                16  => HH4xQ
    # KPRIORITY BasePriority;                   4
    # padding                                  4   => align HANDLE
    # HANDLE UniqueProcessId;                   8
    # HANDLE InheritedFromUniqueProcessId;      8
    # ULONG HandleCount;                        4
    # ULONG SessionId;                          4
    # PVOID Reserved3;                          8
    # SIZE_T PeakVirtualSize;                   8
    # SIZE_T VirtualSize;                       8
    # ULONG Reserved4;                          4
    # padding                                  4
    # SIZE_T PeakWorkingSetSize;                8
    # SIZE_T WorkingSetSize;                    8
    # PVOID Reserved5;                          8
    # SIZE_T QuotaPagedPoolUsage;               8
    # PVOID Reserved6;                          8
    # SIZE_T QuotaNonPagedPoolUsage;            8
    # SIZE_T PagefileUsage;                     8
    # SIZE_T PeakPagefileUsage;                 8
    # SIZE_T PrivatePageCount;                  8
    # LARGE_INTEGER Reserved7[6];              48
    #
    fmt = (
        "<"
        "I"      # NextEntryOffset
        "I"      # NumberOfThreads
        "48s"    # Reserved1
        "H"      # ImageName.Length
        "H"      # ImageName.MaximumLength
        "4x"     # padding before Buffer
        "Q"      # ImageName.Buffer
        "i"      # BasePriority
        "4x"     # padding before UniqueProcessId
        "Q"      # UniqueProcessId
        "Q"      # InheritedFromUniqueProcessId
        "I"      # HandleCount
        "I"      # SessionId
        "Q"      # Reserved3
        "Q"      # PeakVirtualSize
        "Q"      # VirtualSize
        "I"      # Reserved4
        "4x"     # padding before PeakWorkingSetSize
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
    fixed_size = struct.calcsize(fmt)

    processes = []
    offset = 0

    while True:
        if offset + fixed_size > len(blob):
            break

        fields = struct.unpack_from(fmt, blob, offset)

        next_entry_offset = fields[0]
        number_of_threads = fields[1]

        image_name_length = fields[3]
        image_name_max_length = fields[4]
        image_name_buffer = fields[5]

        base_priority = fields[6]
        pid = fields[7]
        parent_pid = fields[8]
        handle_count = fields[9]
        session_id = fields[10]

        peak_virtual_size = fields[12]
        virtual_size = fields[13]
        peak_working_set_size = fields[15]
        working_set_size = fields[16]
        quota_paged_pool_usage = fields[18]
        quota_non_paged_pool_usage = fields[20]
        pagefile_usage = fields[21]
        peak_pagefile_usage = fields[22]
        private_page_count = fields[23]

        # ImageName.Buffer is an absolute pointer in the returned structure,
        # not inline UTF-16 data and not a buffer-relative offset.
        # Without the original address space / dereference support, we cannot decode it here.
        if image_name_length == 0 or image_name_buffer == 0:
            name = "System"
        else:
            name = raw_buffer[image_name_buffer - scratchpad:image_name_buffer - scratchpad+image_name_length].decode('utf-16le')

        processes.append({
            "pid": pid,
            "parent_pid": parent_pid,
            "name": name,
            "threads": number_of_threads,
            "handles": handle_count,
            "session_id": session_id,
            "base_priority": base_priority,
            "peak_virtual_size": peak_virtual_size,
            "virtual_size": virtual_size,
            "peak_working_set_size": peak_working_set_size,
            "working_set_size": working_set_size,
            "quota_paged_pool_usage": quota_paged_pool_usage,
            "quota_non_paged_pool_usage": quota_non_paged_pool_usage,
            "pagefile_usage": pagefile_usage,
            "peak_pagefile_usage": peak_pagefile_usage,
            "private_page_count": private_page_count,
            "image_name_length": image_name_length,
            "image_name_max_length": image_name_max_length,
            "image_name_buffer": image_name_buffer,
            "entry_offset": offset,
            "next_entry_offset": next_entry_offset,
        })

        if next_entry_offset == 0:
            break

        if next_entry_offset < fixed_size:
            raise ValueError(f"Corrupt NextEntryOffset {next_entry_offset} at offset {offset}")

        offset += next_entry_offset

    return processes

def function(agent_id, args):
    import struct
    from models.agent import Agent
    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad

    SYSTEM_PROCESS_INFORMATION_CLASS = 5

    ret = NtQuerySystemInformation(agent_id, [SYSTEM_PROCESS_INFORMATION_CLASS])
    if not ret:
        return {"retval": -1, "message": "NtQuerySystemInformation returned no result"}

    if ret.get("retval") != 0:
        return {
            "retval": -1,
            "message": f"NtQuerySystemInformation failed {ret.get('retval')}"
        }

    raw_buffer = ret.get("raw_buffer")
    if raw_buffer is None:
        return {"retval": -1, "message": "NtQuerySystemInformation did not return raw_buffer"}

    processes = parse_system_process_information(scratchpad, raw_buffer)

    return {
        "retval": 0,
        "count": len(processes),
        "processes": processes,
    }