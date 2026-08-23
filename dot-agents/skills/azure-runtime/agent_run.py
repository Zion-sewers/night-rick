#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "azure-ai-projects>=1.0",
#   "azure-identity>=1.21",
# ]
# ///
"""
Run an Azure AI Foundry agent with full step observability.
Auth: DefaultAzureCredential — uses existing `az login`. No keys handled.

Usage:
  agent_run.py <project_endpoint> <agent_id> "<prompt>"

Example:
  agent_run.py "https://<foundry-account>.services.ai.azure.com/api/projects/<project-name>" \
               "<agent-id>" "is this comment toxic?"

Stdout: assistant message text (pipe-safe).
Stderr: thread/run/step lifecycle, tool calls.
Exit:   0 completed, 1 failed/cancelled/expired, 2 usage error.
"""
from __future__ import annotations

import sys

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    if len(sys.argv) < 4:
        err('usage: agent_run.py <project_endpoint> <agent_id> "<prompt>"')
        return 2
    endpoint, agent_id, prompt = sys.argv[1], sys.argv[2], sys.argv[3]

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    thread = project.agents.threads.create()
    err(f"[thread] {thread.id}")

    project.agents.messages.create(thread_id=thread.id, role="user", content=prompt)

    final_chunks: list[str] = []
    with project.agents.runs.stream(thread_id=thread.id, agent_id=agent_id) as stream:
        for event in stream:
            event_type = getattr(event, "event", None) or (
                event[0] if isinstance(event, tuple) else type(event).__name__
            )
            data = getattr(event, "data", None) or (
                event[1] if isinstance(event, tuple) and len(event) >= 2 else event
            )

            if event_type == "thread.run.created":
                err(f"[run] {getattr(data, 'id', '?')}")
            elif event_type == "thread.run.step.created":
                step_type = getattr(data, "type", "?")
                err(f"  [step] {step_type}")
            elif event_type == "thread.run.step.delta":
                delta = getattr(data, "delta", None)
                step_details = getattr(delta, "step_details", None) if delta else None
                tool_calls = (
                    getattr(step_details, "tool_calls", None) if step_details else None
                )
                for tc in tool_calls or []:
                    name = (
                        getattr(getattr(tc, "function", None), "name", None)
                        or getattr(tc, "type", "tool")
                    )
                    err(f"    [tool_call] {name}")
            elif event_type == "thread.message.delta":
                delta = getattr(data, "delta", None)
                content = getattr(delta, "content", None) if delta else None
                for block in content or []:
                    text_obj = getattr(block, "text", None)
                    chunk = getattr(text_obj, "value", "") if text_obj else ""
                    if chunk:
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                        final_chunks.append(chunk)
            elif event_type == "thread.run.completed":
                err("\n[run] completed")
            elif event_type == "thread.run.failed":
                err(f"\n[run] FAILED: {getattr(data, 'last_error', None)}")
                return 1
            elif event_type in ("thread.run.cancelled", "thread.run.expired"):
                err(f"\n[run] {event_type.split('.')[-1]}")
                return 1

    if final_chunks:
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
