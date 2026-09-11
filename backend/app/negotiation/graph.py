
from langgraph.graph import StateGraph, END
from app.negotiation.state import GraphNegotiationState
from app.negotiation.gov_agent import run_gov_agent
from app.negotiation.vendor_agent import run_vendor_agent

def create_negotiation_graph():
    workflow = StateGraph(GraphNegotiationState)
    
    workflow.add_node("gov_agent", run_gov_agent)
    workflow.add_node("vendor_agent", run_vendor_agent)
    
    workflow.set_entry_point("gov_agent")
    
    def decide_next(state: GraphNegotiationState):
        return state.get("next_actor", "END")
    
    workflow.add_conditional_edges(
        "gov_agent",
        decide_next,
        {
            "VENDOR_AGENT": "vendor_agent",
            "END": END
        }
    )
    
    workflow.add_conditional_edges(
        "vendor_agent",
        decide_next,
        {
            "GOV_AGENT": "gov_agent",
            "END": END
        }
    )
    
    return workflow.compile()

def run_bilateral_negotiation(initial_state: GraphNegotiationState) -> GraphNegotiationState:
    graph = create_negotiation_graph()
    
    # We only run it for a maximum of 6 steps to prevent infinite loops (3 rounds)
    final_state = graph.invoke(initial_state, {"recursion_limit": 15})
    return final_state
