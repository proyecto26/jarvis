"""State manipulation tools for inter-agent communication via ADK session state."""

from google.adk.tools import ToolContext


def append_to_state(key: str, value: str, tool_context: ToolContext) -> dict:
    """Append a value to a list key in session state, or set a scalar key.

    If the key already holds a list, the value is appended to it.
    Otherwise, the key is set (or overwritten) with the given value.

    Args:
        key: The state key to write to.
        value: The value to append or set.
    """
    current = tool_context.state.get(key)
    if isinstance(current, list):
        current.append(value)
        tool_context.state[key] = current
    else:
        tool_context.state[key] = value
    return {"status": "updated", "key": key}


def exit_loop(tool_context: ToolContext) -> dict:
    """Signal that the current dream loop should end.

    Call this when a genuine breakthrough has been detected.
    Store the breakthrough in state before calling this tool.
    """
    tool_context.actions.escalate = True
    return {"status": "loop_exit_signaled"}
