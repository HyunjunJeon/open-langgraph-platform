"""
Agent Card Generator

Generates A2A Agent Cards from LangGraph graphs.
"""

import hashlib
import logging
import re
from typing import Any

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    AgentSkill,
)

logger = logging.getLogger(__name__)


class AgentCardGenerator:
    """
    Generates A2A Agent Cards from LangGraph graphs.

    Metadata sources (priority order):
    1. @a2a_metadata decorator
    2. Graph module docstring
    3. Graph tools
    4. Defaults
    """

    def __init__(self, base_url: str):
        """
        Initialize generator.

        Args:
            base_url: Base URL for the A2A endpoints (e.g., "http://localhost:8000")
        """
        self.base_url = base_url.rstrip("/")

    def generate_for_graph(self, graph_id: str, graph: Any) -> AgentCard:
        """
        Generate Agent Card for a graph.

        Args:
            graph_id: Unique identifier for the graph
            graph: Compiled LangGraph graph

        Returns:
            AgentCard instance
        """
        # Get decorator metadata
        decorator_meta = getattr(graph, "_a2a_metadata", {}) or {}

        # Get docstring metadata
        docstring_meta = self._parse_docstring(graph)

        # Build name
        name = decorator_meta.get("name") or docstring_meta.get("name") or self._generate_name(graph_id)

        # Build description
        description = (
            decorator_meta.get("description") or docstring_meta.get("description") or f"LangGraph agent: {graph_id}"
        )

        # Build skills
        skills_data = (
            decorator_meta.get("skills") or docstring_meta.get("skills") or self._extract_skills_from_tools(graph)
        )

        skills = self._build_skills(skills_data)

        return AgentCard(
            name=name,
            description=description,
            url=f"{self.base_url}/a2a/{graph_id}",
            version=self._generate_version(graph, graph_id),
            protocol_version="0.3.0",
            capabilities=AgentCapabilities(
                streaming=True,
                push_notifications=False,
                state_transition_history=True,
            ),
            skills=skills,
            default_input_modes=["text"],
            default_output_modes=["text"],
            provider=AgentProvider(
                organization="Open LangGraph Platform",
                url="https://github.com/your-org/open-langgraph-platform",
            ),
            icon_url=decorator_meta.get("icon_url"),
            documentation_url=decorator_meta.get("documentation_url"),
        )

    def _generate_name(self, graph_id: str) -> str:
        """Generate readable name from graph_id"""
        # snake_case or kebab-case -> Title Case
        return graph_id.replace("_", " ").replace("-", " ").title()

    def _generate_version(self, graph: Any, graph_id: str) -> str:
        """Generate version based on graph hash"""
        try:
            graph_repr = f"{graph_id}:{type(graph).__name__}"
            hash_val = hashlib.md5(graph_repr.encode()).hexdigest()[:8]
            return f"1.0.0-{hash_val}"
        except Exception:
            return "1.0.0"

    def _parse_docstring(self, graph: Any) -> dict[str, Any]:
        """Extract metadata from graph module docstring"""
        meta: dict[str, Any] = {}

        try:
            module_name = getattr(graph, "__module__", None)
            if not module_name:
                return meta

            import sys

            module = sys.modules.get(module_name)
            if not module or not module.__doc__:
                return meta

            docstring = module.__doc__.strip()
            lines = docstring.split("\n")

            if lines:
                meta["name"] = lines[0].strip()

            if len(lines) > 1:
                meta["description"] = "\n".join(lines[1:]).strip()

            # Parse "Skills: skill1, skill2" pattern
            skills_match = re.search(
                r"Skills?:\s*(.+?)(?:\n|$)",
                docstring,
                re.IGNORECASE,
            )
            if skills_match:
                skill_names = [s.strip() for s in skills_match.group(1).split(",")]
                meta["skills"] = [{"id": s.lower().replace(" ", "_"), "name": s} for s in skill_names if s]

        except Exception as e:
            logger.debug(f"Error parsing docstring: {e}")

        return meta

    def _extract_skills_from_tools(self, graph: Any) -> list[dict] | None:
        """Extract skills from graph tools"""
        try:
            tools = getattr(graph, "tools", None)
            if not tools:
                return None

            skills = []
            for tool in tools:
                tool_name = getattr(tool, "name", str(tool))
                tool_desc = getattr(tool, "description", "")

                skills.append({"id": tool_name, "name": tool_name, "description": tool_desc})

            return skills if skills else None

        except Exception as e:
            logger.debug(f"Error extracting tools: {e}")
            return None

    def _build_skills(
        self,
        skills_data: list[dict] | None,
    ) -> list[AgentSkill]:
        """Build AgentSkill objects from skill data"""
        if not skills_data:
            return [
                AgentSkill(
                    id="general",
                    name="General Assistant",
                    description="General purpose assistance",
                    tags=["general"],
                )
            ]

        skills = []
        for s in skills_data:
            skill_id = s.get("id", "unknown")
            skills.append(
                AgentSkill(
                    id=skill_id,
                    name=s.get("name", s.get("id", "Unknown")),
                    description=s.get("description", ""),
                    tags=s.get("tags", [skill_id]),
                )
            )

        return skills
