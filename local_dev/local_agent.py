
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
    run_targeted_tests,
    verify_patch,
)

from .local_analyzer import run_analyzer


def delegate_to_analyzer(task):
    """Delegate a repository investigation to the read-only analyzer."""
    return run_analyzer(task)


MODEL = "gemma-4-31b-it"
MAX_TOOL_CALLS = 6

client = genai.Client()

# Only these four read-only functions are available to the model.
FUNCTIONS = {
    "get_status": get_status,
    "read_file": read_file,
    "search_similar_code": search_similar_code,
    "get_code_neighbors": get_code_neighbors,
    "get_code_subgraph": get_code_subgraph,
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
                        description="Execution timeout, from 1 to 300 seconds. Defaults to 120.",
                    ),
                },
                required=["test_paths"],
            ),
        ),
    ]
)


def execute_tool(name, arguments):
    """Execute only registered, read-only tools."""
    function = FUNCTIONS.get(name)

    if function is None:
        return {
            "success": False,
            "error": f"Tool is not permitted: {name}",
        }

    try:
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



def generate_with_retry(**kwargs):
    """Retry temporary Google API availability and rate-limit errors."""
    delays = [5, 15, 30]

    for attempt, delay in enumerate(delays, start=1):
        try:
            return client.models.generate_content(**kwargs)

        except (errors.ServerError, errors.ClientError) as exc:
            status_code = getattr(exc, "code", None)

            if status_code not in (429, 500, 502, 503, 504):
                raise

            if attempt == len(delays):
                raise

            print(
                f"[API RETRY] Attempt {attempt} failed "
                f"(HTTP {status_code}). Waiting {delay} seconds."
            )
            time.sleep(delay)



def run_agent(task):
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
    evidence_ledger = []

    while tool_call_count < MAX_TOOL_CALLS:
        response = generate_with_retry(
                  model=MODEL,
                  contents=contents,
                 config=config,
               )

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

        for call in function_calls:
            if tool_call_count >= MAX_TOOL_CALLS:
                break

            name = call.name
            arguments = dict(call.args or {})

            print(f"\n[TOOL CALL] {name}")
            print("[ARGUMENTS]", arguments)

            result = execute_tool(name, arguments)
            tool_call_count += 1

            new_evidence = build_evidence_records(
                name=name,
                arguments=arguments,
                result=result,
                call_number=tool_call_count,
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
        "completion_reason": "tool_call_limit",
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
        "answer": None,
    }

    print("\n===== RUN COMPLETION =====")
    print("STATUS: incomplete")
    print("REASON: tool_call_limit")
    print("The agent stopped to prevent an unlimited tool loop.")
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
