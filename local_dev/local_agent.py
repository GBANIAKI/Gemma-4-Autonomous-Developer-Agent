
import json
import time

from google.genai import errors

from google import genai
from google.genai import types

from .local_tools import (
    get_status,
    read_file,
    search_similar_code,
    get_code_neighbors,
    get_code_subgraph,
    get_repository_dependencies,
    get_repository_dependents,
    find_dependency_path,
    search_semantic_code,
    run_targeted_tests,
    verify_patch,
)

from .local_analyzer import run_analyzer, ExecutionBudgetExceeded
from .execution_budget import ExecutionBudget


def delegate_to_analyzer(task, budget=None):
    """Delegate a repository investigation using the shared execution budget."""
    return run_analyzer(task, budget=budget)


MODEL = "gemma-4-31b-it"

_client = None


def get_client():
    """Initialize the Google Gen AI client only when needed."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client

# Only these four read-only functions are available to the model.
FUNCTIONS = {
    "get_status": get_status,
    "read_file": read_file,
    "search_similar_code": search_similar_code,
    "get_code_neighbors": get_code_neighbors,
    "get_code_subgraph": get_code_subgraph,
    "get_repository_dependencies": get_repository_dependencies,
    "get_repository_dependents": get_repository_dependents,
    "find_dependency_path": find_dependency_path,
    "search_semantic_code": search_semantic_code,
    "delegate_to_analyzer": delegate_to_analyzer,
    "run_targeted_tests": run_targeted_tests,
    "verify_patch": verify_patch,
}

TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_status",
            description="Inspect the Git working-tree status of the project.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="read_file",
            description="Read a project file. The path must be inside the project.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": types.Schema(
                        type=types.Type.STRING,
                        description="Relative path of the file to read.",
                    )
                },
                required=["target"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_similar_code",
            description=(
                "Search project text files for literal, case-insensitive "
                "text matches. This is lexical search, not semantic search."
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
                "Identify direct Python import relationships for a project "
                "file. Returns files imported by the target and files that "
                "import the target. This is AST-based import analysis, not "
                "full semantic or call-graph analysis."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "target": types.Schema(
                        type=types.Type.STRING,
                        description="Relative path of an existing Python file.",
                    ),
                    "max_results": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum number of neighbors per direction.",
                    ),
                },
                required=["target"],
            ),
        ),

     types.FunctionDeclaration(
            name="get_code_subgraph",
            description=(
                "Build a directed Python import dependency subgraph "
                "starting from a project file. Returns discovered files "
                "as nodes and import relationships as edges. Supports "
                "configurable traversal depth and node limits. This is "
                "AST-based import analysis, not a complete semantic graph."
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
            description="List Python dependencies of a target file, optionally recursively.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "target": types.Schema(type=types.Type.STRING),
                "recursive": types.Schema(type=types.Type.BOOLEAN),
            }, required=["target"]),
        ),
        types.FunctionDeclaration(
            name="get_repository_dependents",
            description="List files that import a target file, optionally recursively.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "target": types.Schema(type=types.Type.STRING),
                "recursive": types.Schema(type=types.Type.BOOLEAN),
            }, required=["target"]),
        ),
        types.FunctionDeclaration(
            name="find_dependency_path",
            description="Find an import dependency path between two Python files.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "source": types.Schema(type=types.Type.STRING),
                "destination": types.Schema(type=types.Type.STRING),
            }, required=["source", "destination"]),
        ),
        types.FunctionDeclaration(
            name="search_semantic_code",
            description="Search the prebuilt semantic code embedding index.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={
                "query": types.Schema(type=types.Type.STRING),
                "max_results": types.Schema(type=types.Type.INTEGER),
                "path_filter": types.Schema(type=types.Type.STRING),
            }, required=["query"]),
        ),
     types.FunctionDeclaration(
            name="delegate_to_analyzer",
            description=(
                "Delegate a repository investigation to a separate "
                "read-only analyzer. The analyzer can read files, search "
                "project text, and inspect Python import relationships. "
                "It cannot edit files, execute shell commands, or submit patches. "
                "Returns a structured result containing status, report, "
                "errors, and completed tool evidence."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "task": types.Schema(
                        type=types.Type.STRING,
                        description="The investigation task for the analyzer.",
                    ),
                },
                required=["task"],
            ),
        ),
        types.FunctionDeclaration(
            name="verify_patch",
            description=(
                "Check whether a unified Git diff can be applied to the "
                "current repository state. This is a read-only check: "
                "it does not apply, stage, or commit the patch."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "patch_text": types.Schema(
                        type=types.Type.STRING,
                        description="The unified Git diff patch to verify.",
                    ),
                },
                required=["patch_text"],
            ),
        ),

        types.FunctionDeclaration(
            name="run_targeted_tests",
            description=(
                "Run explicitly selected pytest files inside the repository's "
                "tests directory. Returns structured test counts, execution "
                "status, duration, and bounded output. Does not modify files "
                "or execute arbitrary shell commands."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "test_paths": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description=(
                            "Explicit repository-relative paths to Python test "
                            "files inside tests/, such as tests/test_repository_graph.py."
                        ),
                    ),
                    "timeout_seconds": types.Schema(
                        type=types.Type.INTEGER,
                        description="Execution timeout, from 1 to 120 seconds. Defaults to 120.",
                    ),
                },
                required=["test_paths"],
            ),
        ),
    ]
)


def execute_tool(name, arguments, budget=None):
    """Execute a registered tool under the shared execution budget."""
    arguments = dict(arguments or {})

    verification_tools = {"run_targeted_tests", "verify_patch"}
    category = "verification" if name in verification_tools else "exploratory"

    function = FUNCTIONS.get(name)
    if function is None:
        return {
            "success": False,
            "error": f"Tool is not permitted: {name}",
        }

    requested_test_timeout = None

    # Validate the requested timeout before consuming a budget reservation.
    if name == "run_targeted_tests" and budget is not None:
        requested_test_timeout = arguments.get("timeout_seconds", 120)

        try:
            requested_test_timeout = float(requested_test_timeout)
        except (TypeError, ValueError):
            return {
                "success": False,
                "status": "error",
                "error": "timeout_seconds must be a number.",
            }

        if requested_test_timeout < 1:
            return {
                "success": False,
                "status": "error",
                "error": "timeout_seconds must be at least one second.",
            }
        # Check whether enough time remains before reserving the call.
        available_timeout = budget.timeout_for(
            min(120, requested_test_timeout)
        )

        if available_timeout < 1:
            return {
                "success": False,
                "status": "budget_exhausted",
                "error": (
                    "Less than one second remains for targeted test execution."
                ),
                "budget": budget.snapshot(),
            }

    if budget is not None and not budget.reserve(category):
        snapshot = budget.snapshot()

        globally_exhausted = (
            snapshot["remaining_seconds"] <= 0
            or snapshot["total_calls"] >= snapshot["max_total_calls"]
        )

        return {
            "success": False,
            "status": (
                "budget_exhausted"
                if globally_exhausted
                else "category_budget_exhausted"
            ),
            "error": (
                "The shared execution budget is exhausted."
                if globally_exhausted
                else f"The {category} call limit has been reached."
            ),
            "budget": snapshot,
        }

    try:
        if name == "delegate_to_analyzer":
            return function(**arguments, budget=budget)

        if name == "run_targeted_tests" and budget is not None:
            timeout = budget.timeout_for(
                min(120, requested_test_timeout)
            )

            if timeout < 1:
                return {
                    "success": False,
                    "status": "budget_exhausted",
                    "error": (
                        "Less than one second remains for targeted test execution."
                    ),
                    "budget": budget.snapshot(),
                }

            arguments["timeout_seconds"] = min(120, int(timeout))
            return function(**arguments)

        if name == "verify_patch" and budget is not None:
            timeout = budget.timeout_for(30)

            if timeout <= 0:
                return {
                    "success": False,
                    "status": "budget_exhausted",
                    "error": "No execution time remains for patch verification.",
                    "budget": budget.snapshot(),
                }

            arguments["timeout_seconds"] = timeout
            return function(**arguments)

        return function(**arguments)

    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }

def build_evidence_records(name, arguments, result, call_number):
    """
    Build traceable evidence records for a main-agent tool call.

    Delegated analyzer evidence receives a parent-qualified ID
    so evidence IDs remain unique across multiple delegations.
    """
    main_evidence_id = f"M{call_number:03d}"

    records = [
        {
            "evidence_id": main_evidence_id,
            "source": "main_agent",
            "tool": name,
            "arguments": arguments,
            "result": result,
        }
    ]

    if name == "delegate_to_analyzer" and isinstance(result, dict):
        analyzer_results = result.get("completed_tool_results", [])

        for index, item in enumerate(analyzer_results, start=1):
            analyzer_id = item.get(
                "evidence_id",
                f"A{index:03d}",
            )

            records.append({
                "evidence_id": f"{main_evidence_id}/{analyzer_id}",
                "source": "delegated_analyzer",
                "parent_evidence_id": main_evidence_id,
                "tool": item.get("tool"),
                "arguments": item.get("arguments", {}),
                "result": item.get("result"),
            })

    return records






def generate_with_retry(budget=None, **kwargs):
    """Retry temporary API errors while respecting the shared deadline."""
    delays = [5, 15, 30]

    for attempt in range(len(delays) + 1):

        if budget is not None and budget.remaining_seconds() <= 0:
            raise ExecutionBudgetExceeded(
                "The shared execution deadline expired before the API request."
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

            if (
                budget is not None
                and budget.remaining_seconds() <= delay
            ):
                raise ExecutionBudgetExceeded(
                    f"Insufficient execution time remains for the {delay}-second API retry delay."
                ) from exc

            print(
                f"[API RETRY] Attempt {attempt + 1}/3 failed "
                f"(HTTP {status_code}). Waiting {delay} seconds."
            )
            time.sleep(delay)


def run_agent(task, budget=None):
    budget = budget or ExecutionBudget()
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=(
                        "You are a repository investigation agent. "
                        "Use the available read-only tools to investigate "
                        "the user's request. Base conclusions on tool "
                         "evidence. Do not claim to have modified files.\n\n"

                         "EVIDENCE AND REPORTING RULES:\n"
                         "1. Use the evidence records returned with tool responses.\n"
                         "2. Cite evidence IDs for important factual claims, "
                         "using formats such as [M001] or [M002/A001].\n"
                         "3. Identify the tool and file path when relevant.\n"
                         "4. Do not invent evidence IDs or cite evidence that "
                         "was not returned.\n"
                         "5. Distinguish directly observed facts from inferences "
                         "and recommendations.\n"
                         "6. If a tool result reports success=false, treat that "
                         "operation as failed and do not use it as proof of success.\n"
                         "7. If a delegated analyzer result has status='incomplete', "
                         "clearly disclose that the investigation is incomplete. "
                         "Do not present its partial report as a completed investigation.\n"
                         "8. If evidence is missing, truncated, conflicting, or "
                         "insufficient, state the limitation and request additional "
                         "inspection rather than guessing.\n"
                         "9. Never claim that a file was edited, a command was run, "
                         "or a patch was submitted unless an authorized tool result "
                         "explicitly confirms that action.\n\n"

                         "FINAL ANSWER FORMAT:\n"
                         "- Findings: concise factual conclusions with evidence IDs.\n"
                         "- Evidence: list the most relevant evidence IDs, tools, "
                         "and inspected paths.\n"
                         "- Limitations: disclose missing, failed, truncated, or "
                         "incomplete evidence; write 'None identified' only when justified.\n"
                         "- Completion: state whether the requested investigation "
                         "is complete or incomplete and explain why.\n\n"

                        f"USER TASK:\n{task}"
                    )
                )
            ],
        )
    ]

    config = types.GenerateContentConfig(
        tools=[TOOL],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="AUTO"
            )
        ),
        temperature=0.2,
        max_output_tokens=4096,
    )

    tool_call_count = 0
    model_tool_call_attempt_count = 0
    max_tool_calls = budget.max_total_calls
    max_model_tool_call_attempts = (
        max_tool_calls + budget.max_total_calls
    )
    evidence_call_count = 0
    evidence_ledger = []
    stop_reason = "tool_call_limit"

    while (
        tool_call_count < max_tool_calls
        and model_tool_call_attempt_count < max_model_tool_call_attempts
    ):
        try:
            response = generate_with_retry(
                budget=budget,
                model=MODEL,
                contents=contents,
                config=config,
            )
        except (ExecutionBudgetExceeded,errors.ServerError,errors.ClientError) as exc:
            status_code = getattr(exc, "code", None)

            incomplete_delegations = [
                record["evidence_id"]
                for record in evidence_ledger
                if (
                    record.get("tool") == "delegate_to_analyzer"
                    and isinstance(record.get("result"), dict)
                    and record["result"].get("status") != "completed"
                )
            ]

            failed_tool_evidence = [
                record["evidence_id"]
                for record in evidence_ledger
                if (
                    isinstance(record.get("result"), dict)
                    and record["result"].get("success") is False
                )
            ]

            truncated_tool_evidence = [
                record["evidence_id"]
                for record in evidence_ledger
                if (
                    isinstance(record.get("result"), dict)
                    and record["result"].get("result_limit_reached") is True
                )
            ]

            retryable_statuses = (429, 500, 502, 503, 504)
            completion_reason = (
                "budget_exhausted"
                if isinstance(exc, ExecutionBudgetExceeded)
                else (
                    "api_retry_exhausted"
                    if status_code in retryable_statuses
                    else "api_request_failed"
                )
            )

            if isinstance(exc, ExecutionBudgetExceeded):
                answer = (
                    "Investigation incomplete: the shared execution deadline "
                    "prevented further API work. Previously collected evidence "
                    "has been preserved in evidence_records."
                )
            else:
                answer = (
                    "Investigation incomplete: the Google API request failed "
                    f"after retry handling. HTTP status: {status_code}. "
                    f"Error: {exc}. Previously collected evidence has been "
                    "preserved in evidence_records."
                )

            run_result = {
                "status": "incomplete",
                "completion_reason": completion_reason,
                "investigation_status": "incomplete",
                "tool_call_count": tool_call_count,
                "evidence_records": evidence_ledger,
                "incomplete_delegations": incomplete_delegations,
                "failed_tool_evidence": failed_tool_evidence,
                "truncated_tool_evidence": truncated_tool_evidence,
                "budget": budget.snapshot(),
                "api_error": {
                    "type": type(exc).__name__,
                    "status_code": status_code,
                    "message": str(exc),
                },
                "answer": answer,
            }

            print("\n===== RUN COMPLETION =====")
            print("STATUS: incomplete")
            print("REASON:", completion_reason)
            print("EVIDENCE RECORDS:", len(evidence_ledger))
            print("TOOL CALLS:", tool_call_count)

            return run_result

        candidate = response.candidates[0]
        model_content = candidate.content

        if model_content is not None:
            contents.append(model_content)

        function_calls = response.function_calls or []

        if not function_calls:
            final_answer = (
                response.text or "(No text response returned.)"
            )

            incomplete_delegations = [
                record
                for record in evidence_ledger
                if (
                    record.get("tool") == "delegate_to_analyzer"
                    and isinstance(record.get("result"), dict)
                    and record["result"].get("status") != "completed"
                )
            ]

            failed_tool_records = [
                record
                for record in evidence_ledger
                if (
                    isinstance(record.get("result"), dict)
                    and record["result"].get("success") is False
                )
            ]

            truncated_tool_records = [
                record
                for record in evidence_ledger
                if (
                    isinstance(record.get("result"), dict)
                    and record["result"].get("result_limit_reached") is True
                )
            ]

            deterministic_limitations = []

            if incomplete_delegations:
                ids = ", ".join(
                    record["evidence_id"]
                    for record in incomplete_delegations
                )
                deterministic_limitations.append(
                    f"Analyzer investigation incomplete (evidence: {ids})."
                )

            if failed_tool_records:
                ids = ", ".join(
                    record["evidence_id"]
                    for record in failed_tool_records
                )
                deterministic_limitations.append(
                    f"One or more tool operations failed (evidence: {ids})."
                )

            if truncated_tool_records:
                ids = ", ".join(
                    record["evidence_id"]
                    for record in truncated_tool_records
                )
                deterministic_limitations.append(
                    f"Tool results were truncated (evidence: {ids}); "
                    "the investigation is not exhaustive."
                )

            if not response.text:
                deterministic_limitations.append(
                    "The model did not return a final text response."
                )

            if deterministic_limitations:
                final_answer += (
                    "\n\nExecution limitations:\n- "
                    + "\n- ".join(deterministic_limitations)
                )

            run_result = {
                "status": (
                    "incomplete"
                    if (
                        incomplete_delegations
                        or failed_tool_records
                        or truncated_tool_records
                        or not response.text
                    )
                    else "completed"
                ),
                "completion_reason": (
                    "incomplete_delegation"
                    if incomplete_delegations
                    else (
                        "failed_tool_operation"
                        if failed_tool_records
                        else (
                            "truncated_tool_result"
                            if truncated_tool_records
                            else (
                                "final_response"
                                if response.text
                                else "empty_final_response"
                            )
                        )
                    )
                    
                ),
                "investigation_status": (
                    "incomplete"
                    if (
                          incomplete_delegations
                          or failed_tool_records
                          or truncated_tool_records
                       )
                     else "no_incomplete_operations_detected"
                ),
                "tool_call_count": tool_call_count,
                "evidence_records": evidence_ledger,
                "incomplete_delegations": [
                    record["evidence_id"]
                    for record in incomplete_delegations
                ],

                "failed_tool_evidence": [
                    record["evidence_id"]
                    for record in failed_tool_records
                ],
                "truncated_tool_evidence": [
                    record["evidence_id"]
                    for record in truncated_tool_records
                ],
                "budget": budget.snapshot(),
                "answer": final_answer,
            }

            print("\n===== AGENT ANSWER =====\n")
            print(final_answer)

            print("\n===== RUN COMPLETION =====")
            print("STATUS:", run_result["status"])
            print("REASON:", run_result["completion_reason"])
            print(
                "INVESTIGATION STATUS:",
                run_result["investigation_status"],
            )

            print("\n===== EVIDENCE RECORDS =====")
            print(len(evidence_ledger))

            print("\n===== TOOL CALLS =====")
            print(tool_call_count)

            return run_result
    

        tool_responses = []
        budget_blocked = False

        for call in function_calls:
            evidence_call_count += 1
            model_tool_call_attempt_count += 1

            name = call.name
            arguments = dict(call.args or {})

            print(f"\n[TOOL CALL] {name}")
            print("[ARGUMENTS]", arguments)

            if (
                model_tool_call_attempt_count
                > max_model_tool_call_attempts
            ):
                result = {
                    "success": False,
                    "status": "model_tool_call_attempt_limit",
                    "error": (
                        "The model exceeded the maximum number of "
                        "tool-call attempts."
                    ),
                    "budget": budget.snapshot(),
                }
            elif tool_call_count >= max_tool_calls:
                result = {
                    "success": False,
                    "status": "tool_call_limit",
                    "error": (
                        f"The main agent reached its maximum "
                        f"of {max_tool_calls} tool calls."
                    ),
                    "budget": budget.snapshot(),
                }
            else:
                before_total = budget.snapshot()["total_calls"]

                result = execute_tool(
                    name,
                    arguments,
                    budget=budget,
                )

                after_total = budget.snapshot()["total_calls"]

                dispatched = after_total > before_total

                if dispatched:
                    tool_call_count += 1

                if (
                    isinstance(result, dict)
                    and result.get("status") in {
                        "budget_exhausted",
                        "category_budget_exhausted",
                    }
                ):
                    snapshot = result.get("budget") or budget.snapshot()

                    globally_exhausted = (
                        result.get("status") == "budget_exhausted"
                        or snapshot.get("remaining_seconds", 0) <= 0
                        or snapshot.get("total_calls", 0)
                        >= snapshot.get("max_total_calls", 0)
                    )

                    if globally_exhausted:
                        budget_blocked = True
            new_evidence = build_evidence_records(
                name=name,
                arguments=arguments,
                result=result,
                call_number=evidence_call_count,
            )

            evidence_ledger.extend(new_evidence)

            print("[EVIDENCE IDS]", [
                item["evidence_id"] for item in new_evidence
            ])
            print(
                "[RESULT]",
                json.dumps(result, indent=2, default=str)[:4000],
            )

            tool_responses.append(
                types.Part.from_function_response(
                    name=name,
                    response={
                        "result": result,
                        "evidence_records": new_evidence,
                    },
                )
            )

        if tool_responses:
            contents.append(
                types.Content(
                    role="user",
                    parts=tool_responses,
                )
            )

        if budget_blocked:
            stop_reason = "budget_exhausted"
            break

        if model_tool_call_attempt_count >= max_model_tool_call_attempts:
            stop_reason = "model_tool_call_attempt_limit"
            break


    incomplete_delegations = [
        record
        for record in evidence_ledger
        if (
            record.get("tool") == "delegate_to_analyzer"
            and isinstance(record.get("result"), dict)
            and record["result"].get("status") != "completed"
        )
    ]

    failed_tool_records = [
        record
        for record in evidence_ledger
        if (
            isinstance(record.get("result"), dict)
            and record["result"].get("success") is False
        )
    ]

    truncated_tool_records = [
        record
        for record in evidence_ledger
        if (
            isinstance(record.get("result"), dict)
            and record["result"].get("result_limit_reached") is True
        )
    ]

    
    

    run_result = {
        "status": "incomplete",
        "completion_reason": stop_reason,
        "investigation_status": "incomplete",
        "tool_call_count": tool_call_count,
        "evidence_records": evidence_ledger,
        "incomplete_delegations": [
            record["evidence_id"]
            for record in incomplete_delegations
        ],
        "failed_tool_evidence": [
            record["evidence_id"]
            for record in failed_tool_records
        ],

        "truncated_tool_evidence": [
            record["evidence_id"]
            for record in truncated_tool_records
        ],
        "budget": budget.snapshot(),
        "answer": None,
    }

    print("\n===== RUN COMPLETION =====")
    print("STATUS: incomplete")
    print("REASON:", stop_reason)

    if stop_reason == "budget_exhausted":
        print("The agent stopped because the shared execution budget was exhausted.")
    else:
        print("The agent stopped after reaching the main-agent tool-call limit.")
    print("EVIDENCE RECORDS:", len(evidence_ledger))
    print("TOOL CALLS:", tool_call_count)

    return run_result



if __name__ == "__main__":
    task =(
    "Investigate the repository. First inspect its Git working-tree "
    "status. Then search for occurrences of 'get_code_subgraph' "
    "using the search tool. Report which files contain matches and "
    "whether the working tree has uncommitted changes."
)

    run_agent(task)
