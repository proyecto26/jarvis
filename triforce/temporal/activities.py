"""Temporal Activities for Gemini LLM calls and dynamic tool dispatch.

Each Activity is a durable unit of work — if the worker crashes mid-activity,
Temporal will retry it on a new worker without re-executing completed activities.

Requires: temporalio, google-genai
Install with: pip install jarvis-triforce[temporal]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes (always importable — no external dependencies)
# ---------------------------------------------------------------------------


@dataclass
class GeminiChatRequest:
    """Request payload for the generate_content activity.

    Matches Google's Gemini API pattern for multi-turn conversation.
    """

    model: str = "gemini-2.0-flash"
    system_instruction: str = ""
    contents: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GeminiChatResponse:
    """Response from the generate_content activity."""

    text: str = ""
    function_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_parts: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tool registry (always available)
# ---------------------------------------------------------------------------

_TOOL_HANDLERS: dict[str, Any] = {}


def register_tool(name: str, handler: Any) -> None:
    """Register a tool handler for dynamic dispatch."""
    _TOOL_HANDLERS[name] = handler


def get_handler(name: str) -> Any:
    """Look up a registered tool handler by name."""
    return _TOOL_HANDLERS.get(name)


# ---------------------------------------------------------------------------
# Temporal Activities (guarded import)
# ---------------------------------------------------------------------------

try:
    from temporalio import activity

    @activity.defn
    async def generate_content(request: GeminiChatRequest) -> GeminiChatResponse:
        """Durable Temporal Activity wrapping a Gemini API call.

        - Disables automatic function calling (Temporal owns the tool loop)
        - Disables SDK retries (Temporal owns retry logic)
        - Preserves raw_parts including thought signatures for multi-turn
        """
        from google import genai
        from google.genai.types import (
            GenerateContentConfig,
            HttpOptions,
        )

        client = genai.Client(
            http_options=HttpOptions(api_version="v1alpha"),
        )

        config = GenerateContentConfig(
            system_instruction=request.system_instruction or None,
            tools=request.tools or None,
            automatic_function_calling_config={"disable": True},
            http_options=HttpOptions(timeout=60_000),
        )

        response = client.models.generate_content(
            model=request.model,
            contents=request.contents,
            config=config,
        )

        # Extract structured response
        text = ""
        function_calls: list[dict[str, Any]] = []
        raw_parts: list[dict[str, Any]] = []

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    part_dict: dict[str, Any] = {}
                    if hasattr(part, "text") and part.text:
                        text += part.text
                        part_dict["text"] = part.text
                    if hasattr(part, "function_call") and part.function_call:
                        fc = {
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args) if part.function_call.args else {},
                        }
                        function_calls.append(fc)
                        part_dict["function_call"] = fc
                    if hasattr(part, "thought") and part.thought:
                        part_dict["thought"] = True
                    raw_parts.append(part_dict)

        return GeminiChatResponse(
            text=text,
            function_calls=function_calls,
            raw_parts=raw_parts,
        )

    @activity.defn(dynamic=True)
    async def dynamic_tool_activity(activity_name: str, args: list[Any]) -> dict:
        """Dynamic Activity that dispatches to any registered Jarvis tool.

        Uses @activity.defn(dynamic=True) so any unregistered activity type
        name is routed here. The activity_name is the tool name.
        """
        handler = get_handler(activity_name)
        if handler is None:
            raise ValueError(f"No tool handler registered for: {activity_name}")

        # Parse arguments — handle both dict and Pydantic model args
        if args and len(args) == 1 and isinstance(args[0], dict):
            result = await handler(**args[0]) if _is_async(handler) else handler(**args[0])
        elif args:
            result = await handler(*args) if _is_async(handler) else handler(*args)
        else:
            result = await handler() if _is_async(handler) else handler()

        if isinstance(result, dict):
            return result
        return {"result": str(result)}

    def _is_async(func: Any) -> bool:
        """Check if a function is async."""
        import asyncio
        return asyncio.iscoroutinefunction(func)

    logger.info("Temporal activities registered successfully")

except ImportError:
    logger.info(
        "temporalio not installed — Temporal activities unavailable. "
        "Install with: pip install jarvis-triforce[temporal]"
    )

    # Provide no-op stubs so imports don't break
    async def generate_content(request: GeminiChatRequest) -> GeminiChatResponse:
        """Stub — temporalio not installed."""
        raise NotImplementedError(
            "generate_content requires temporalio. "
            "Install with: pip install jarvis-triforce[temporal]"
        )

    async def dynamic_tool_activity(activity_name: str, args: list) -> dict:
        """Stub — temporalio not installed."""
        raise NotImplementedError(
            "dynamic_tool_activity requires temporalio. "
            "Install with: pip install jarvis-triforce[temporal]"
        )
