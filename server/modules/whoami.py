NAME = "whoami"
DESCRIPTION = "Get the current agent and user."
PARAMS = [
]

def function(agent_id, args):
        from models.agent import Agent
        agent = Agent.by_id(agent_id)
        return {"agent_id":agent.id, "user":agent.user_id}