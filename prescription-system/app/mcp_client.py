"""Client for the existing Clinical Guidelines MCP server."""

from __future__ import annotations

import os
import shutil
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
	"query_drug_interactions",
	"search_clinical_guidance",
	"search_prescription_guidance",
}


class ClinicalMCPError(RuntimeError):
	"""A connection, tool discovery, or remote tool error."""


class ClinicalMCPClient:
	def __init__(
		self,
		server_path: str | Path | None = None,
		python_executable: str | None = None,
		environment: dict[str, str] | None = None,
	) -> None:
		configured_path = server_path or os.getenv("CLINICAL_MCP_PATH")
		self.server_path = Path(configured_path) if configured_path else Path(__file__).resolve().parents[2] / "clinical-mcp"
		self.python_executable = python_executable or os.getenv("CLINICAL_MCP_PYTHON") or sys.executable
		self.environment = environment
		self._stack: AsyncExitStack | None = None
		self._session: ClientSession | None = None
		self._tools: list[str] = []

	async def connect(self) -> list[str]:
		if not self.server_path.is_dir():
			raise ClinicalMCPError(f"Clinical MCP server directory not found: {self.server_path}")
		if Path(self.python_executable).is_absolute() and not Path(self.python_executable).exists():
			raise ClinicalMCPError(f"Python executable not found: {self.python_executable}")
		if not Path(self.python_executable).is_absolute() and shutil.which(self.python_executable) is None:
			raise ClinicalMCPError(f"Python executable not found: {self.python_executable}")

		server_parameters = StdioServerParameters(
			command=self.python_executable,
			args=["server.py"],
			cwd=str(self.server_path),
			env=self.environment,
		)
		self._stack = AsyncExitStack()
		try:
			read_stream, write_stream = await self._stack.enter_async_context(stdio_client(server_parameters))
			self._session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
			await self._session.initialize()
			self._tools = await self.list_tools()
			missing_tools = sorted(EXPECTED_TOOLS.difference(self._tools))
			if missing_tools:
				raise ClinicalMCPError(f"Clinical MCP server is missing tools: {', '.join(missing_tools)}")
			return self._tools
		except Exception:
			await self.close()
			raise

	async def close(self) -> None:
		if self._stack is not None:
			await self._stack.aclose()
		self._stack = None
		self._session = None
		self._tools = []

	async def list_tools(self) -> list[str]:
		if self._session is None:
			raise ClinicalMCPError("Clinical MCP client is not connected")
		result = await self._session.list_tools()
		return [tool.name for tool in result.tools]

	async def _call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
		if self._session is None:
			raise ClinicalMCPError("Clinical MCP client is not connected")
		try:
			result = await self._session.call_tool(tool_name, arguments=arguments)
		except Exception as error:
			raise ClinicalMCPError(f"MCP tool execution failed for {tool_name}: {error}") from error
		if result.isError:
			raise ClinicalMCPError(f"MCP tool returned an error for {tool_name}")
		structured = getattr(result, "structuredContent", None)
		if isinstance(structured, dict):
			return structured
		for content in result.content:
			text = getattr(content, "text", None)
			if text:
				import json
				try:
					decoded = json.loads(text)
				except json.JSONDecodeError as error:
					raise ClinicalMCPError(f"MCP returned malformed JSON for {tool_name}") from error
				if isinstance(decoded, dict):
					return decoded
		raise ClinicalMCPError(f"MCP returned no structured response for {tool_name}")

	async def query_drug_interactions(self, medications: list[str]) -> dict[str, Any]:
		return await self._call("query_drug_interactions", {"meds_list": medications})

	async def search_clinical_guidance(self, anomaly_code: str) -> dict[str, Any]:
		return await self._call("search_clinical_guidance", {"anomaly_code": anomaly_code})

	async def search_prescription_guidance(
		self,
		medication: str,
		condition: str | None = None,
		dosage: str | None = None,
	) -> dict[str, Any]:
		return await self._call(
			"search_prescription_guidance",
			{"medication": medication, "condition": condition, "dosage": dosage},
		)
