
from google import genai
from google.genai import types

client = genai.Client()

inspect_project = types.FunctionDeclaration(
    name="inspect_project",
    description="Inspect a project file by its filename.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "The filename to inspect."
            }
        },
        "required": ["target"]
    }
)

tool = types.Tool(
    function_declarations=[inspect_project]
)

response = client.models.generate_content(
    model="gemma-4-31b-it",
    contents=(
        "You must call inspect_project with target set to "
        "'README.md'. Do not answer without calling the tool."
    ),
    config=types.GenerateContentConfig(
        tools=[tool],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY"
            )
        ),
        temperature=0,
        max_output_tokens=256
    )
)

if response.function_calls:
    for call in response.function_calls:
        print("FUNCTION CALL:", call.name)
        print("ARGUMENTS:", call.args)
else:
    print("NO FUNCTION CALL")
    print(response.text)
