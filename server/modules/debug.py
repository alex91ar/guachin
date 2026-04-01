NAME = "debug"
DESCRIPTION = "Enable or disable putting an int3 before execution."
PARAMS = [
        {"name":"enable", "description":"True or False", "type":"bool"}
]

def function(agent_id, args):
        from models.agent import Agent
        agent = Agent.by_id(agent_id)
        new_val = args[0]
        agent.debug = new_val
        agent.save()
        return {"agent_id":agent.id, "debug":str(new_val)}