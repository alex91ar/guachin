NAME = "delete"
DESCRIPTION = "Delete a file"
PARAMS = [
    {"name":"file_name", "description":"The file name", "type":"str"},
]
DEPENDENCIES = ["NtOpenFile", "NtClose", "NtSetInformationFile"]
DEFAULT = True
def build_file_disposition_information(delete=True):
    """
    Create a FILE_DISPOSITION_INFORMATION struct as bytes.
    """
    return bytearray([1 if delete else 0])

def function(agent_id, args):
    from models.agent import Agent
    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    file_name = "\\??\\" + args[0]
    open_ret = NtOpenFile(agent_id, [file_name, 0x00110000, 0x7, 0x1000,0x0])
    if open_ret["retval"] != 0:
        return {"retval": -1, "message":"Error opening file."}
    file_handle = open_ret["FILE_HANDLE"]
    NtClose(agent_id, [file_handle])
    return {"retval":0}
    
