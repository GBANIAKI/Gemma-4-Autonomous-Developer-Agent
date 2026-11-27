
import json
import time
from pathlib import Path
from .execution_budget import ExecutionBudget

from google import genai
from google.genai import errors, types

from .local_tools import (
    read_file,
    search_similar_code,
    get_code_neighbors,
    get_code_subgraph,
    get_repository_dependencies,
    get_repository_dependents,
    find_dependency_path,
    search_semantic_code,
)


# Local development model.
# The official competition configuration uses a different checkpoint
# and the tool_lora adapter.
MODEL = "gemma-4-31b-it"

MAX_TOOL_CALLS = 8

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "submission" / "prompts" / "analyzer.md"

_client = None


def get_client():
    """Initialize the Google GenAI client only when needed."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


class ExecutionBudgetExceeded(RuntimeError):
    """Raised when the shared execution deadline prevents more work."""

# ---------------------------------------------------------
# ANALYZER PERMISSIONS
# ---------------------------------------------------------

# This is the analyzer's independent tool whitelist.
# Do not add shell, write, edit, patch, or submission tools.

ANALYZER_FUNCTIONS = {
    "read_file": read_file,
    "search_similar_code": search_similar_code,
    "get_code_neighbors": get_code_neighbors,
    "get_code_subgraph": get_code_subgraph,
    "get_repository_dependencies": get_repository_dependencies,
    "get_repository_dependents": get_repository_dependents,
    "find_dependency_path": find_dependency_path,
    "search_semantic_code": search_semantic_code,
}


# ---------------------------------------------------------
# GEMMA FUNCTION DECLARATIONS
# ---------------------------------------------------------

ANALYZER_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="read_file",
            description=(
                "Read a project file inside the repository. "
                "Use this to inspect actual source code."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": types.Schema(
                        type=types.Type.STRING,
                        description="Relative path of the file to read.",
                    ),
                },
                required=["target"],
            ),
        ),

        types.FunctionDeclaration(
            name="search_similar_code",
            description=(
                "Search project text files for literal, "
                "case-insensitive text matches. This is lexical "
                "search, not semantic search."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Text to search for.",
                    ),
                    "max_results": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum number of results, from 1 to 20.",
                    ),
                },
                required=["query"],
            ),
        ),

        types.FunctionDeclaration(
            name="get_code_neighbors",
            description=(
                "Identify direct Python import relationships for a "
                "project file. Returns files imported by the target "
                "and files that import the target. This is AST-based "
                "import analysis, not full semantic analysis."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": types.Schema(
                        type=types.Type.STRING,
                        description="Relative path of a Python file.",
                    ),
                    "max_results": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum neighbors per direction.",
                    ),
                },
                required=["target"],
            ),
        ),

        types.FunctionDeclaration(
            name="get_code_subgraph",
            description=(
                "Build a directed Python import dependency subgraph "
                "starting from a project file. Returns discovered "
                "files as nodes and import relationships as edges. "
                "This is AST-based analysis, not a complete semantic graph."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": types.Schema(
                        type=types.Type.STRING,
                        description="Relative path of the starting Python file.",
                    ),
                    "max_depth": types.Schema(
                        type=types.Type.INTEGER,
                        description="Import traversal depth, from 0 to 5.",
                    ),
                    "max_nodes": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum graph nodes, from 1 to 100.",
                    ),
                },
                required=["target"],
            ),
        ),

        types.FunctionDeclaration(
            name="get_repository_dependencies",
            description="List Python files imported by a target file. Optionally traverse dependencies recursively.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": types.Schema(type=types.Type.STRING),
                    "recursive": types.Schema(type=types.Type.BOOLEAN),
                },
                required=["target"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_repository_dependents",
            description="List Python files that import a target file. Optionally traverse dependents recursively.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": types.Schema(type=types.Type.STRING),
                    "recursive": types.Schema(type=types.Type.BOOLEAN),
                },
                required=["target"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_dependency_path",
            description="Find an import dependency path between two Python files.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "source": types.Schema(type=types.Type.STRING),
                    "destination": types.Schema(type=types.Type.STRING),
                },
                required=["source", "destination"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_semantic_code",
            description="Search indexed repository code by semantic similarity. Requires an existing embedding index.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING),
                    "max_results": types.Schema(type=types.Type.INTEGER),
                    "path_filter": types.Schema(type=types.Type.STRING),
                },
                required=["query"],
            ),
        ),
    ]
)


# ---------------------------------------------------------
# RESTRICTED TOOL EXECUTION
# ---------------------------------------------------------

def execute_analyzer_tool(name, arguments):
    """
    Execute only tools explicitly permitted for the analyzer.
    Unknown or unauthorized tools are rejected.
    """

    function = ANALYZER_FUNCTIONS.get(name)

    if function is None:
        return {
            "success": False,
            "error": f"Analyzer tool is not permitted: {name}",
        }

    try:
        return function(**arguments)

    except Exception as exc:
        return {
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


# ---------------------------------------------------------
# API RETRY HANDLING
# ---------------------------------------------------------

def generate_with_retry(budget=None, **kwargs):
    """Retry temporary API errors while respecting the shared deadline."""

    delays = [5, 15, 30]

    for attempt in range(len(delays) + 1):

        if budget is not None and budget.remaining_seconds() <= 0:
            raise ExecutionBudgetExceeded(
                "The shared execution deadline expired before API generation."
            )

        try:
            return get_client().models.generate_content(**kwargs)

        except (errors.ServerError, errors.ClientError) as exc:
            status_code = getattr(exc, "code", None)

            if status_code not in (429, 500, 502, 503, 504):
                raise

            if attempt == len(delays):
                raise

            delay = delays[attempt]

            if budget is not None:
                remaining = budget.remaining_seconds()

                if remaining <= delay:
                    raise ExecutionBudgetExceeded(
                        "Insufficient remaining time for the next API retry."
                    )

            print(
                f"[ANALYZER API RETRY] Attempt {attempt + 1} failed "
                f"(HTTP {status_code}). Waiting {delay} seconds."
            )

            time.sleep(delay)
# ---------------------------------------------------------
# ANALYZER PROMPT
# ---------------------------------------------------------

def load_analyzer_prompt():
    """Load the competition's analyzer instructions."""

    if not PROMPT_PATH.is_file():
        raise FileNotFoundError(
            f"Analyzer prompt not found: {PROMPT_PATH}"
        )

    return PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------
