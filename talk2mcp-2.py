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

# max_iterations = 7    # commented out—no longer used (loop until FINAL_ANSWER)
last_response = None
iteration = 0
iteration_response = []

async def generate_with_timeout(model, prompt, timeout=10):
    """Generate content with a timeout using the new google.generativeai API."""
    # print("Starting LLM generation…")
    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                # direct call to model.generate_content
                lambda: model.generate_content(prompt)
            ),
            timeout=timeout
        )
        # print("LLM generation completed")
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
                print(f"Number of tools: {len(tools)}")
                
                try:
                    # First, let's inspect what a tool object looks like
                    # if tools:
                    #     print(f"First tool properties: {dir(tools[0])}")
                    #     print(f"First tool example: {tools[0]}")
                    
                    tools_description = []
                    for i, tool in enumerate(tools):
                        try:
                            # Get tool properties
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
                except Exception as e:
                    print(f"Error creating tools description: {e}")
                    tools_description = "Error loading tools"
                
                print("Created system prompt...")
                
                system_prompt = f"""You are a creative and artistic agent that works step by step to create beautiful art. You can reason about your tasks and work in MS Paint using basic tools. You can verify your work and decide how would you like to proceed.

You have access to these tools:{tools_description}

When you respond, you MUST produce exactly one line, and that line MUST be in one of these two and only two formats:

  1) Tool invocation:
     FUNCTION_CALL:<tool_name>|<arg1>|<arg2>|...  
     – where <tool_name> is one of the available tool names  
     – arguments follow separated by a single pipe character (“|”)  
     – e.g. FUNCTION_CALL:draw_rectangle|272|310|559|657

  2) Final answer:
     FINAL_ANSWER:<your answer here>  
     – Must begin with “FINAL_ANSWER:”  
     – Do NOT prefix this with “FUNCTION_CALL:”

🛑 IT IS ILLEGAL to ever write:
   FUNCTION_CALL:FINAL_ANSWER|…  
or any variant that treats FINAL_ANSWER as a tool.

🧠 Very Important Behavior Rules
- On the very first iteration, do NOT emit planning in plain text; to communicate your plan use exactly:
     FUNCTION_CALL:show_reasoning|<JSON-encoded-list-of-steps>
- Whenever you complete a step, verify whether your action was successful using the verify_task tool. If it was, proceed to the next step. If it was not, repeat the same step.
- There should be no step called "Finalize the image" in the initial plan.
- Do NOT call the show_reasoning tool in any two consecutive iterations under any circumstance, ever!!!!!!!!!!
- Only issue FINAL_ANSWER when you have completed all steps.

  
✅ Example:

  --- Iteration 1 ---
LLM Response: FUNCTION_CALL: show_reasoning|["Step 1: Open MS Paint.", "Step 2: Draw a rectangle with the specified corner points.", "Step 3: Add the specified text in the canvas.", "Step 4: Finalize the image."]
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
LLM Response: FUNCTION_CALL: open_paint

--- Iteration 3 ---
LLM Response: FUNCTION_CALL: draw_rectangle|272|310|559|657

--- Iteration 4 ---
LLM Response: FUNCTION_CALL:verify_task|shape|1

--- Iteration 5 ---
LLM Response: FUNCTION_CALL: add_text_in_paint|Picasso_the_cubist

--- Iteration 6 ---
LLM Response: FUNCTION_CALL:verify_task|text|1

--- Iteration 7 ---
LLM Response: FINAL_ANSWER: Done!

=== Agent Execution Complete ===

  """

                query = """Get creative with shapes! Open paint and draw a rectangle with corner points (272,310) and (559, 657). Then make a small oval in the rectangle, and multiple arrows pointing to the oval, all in the rectangle. Finally, add text "baby_AGI" in the canvas."""
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
                    # print("Preparing to generate LLM response...")
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
                        # Parse out name and args; allow LLM to include "()" after the name
                        _, function_info = response_text.split(":", 1)
                        parts = [p.strip() for p in function_info.split("|")]
                        raw_name, params = parts[0], parts[1:]
                        # Strip trailing parentheses if present
                        if raw_name.endswith("()"):
                            func_name = raw_name[:-2]
                        else:
                            func_name = raw_name
                        
                        # print(f"\nDEBUG: Raw function info: {function_info}")
                        # print(f"DEBUG: Split parts: {parts}")
                        # print(f"DEBUG: Function name: {func_name}")
                        # print(f"DEBUG: Raw parameters: {params}")
                        
                        try:
                            # Find the matching tool to get its input schema
                            tool = next((t for t in tools if t.name == func_name), None)
                            if not tool:
                                print(f"DEBUG: Available tools: {[t.name for t in tools]}")
                                raise ValueError(f"Unknown tool: {func_name}")

                            # print(f"DEBUG: Found tool: {tool.name}")
                            # print(f"DEBUG: Tool schema: {tool.inputSchema}")

                            # Prepare arguments according to the tool's input schema
                            arguments = {}
                            schema_properties = tool.inputSchema.get('properties', {})
                            # print(f"DEBUG: Schema properties: {schema_properties}")

                            for param_name, param_info in schema_properties.items():
                                if not params:  # Check if we have enough parameters
                                    raise ValueError(f"Not enough parameters provided for {func_name}")
                                    
                                value = params.pop(0)  # Get and remove the first parameter
                                param_type = param_info.get('type', 'string')
                                
                                # print(f"DEBUG: Converting parameter {param_name} with value {value} to type {param_type}")
                                
                                # Convert the value to the correct type based on the schema
                                if param_type == 'integer':
                                    arguments[param_name] = int(value)
                                elif param_type == 'number':
                                    arguments[param_name] = float(value)
                                elif param_type == 'array':
                                    # Handle array input
                                    if isinstance(value, str):
                                        value = value.strip('[]').split(',')
                                    arguments[param_name] = [int(x.strip()) for x in value]
                                else:
                                    arguments[param_name] = str(value)

                            # print(f"DEBUG: Final arguments: {arguments}")
                            # print(f"DEBUG: Calling tool {func_name}")
                            
                            result = await session.call_tool(func_name, arguments=arguments)
                            # print(f"DEBUG: Raw result: {result}")
                            
                            # show panels immediately
                            if func_name == "show_reasoning":
                                # re-parse the raw 'steps' argument we sent
                                raw = arguments.get("steps", "")
                                try:
                                    steps_list = json.loads(raw)
                                except json.JSONDecodeError:
                                    steps_list = [
                                        s.strip()
                                        for s in re.split(r"[;,]", raw)
                                        if s.strip()
                                    ]
                                # render each step in a rich Panel
                                for idx, step in enumerate(steps_list, start=1):
                                    console.print(
                                        Panel(
                                            step,
                                            title=f"Step {idx}",
                                            border_style="cyan",
                                            expand=False,
                                        )
                                    )

                            # Get the full result content
                            if hasattr(result, 'content'):
                                # print(f"DEBUG: Result has content attribute")
                                # Handle multiple content items
                                if isinstance(result.content, list):
                                    iteration_result = [
                                        item.text if hasattr(item, 'text') else str(item)
                                        for item in result.content
                                    ]
                                else:
                                    iteration_result = str(result.content)
                            else:
                                # print(f"DEBUG: Result has no content attribute")
                                iteration_result = str(result)
                                
                            # print(f"DEBUG: Final iteration result: {iteration_result}")
                            
                            # Format the response based on result type
                            if isinstance(iteration_result, list):
                                result_str = f"[{', '.join(iteration_result)}]"
                            else:
                                result_str = str(iteration_result)
                            
                            iteration_response.append(
                                f"In the {iteration + 1} iteration you called {func_name} with {arguments} parameters, "
                                f"and the function returned {result_str}."
                            )
                            last_response = iteration_result

                        except Exception as e:
                            # print(f"DEBUG: Error details: {str(e)}")
                            # print(f"DEBUG: Error type: {type(e)}")
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
    
    
