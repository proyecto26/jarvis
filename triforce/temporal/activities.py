"""Temporal Activities for Gemini LLM calls and dynamic tool dispatch.

Each Activity is a durable unit of work — if the worker crashes mid-activity,
Temporal will retry it on a new worker without re-executing completed activities.

Requires: temporalio, google-genai
Install with: pip install jarvis-triforce[temporal]
"""

from __future__ import annotations

import base64
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

    model: str = "gemini-3.5-flash"
    system_instruction: str = ""
    contents: list[dict[str, Any]] = field(default_factory=list)
    # Raw function declarations passed straight through to Gemini (dict form).
    tools: list[dict[str, Any]] = field(default_factory=list)
    # Tool NAMES resolved to registered handlers inside the activity — Python
    # callables cannot cross the Temporal boundary, so the durable ReAct loop
    # ships names and the worker rebuilds declarations from the registry.
    # Additive to ``tools``; both may be supplied.
    tool_names: list[str] = field(default_factory=list)


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


def _build_function_declaration(client: Any, name: str, handler: Any) -> Any:
    """Build a Gemini ``FunctionDeclaration`` for a registered handler.

    Prefers ``FunctionDeclaration.from_callable`` (google-genai 2.11), which
    derives the full parameter schema from the handler's signature. The
    declaration name is then forced to the *registered* ``name`` so it matches
    the key the durable ReAct loop dispatches on (handler ``__name__`` often
    differs, e.g. ``reset_accumulator`` vs ``reset_accumulator_activity``).

    Falls back to a minimal name + docstring declaration if introspection
    fails (e.g. a handler with untyped ``**kwargs``), so a single awkward
    handler never breaks the whole call.
    """
    from google.genai.types import FunctionDeclaration

    try:
        declaration = FunctionDeclaration.from_callable(client=client, callable=handler)
        declaration.name = name
        return declaration
    except Exception as exc:  # noqa: BLE001 — signature introspection can fail
        logger.warning(
            "from_callable failed for tool %r (%s) — using minimal declaration",
            name,
            exc,
        )
        return FunctionDeclaration(
            name=name,
            description=(getattr(handler, "__doc__", "") or "").strip(),
        )


# ---------------------------------------------------------------------------
# Temporal Activities (guarded import)
# ---------------------------------------------------------------------------

try:
    from collections.abc import Sequence

    from temporalio import activity
    from temporalio.common import RawValue

    @activity.defn
    async def generate_content(request: GeminiChatRequest) -> GeminiChatResponse:
        """Durable Temporal Activity wrapping a Gemini API call.

        - Disables automatic function calling (Temporal owns the tool loop)
        - Disables SDK retries (Temporal owns retry logic)
        - Preserves raw_parts including thought signatures for multi-turn
        """
        from google import genai
        from google.genai.types import (
            AutomaticFunctionCallingConfig,
            GenerateContentConfig,
            HttpOptions,
            Tool,
        )

        # Default client (stable endpoint). GOOGLE_API_KEY is read from the
        # environment. The previous ``api_version="v1alpha"`` override was
        # removed: an empirical A/B against gemini-3.5-flash showed the default
        # endpoint serves text, function calls, and thought signatures
        # correctly, matching the working GeminiProvider (triforce/llm/
        # providers/gemini.py). See PR notes for the ACT-OK evidence.
        client = genai.Client()

        # Assemble tool declarations from two additive sources:
        #   1. request.tools      — raw dict declarations, passed through as-is
        #   2. request.tool_names — names resolved to registered handlers HERE,
        #      because Python callables cannot cross the Temporal boundary.
        tools_list: list[Any] = list(request.tools) if request.tools else []
        if request.tool_names:
            function_declarations: list[Any] = []
            for name in request.tool_names:
                handler = get_handler(name)
                if handler is None:
                    logger.warning(
                        "tool_names: no handler registered for %r — skipping", name
                    )
                    continue
                function_declarations.append(
                    _build_function_declaration(client, name, handler)
                )
            if function_declarations:
                tools_list.append(Tool(function_declarations=function_declarations))

        config = GenerateContentConfig(
            system_instruction=request.system_instruction or None,
            tools=tools_list or None,
            # Temporal owns the tool loop and retries — disable the SDK's
            # automatic function calling. Correct field for google-genai 2.11.
            automatic_function_calling=AutomaticFunctionCallingConfig(disable=True),
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
                    # Preserve the thought signature for multi-turn continuity.
                    # It is raw bytes (not JSON-serializable) so we base64-encode
                    # it: the string survives Temporal's JSON payload boundary and
                    # Part validation decodes it back to the exact bytes when the
                    # workflow replays raw_parts as model content on the next turn.
                    sig = getattr(part, "thought_signature", None)
                    if sig:
                        part_dict["thought_signature"] = base64.b64encode(sig).decode(
                            "ascii"
                        )
                    raw_parts.append(part_dict)

        return GeminiChatResponse(
            text=text,
            function_calls=function_calls,
            raw_parts=raw_parts,
        )

    @activity.defn(dynamic=True)
    async def dynamic_tool_activity(args: Sequence[RawValue]) -> dict:
        """Dynamic Activity that dispatches to any registered Jarvis tool.

        Uses @activity.defn(dynamic=True) so any unregistered activity type
        name is routed here. Temporal's dynamic-activity contract requires a
        single ``Sequence[RawValue]`` parameter; the tool name is the invoked
        activity type (``activity.info().activity_type``), so workflows call
        tools by name string (e.g. ``workflow.execute_activity("run_consolidation")``).
        """
        activity_name = activity.info().activity_type
        handler = get_handler(activity_name)
        if handler is None:
            raise ValueError(f"No tool handler registered for: {activity_name}")

        converter = activity.payload_converter()
        values = converter.from_payloads([arg.payload for arg in args])

        # Parse arguments — handle both dict (kwargs) and positional args.
        # A raising handler is surfaced to the ReAct loop as a structured error
        # instead of crashing the activity: the model receives it as a tool
        # result and can react. ``Exception`` (not ``BaseException``) is caught
        # so cancellation/shutdown still propagate to Temporal.
        try:
            if values and len(values) == 1 and isinstance(values[0], dict):
                result = await handler(**values[0]) if _is_async(handler) else handler(**values[0])
            elif values:
                result = await handler(*values) if _is_async(handler) else handler(*values)
            else:
                result = await handler() if _is_async(handler) else handler()
        except Exception as exc:  # noqa: BLE001 — report tool failure to the loop
            logger.exception("Tool handler %r raised", activity_name)
            return {"error": f"{type(exc).__name__}: {exc}"}

        if not isinstance(result, dict):
            result = {"result": str(result)}
        return _ensure_json_serializable(result)

    def _is_async(func: Any) -> bool:
        """Check if a function is async."""
        import asyncio
        return asyncio.iscoroutinefunction(func)

    def _ensure_json_serializable(obj: dict) -> dict:
        """Guarantee a dict survives Temporal's JSON payload converter.

        Fast path: return it unchanged when it already round-trips. Otherwise
        coerce non-serializable values (bytes, datetimes, custom objects) via
        ``default=str`` so a tool result never fails serialization on return.
        """
        import json

        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return json.loads(json.dumps(obj, default=str))

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

    async def dynamic_tool_activity(args: list) -> dict:
        """Stub — temporalio not installed."""
        raise NotImplementedError(
            "dynamic_tool_activity requires temporalio. "
            "Install with: pip install jarvis-triforce[temporal]"
        )