# ANALYZER AGENT LOOP
# ---------------------------------------------------------


def run_analyzer(task, budget=None):
    """
    Run the specialized read-only code analyzer.

    Always return a consistent dictionary, whether the analysis
    completes successfully or stops before producing a final report.

    The analyzer cannot edit files, execute shell commands,
    or submit patches.
    """

    tool_call_count = 0
    completed_tool_results = []

    def make_result(
        status,
        report=None,
        error=None,
        message="",
    ):
        """Build the standard result consumed by the main agent."""
        return {
            "status": status,
            "report": report,
            "error": error,
            "message": message,
            "tool_call_count": tool_call_count,
            "completed_tool_results": completed_tool_results,
            "budget": budget.snapshot() if budget is not None else None,
        }

    system_prompt = load_analyzer_prompt()

    initial_message = (
        system_prompt
        + "\n\n"
        + "LOCAL EXECUTION CONSTRAINTS:\n"
        + "You are operating as a strictly read-only analyzer.\n"
        + "Use only the four declared analysis tools.\n"
        + "Do not modify, create, or delete files.\n"
        + "Do not execute commands.\n"
        + "Do not submit patches.\n"
        + "Base conclusions on inspected repository evidence.\n"
        + "Clearly distinguish evidence from hypotheses.\n"
        + "Return the structured report required by your instructions.\n\n"
        + "INVESTIGATION REQUEST:\n"
        + task
    )

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=initial_message)
            ],
        )
    ]

    config = types.GenerateContentConfig(
        tools=[ANALYZER_TOOL],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="AUTO"
            )
        ),
        temperature=0.2,
        max_output_tokens=4096,
    )

    while tool_call_count < MAX_TOOL_CALLS:

        try:
            response = generate_with_retry(
                budget=budget,
                model=MODEL,
                contents=contents,
                config=config,
            )

        except ExecutionBudgetExceeded as exc:
            return make_result(
                status="incomplete",
                error={
                    "type": "budget_exhausted",
                    "message": str(exc),
                },
                message=(
                    "The shared execution deadline prevented the "
                    "analyzer from continuing. Completed evidence "
                    "has been preserved."
                ),
            )

        except (errors.ServerError, errors.ClientError) as exc:
            status_code = getattr(exc, "code", None)

            print("\n===== ANALYZER API UNAVAILABLE =====")
            print(f"HTTP STATUS: {status_code}")
            print("Previously completed tool results are preserved.")

            return make_result(
                status="incomplete",
                error={
                    "type": "api_error",
                    "status_code": status_code,
                    "exception": type(exc).__name__,
                    "message": str(exc),
                },
                message=(
                    "Gemma could not continue the investigation. "
                    "No final model-generated report is available."
                ),
            )

        if not response.candidates:
            print("\n[ANALYZER ERROR] No response candidate returned.")

            return make_result(
                status="incomplete",
                error={
                    "type": "empty_response",
                    "message": "The model returned no response candidates.",
                },
                message="The analyzer received no usable model response.",
            )

        candidate = response.candidates[0]
        model_content = candidate.content

        if model_content is not None:
            contents.append(model_content)

        function_calls = response.function_calls or []

        if not function_calls:
            report = (response.text or "").strip()

            if not report:
                print("\n[ANALYZER ERROR] Empty final report.")

                return make_result(
                    status="incomplete",
                    error={
                        "type": "empty_report",
                        "message": "The model returned no final report text.",
                    },
                    message="The analyzer did not produce a usable report.",
                )

            print("\n===== ANALYZER REPORT =====\n")
            print(report)

            print("\n===== ANALYZER TOOL CALLS =====")
            print(tool_call_count)

            return make_result(
                status="completed",
                report=report,
                message="The analyzer completed its investigation.",
            )

        tool_responses = []
        budget_blocked = False
        local_limit_reached = False

        for call in function_calls:

            name = call.name
            arguments = dict(call.args or {})
            dispatched = False

            print(f"\n[ANALYZER TOOL CALL] {name}")
            print("[ARGUMENTS]", arguments)

            if tool_call_count >= MAX_TOOL_CALLS:
                local_limit_reached = True

                result = {
                    "success": False,
                    "status": "tool_call_limit",
                    "error": (
                        f"The analyzer reached its maximum of "
                        f"{MAX_TOOL_CALLS} tool calls."
                    ),
                }

            elif budget is not None and not budget.reserve("exploratory"):
                budget_blocked = True

                result = {
                    "success": False,
                    "status": "budget_exhausted",
                    "error": (
                        "The shared execution budget does not permit "
                        "another analyzer tool call."
                    ),
                    "budget": budget.snapshot(),
                }

            else:
                dispatched = True
                result = execute_analyzer_tool(name, arguments)
                tool_call_count += 1

            evidence_id = f"A{len(completed_tool_results) + 1:03d}"

            completed_tool_results.append({
                "evidence_id": evidence_id,
                "tool": name,
                "arguments": arguments,
                "result": result,
                "dispatched": dispatched,
            })

            print(
                "[RESULT]",
                json.dumps(result, indent=2, default=str)[:4000],
            )

            tool_responses.append(
                types.Part.from_function_response(
                    name=name,
                    response={"result": result},
                )
            )

        if tool_responses:
            contents.append(
                types.Content(
                    role="user",
                    parts=tool_responses,
                )
            )

        if budget_blocked or local_limit_reached:
            if budget_blocked:
                error_type = "budget_exhausted"
                error_message = (
                    "The shared execution budget prevented the analyzer "
                    "from continuing. Completed evidence has been preserved."
                )
            else:
                error_type = "tool_call_limit"
                error_message = (
                    f"The analyzer reached its maximum of "
                    f"{MAX_TOOL_CALLS} tool calls. Completed evidence "
                    "has been preserved."
                )

            return make_result(
                status="incomplete",
                error={
                    "type": error_type,
                    "message": error_message,
                },
                message=error_message,
            )


    print("\n[ANALYZER] Tool-call limit reached.")
    print("The analyzer stopped to prevent an unlimited tool loop.")

    return make_result(
        status="incomplete",
        error={
            "type": "tool_call_limit",
            "message": (
                f"The analyzer reached its maximum of "
                f"{MAX_TOOL_CALLS} tool calls."
            ),
        },
        message=(
            "The investigation stopped at the tool-call limit "
            "without producing a final report."
        ),
    )

# ---------------------------------------------------------
# LOCAL ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":

    investigation = (
        "Investigate the local_dev/local_agent.py module. "
        "Identify its imported modules, inspect the related source "
        "code, and explain the relationship between the main agent "
        "and its local tools. Identify any relevant architectural "
        "limitations. Base your findings on repository evidence."
    )

    run_analyzer(investigation)
