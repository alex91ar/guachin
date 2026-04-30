NAME = "readPipe"
DESCRIPTION = "Read bytes from a pipe"
PARAMS = [
    {"name":"pipe_handle", "description":"The file name", "type":"hex"},
    {"name":"read_size", "description":"Number of bytes to read", "type":"hex"},
]
DEPENDENCIES = ["NtOpenFile", "NtReadFile", "NtClose"]
DEFAULT = True

def function(agent_id, args):
    from services.orders import read_scratchpad
    from services.binary import align_up
    from models.agent import Agent
    agent = Agent.by_id(agent_id)

    pipe_handle = args[0]
    read_size = args[1]
    scratchpad = agent.scratchpad


    file_handle = pipe_handle
    print(f"About to call NtReadFile {[file_handle, scratchpad, read_size, "0x0"]}")
    ret = NtReadFile(agent_id, [file_handle, scratchpad, read_size, "0x0"])
    if ret["retval"] == 0:
        data = read_scratchpad(agent_id, read_size)
        decoded = data
        import hashlib
        return {
            "retval": 0,
            "data": decoded,
            "hash": hashlib.sha256(decoded).hexdigest(),
            "len": len(decoded)
        }
    else:

        return {"retval": -1, "message":f"Error in NtReadFile: {hex(ret['retval'])}"}