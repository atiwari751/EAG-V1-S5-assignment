import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
import google.generativeai as genai
import json
import re
from rich.console import Console
from rich.panel import Panel
from concurrent.futures import TimeoutError
from functools import partial

console = Console()
# Load environment variables from .env file
load_dotenv()

# Access your API key and initialize Gemini client correctly
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
# instantiate exactly one model
model = genai.GenerativeModel("gemini-2.0-flash-lite")

# Global variables to track iterations and responses
last_response = None
iteration = 0
iteration_response = []

async def generate_with_timeout(model, prompt, timeout=10):
    """Generate content with a timeout using the new google.generativeai API."""
    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: model.generate_content(prompt)
            ),
            timeout=timeout
        )
        return response
    except TimeoutError:
        print("LLM generation timed out!")
        raise
    except Exception as e:
        print(f"Error in LLM generation: {e}")
        raise

def reset_state():
    """Reset all global variables to their initial state"""
    global last_response, iteration, iteration_response
    last_response = None
    iteration = 0
    iteration_response = []

async def main():
    reset_state()  # Reset at the start of main
    print("Starting main execution...")
    try:
        # Create a single MCP server connection
        print("Establishing connection to MCP server...")
        server_params = StdioServerParameters(
            command="python",
            args=["paint_mcp_tools.py"]
        )

        async with stdio_client(server_params) as (read, write):
            print("Connection established, creating session...")
            async with ClientSession(read, write) as session:
                print("Session created, initializing...")
                await session.initialize()
                
                # Get available tools
                print("Requesting tool list...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"Successfully retrieved {len(tools)} tools")

                # Create system prompt with available tools
                print("Creating system prompt...")
                tools_description = []
                for i, tool in enumerate(tools):
                    try:
                        params = tool.inputSchema
                        desc = getattr(tool, 'description', 'No description available')
                        name = getattr(tool, 'name', f'tool_{i}')
                        
                        # Format the input schema in a more readable way
                        if 'properties' in params:
                            param_details = []
                            for param_name, param_info in params['properties'].items():
                                param_type = param_info.get('type', 'unknown')
                                param_details.append(f"{param_name}: {param_type}")
                            params_str = ', '.join(param_details)
                        else:
                            params_str = 'no parameters'

                        tool_desc = f"{i+1}. {name}({params_str}) - {desc}"
                        tools_description.append(tool_desc)
                        print(f"Added description for tool: {tool_desc}")
                    except Exception as e:
                        print(f"Error processing tool {i}: {e}")
                        tools_description.append(f"{i+1}. Error processing tool")
                
                tools_description = "\n".join(tools_description)
                print("Successfully created tools description")
                
                # Updated system prompt with JSON formatted function calls
                system_prompt = f"""You are a creative and artistic agent that works step by step to create beautiful art. You can reason about your tasks and work in MS Paint using basic tools. You can verify your work and decide how you would like to proceed.

You have access to these tools:
{tools_description}

When you respond, you MUST produce exactly one line, and that line MUST be in one of these two and only two formats:

  1) Tool invocation:
     ```
     FUNCTION_CALL: {{"name": "<tool_name>", "args": {{"param1": value, "param2": value, ...}}}}
     ```
     – "name" must be one of the available tool names.
     – "args" is a JSON object containing the tool's parameters.
     – E.g.:
     ```
     FUNCTION_CALL: {{"name": "draw_rectangle", "args": {{"x1": 272, "y1": 310, "x2": 559, "y2": 657}}}}
     ```

  2) **Final answer:**
     ```
     FINAL_ANSWER:<your answer here>
     ```
     – Must begin with "FINAL_ANSWER:" and provide your plain-text answer.

🛑 It is ILLEGAL to ever write:
   FUNCTION_CALL:FINAL_ANSWER|…  
or any variant that treats FINAL_ANSWER as a tool.

🧠 Very Important Behavior Rules
- On the very first iteration, do NOT emit planning in plain text; to communicate your plan use exactly:
     FUNCTION_CALL: {{"name": "show_reasoning", "args": {{"steps": <JSON-encoded-list-of-steps>}}}}
- After completing a step, verify whether your action was successful using the verify_task tool. If it was, proceed to the next step. If not, repeat the same step.
- There should be no step called "Finalize the image" in the initial plan.
- Do NOT use the show_reasoning tool in two consecutive iterations.
- Only issue FINAL_ANSWER when you have completed all steps.

✅ Example:

  --- Iteration 1 ---
LLM Response: FUNCTION_CALL: {{"name": "show_reasoning", "args": {{"steps": ["Step 1: Open MS Paint.", "Step 2: Draw a rectangle with the specified corner points.", "Step 3: Add the specified text in the canvas.", "Step 4: Finalize the image."]}}}}
╭──────── Step 1 ────────╮
│ Step 1: Open MS Paint. │
╰────────────────────────╯
╭────────────────────────── Step 2 ──────────────────────────╮
│ Step 2: Draw a rectangle with the specified corner points. │
╰────────────────────────────────────────────────────────────╯
╭─────────────────── Step 3 ────────────────────╮
│ Step 3: Add the specified text in the canvas. │
╰───────────────────────────────────────────────╯
╭────────────── Step 4 ───────────────╮
│ Step 4: Verify the text and shapes. │
╰─────────────────────────────────────╯
--- Iteration 2 ---
LLM Response: FUNCTION_CALL: {{"name": "open_paint", "args": {{}}}}

--- Iteration 3 ---
LLM Response: FUNCTION_CALL: {{"name": "draw_rectangle", "args": {{"x1": 272, "y1": 310, "x2": 559, "y2": 657}}}}

--- Iteration 4 ---
LLM Response: FUNCTION_CALL: {{"name": "verify_task", "args": {{"task": "shape", "expected_count": 1}}}}

--- Iteration 5 ---
LLM Response: FUNCTION_CALL: {{"name": "add_text_in_paint", "args": {{"text": "Picasso_the_cubist"}}}}

--- Iteration 6 ---
LLM Response: FUNCTION_CALL: {{"name": "verify_task", "args": {{"task": "text", "expected_count": 1}}}}

--- Iteration 7 ---
LLM Response: FINAL_ANSWER: Done!

=== Agent Execution Complete ===

  """

                query = """Get creative with shapes! Open paint and draw a rectangle with corner points (272,310) and (559, 657). Then make a face in the rectangle using ovals and arrows. Finally, add text "baby_AGI" in the canvas."""
                print("Starting iteration loop...")
                
                # Use global iteration variables
                global iteration, last_response
                
                # Adaptive iteration loop; exit on FINAL_ANSWER
                while True:
                    print(f"\n--- Iteration {iteration + 1} ---")
                    if last_response is None:
                        current_query = query
                    else:
                        current_query = current_query + "\n\n" + " ".join(iteration_response)
                        current_query = current_query + "  What should I do next?"

                    # Get model's response with timeout
                    prompt = f"{system_prompt}\n\nQuery: {current_query}"
                    try:
                        response = await generate_with_timeout(model, prompt)
                        response_text = response.text.strip()
                        print(f"LLM Response: {response_text}")
                        
                        # Keep only the single relevant line
                        for line in response_text.split('\n'):
                            if line.startswith("FUNCTION_CALL:") or line.startswith("FINAL_ANSWER:"):
                                response_text = line
                                break
                    except Exception as e:
                        print(f"Failed to get LLM response: {e}")
                        break

                    if response_text.startswith("FUNCTION_CALL:"):
                        # New parsing: expect a JSON blob after "FUNCTION_CALL:"
                        json_str = response_text[len("FUNCTION_CALL:"):].strip()
                        # Remove any wrapping backticks (if the model output included markdown formatting)
                        json_str = json_str.strip("`")
                        try:
                            # First decode attempt
                            call_obj = json.loads(json_str)
                            # If the resulting object is a string, it means the JSON was double encoded.
                            if isinstance(call_obj, str):
                                call_obj = json.loads(call_obj)
                            func_name = call_obj["name"]
                            arguments = call_obj.get("args", {})
                        except Exception as e:
                            print(f"Error parsing JSON function call: {e}")
                            break
                        
                        try:
                            tool = next((t for t in tools if t.name == func_name), None)
                            if not tool:
                                print(f"DEBUG: Available tools: {[t.name for t in tools]}")
                                raise ValueError(f"Unknown tool: {func_name}")

                            # Use the parsed `arguments` instead of reinitializing it to {}
                            schema_properties = tool.inputSchema.get('properties', {})

                            # Convert each argument's type based on the tool's schema
                            for param_name, param_info in schema_properties.items():
                                if param_name in arguments:
                                    expected_type = param_info.get('type', 'string')
                                    value = arguments[param_name]
                                    if expected_type == 'integer':
                                        arguments[param_name] = int(value)
                                    elif expected_type == 'number':
                                        arguments[param_name] = float(value)
                                    elif expected_type == 'array':
                                        if isinstance(value, str):
                                            # Convert a comma-separated string into a list of integers
                                            arguments[param_name] = [int(x.strip()) for x in value.strip('[]').split(',')]
                                    else:
                                        arguments[param_name] = str(value)
                            
                            result = await session.call_tool(func_name, arguments=arguments)
                            
                            # For "show_reasoning", render the steps using rich panels
                            if func_name == "show_reasoning":
                                raw = arguments.get("steps", "")
                                try:
                                    steps_list = json.loads(raw)
                                except json.JSONDecodeError:
                                    steps_list = [
                                        s.strip()
                                        for s in re.split(r"[;,]", raw)
                                        if s.strip()
                                    ]
                                for idx, step in enumerate(steps_list, start=1):
                                    console.print(
                                        Panel(
                                            step,
                                            title=f"Step {idx}",
                                            border_style="cyan",
                                            expand=False,
                                        )
                                    )

                            # Process the result content
                            if hasattr(result, 'content'):
                                if isinstance(result.content, list):
                                    iteration_result = [
                                        item.text if hasattr(item, 'text') else str(item)
                                        for item in result.content
                                    ]
                                else:
                                    iteration_result = str(result.content)
                            else:
                                iteration_result = str(result)
                            
                            if isinstance(iteration_result, list):
                                result_str = f"[{', '.join(iteration_result)}]"
                            else:
                                result_str = str(iteration_result)
                            
                            iteration_response.append(
                                f"In iteration {iteration + 1}, you called {func_name} with arguments {arguments}, and the function returned {result_str}."
                            )
                            last_response = iteration_result

                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            iteration_response.append(f"Error in iteration {iteration + 1}: {str(e)}")
                            break

                    elif response_text.startswith("FINAL_ANSWER:"):
                        # Agent is done
                        final_answer = response_text.split("FINAL_ANSWER:", 1)[1].strip()
                        print("\n=== Agent Execution Complete ===")
                        break
                    else:
                        print("Unexpected model response—terminating loop.")
                        break

                    iteration += 1

    except Exception as e:
        print(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        reset_state()  # Reset at the end of main

if __name__ == "__main__":
    asyncio.run(main())
    
    
