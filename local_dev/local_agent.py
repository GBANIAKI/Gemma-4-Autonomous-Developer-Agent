
import json
import time

from google.genai import errors

from google import genai
from google.genai import types

from local_tools import (
    get_status,
    read_file,
    search_similar_code,
)


MODEL = "gemma-4-31b-it"
MAX_TOOL_CALLS = 6

client = genai.Client()

# Only these three read-only functions are available to the model.
FUNCTIONS = {
    "get_status": get_status,
    "read_file": read_file,
    "search_similar_code": search_similar_code,
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
            print("\n===== AGENT ANSWER =====\n")
            print(response.text or "(No text response returned.)")
            print("\n===== TOOL CALLS =====")
            print(tool_call_count)
            return

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

            print("[RESULT]", json.dumps(result, indent=2)[:4000])

            tool_responses.append(
                types.Part.from_function_response(
                    name=name,
                    response={"result": result},
                )
            )

        if tool_responses:
            contents.append(
                types.Content(
                    role="tool",
                    parts=tool_responses,
                )
            )

    print("\nTool-call limit reached.")
    print("The agent stopped to prevent an unlimited tool loop.")


if __name__ == "__main__":
    task =(
    "Investigate the repository. First inspect its Git working-tree "
    "status. Then search for occurrences of 'get_code_subgraph' "
    "using the search tool. Report which files contain matches and "
    "whether the working tree has uncommitted changes."
)

    run_agent(task)
