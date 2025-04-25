# basic import 
from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.prompts import base
from mcp.types import TextContent
from PIL import Image as PILImage
import sys
from pywinauto.application import Application
import win32gui
import win32con
import time
from win32api import GetSystemMetrics
from pywinauto.keyboard import send_keys
import os


import json
import tempfile
from rich.console import Console
from rich.panel import Panel
import re

console = Console()
# instantiate an MCP server client
mcp = FastMCP("MSPainter")

# DEFINE TOOLS


@mcp.tool()
async def draw_rectangle(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Draw a rectangle in Paint from (x1,y1) to (x2,y2)"""
    global paint_app
    try:
        if not paint_app:
            return {
                "content": [
                    TextContent(
                        type="text",
                        text="Paint is not open. Please call open_paint first."
                    )
                ]
            }
        
        paint_window = paint_app.window(class_name='MSPaintApp')
        if not paint_window.has_focus():
            paint_window.set_focus(); time.sleep(0.2)
        
        # Select the Rectangle tool
        paint_window.click_input(coords=(440, 63))
        time.sleep(0.2)
        
        canvas = paint_window.child_window(class_name='MSPaintView')
        canvas.press_mouse_input(coords=(x1, y1))
        canvas.move_mouse_input(coords=(x2, y2))
        canvas.release_mouse_input(coords=(x2, y2))
        
        # Deselect
        time.sleep(0.1)
        canvas.click_input(coords=(x2 + 5, y2 + 5))
        time.sleep(0.2)    # ← added sleep after deselect
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Rectangle drawn from ({x1},{y1}) to ({x2},{y2})"
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error drawing rectangle: {str(e)}"
                )
            ]
        }

@mcp.tool()
async def add_text_in_paint(text: str) -> dict:
    """Add text in Paint"""
    global paint_app
    try:
        if not paint_app:
            return {
                "content": [
                    TextContent(
                        type="text",
                        text="Paint is not open. Please call open_paint first."
                    )
                ]
            }
        
        # Get the Paint window
        paint_window = paint_app.window(class_name='MSPaintApp')
        
        # Ensure Paint window is active
        if not paint_window.has_focus():
            paint_window.set_focus()
            time.sleep(0.2)
        
        # 1) Open the Home tab (ALT+H), then select Text (T)
        send_keys('%H')    # ALT+H
        time.sleep(0.2)
        send_keys('T')     # Text tool
        time.sleep(0.5)

        # 2) Click on canvas to begin your text box
        canvas = paint_window.child_window(class_name='MSPaintView')
        canvas.click_input(coords=(350, 533))
        time.sleep(0.5)

        # 3) Type the actual text
        send_keys(text)
        time.sleep(0.5)

        # 4) Click outside to finish
        canvas.click_input(coords=(600, 800))
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Text:'{text}' added successfully"
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )
            ]
        }

@mcp.tool()
async def open_paint() -> dict:
    """Open Microsoft Paint maximized on secondary monitor"""
    global paint_app
    try:
        paint_app = Application().start('mspaint.exe')
        time.sleep(0.2)
        
        # Get the Paint window
        paint_window = paint_app.window(class_name='MSPaintApp')
        
        # Get primary monitor width
        primary_width = GetSystemMetrics(0)
        
        # First move to secondary monitor without specifying size
        win32gui.SetWindowPos(
            paint_window.handle,
            win32con.HWND_TOP,
            primary_width - 1920, 0,  # Position it on secondary monitor
            0, 0,  # Let Windows handle the size
            win32con.SWP_NOSIZE  # Don't change the size
        )
        
        # Now maximize the window
        win32gui.ShowWindow(paint_window.handle, win32con.SW_MAXIMIZE)
        time.sleep(0.2)
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text="Paint opened successfully on secondary monitor and maximized"
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error opening Paint: {str(e)}"
                )
            ]
        }

@mcp.tool()
def show_reasoning(steps) -> TextContent:
    """
    Show the step-by-step reasoning process.
    Accepts either:
      - A Python list of strings, or
      - A JSON string encoding an array of strings.
    """
    # 1) Normalize input into a List[str]
    if isinstance(steps, str):
        try:
            steps_list = json.loads(steps)
        except json.JSONDecodeError:
            steps_list = [
                s.strip() for s in re.split(r"[;,]", steps)
                if s.strip()
            ]
    else:
        steps_list = steps  # assume already List[str]

    # 2) Render them to a temporary console
    record_console = Console(record=True, width=80)
    for idx, step in enumerate(steps_list, start=1):
        record_console.print(Panel(
            step,
            title=f"Step {idx}",
            border_style="cyan"
        ))

    # 3) Export the rendered panel as text (with borders & padding)
    rendered = record_console.export_text()

    # 4) Return that back to the client
    return TextContent(
        type="text",
        text=rendered
    )

@mcp.tool()
async def draw_oval(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Draw an oval in Paint from (x1,y1) to (x2,y2)"""
    global paint_app
    try:
        if not paint_app:
            return {"content":[TextContent(type="text",text="Paint is not open. Please call open_paint first.")]}
        paint_window = paint_app.window(class_name="MSPaintApp")
        if not paint_window.has_focus():
            paint_window.set_focus(); time.sleep(0.2)
        # Select Oval tool
        paint_window.click_input(coords=(421, 63)); time.sleep(0.2)
        canvas = paint_window.child_window(class_name="MSPaintView")
        canvas.press_mouse_input(coords=(x1, y1))
        canvas.move_mouse_input(coords=(x2, y2))
        canvas.release_mouse_input(coords=(x2, y2))
        # Deselect
        time.sleep(0.1)
        canvas.click_input(coords=(x2 + 5, y2 + 5))
        time.sleep(0.2)  
        return {"content":[TextContent(type="text",text=f"Oval drawn from ({x1},{y1}) to ({x2},{y2})")]}
    except Exception as e:
        return {"content":[TextContent(type="text",text=f"Error drawing oval: {e}")]}

@mcp.tool()
async def draw_right_arrow(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Draw a right arrow in Paint from (x1,y1) to (x2,y2)"""
    global paint_app
    try:
        if not paint_app:
            return {"content":[TextContent(type="text",text="Paint is not open. Please call open_paint first.")]}
        paint_window = paint_app.window(class_name="MSPaintApp")
        if not paint_window.has_focus():
            paint_window.set_focus(); time.sleep(0.2)
        # Select Right Arrow tool
        paint_window.click_input(coords=(460, 82)); time.sleep(0.2)
        canvas = paint_window.child_window(class_name="MSPaintView")
        canvas.press_mouse_input(coords=(x1, y1))
        canvas.move_mouse_input(coords=(x2, y2))
        canvas.release_mouse_input(coords=(x2, y2))
        time.sleep(0.1)
        canvas.click_input(coords=(x2 + 5, y2 + 5))
        time.sleep(0.2)  
        return {"content":[TextContent(type="text",text=f"Right arrow drawn from ({x1},{y1}) to ({x2},{y2})")]}
    except Exception as e:
        return {"content":[TextContent(type="text",text=f"Error drawing right arrow: {e}")]}

@mcp.tool()
async def draw_left_arrow(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Draw a left arrow in Paint from (x1,y1) to (x2,y2)"""
    global paint_app
    try:
        if not paint_app:
            return {"content":[TextContent(type="text",text="Paint is not open. Please call open_paint first.")]}
        paint_window = paint_app.window(class_name="MSPaintApp")
        if not paint_window.has_focus():
            paint_window.set_focus(); time.sleep(0.2)
        # Select Left Arrow tool
        paint_window.click_input(coords=(482, 82)); time.sleep(0.2)
        canvas = paint_window.child_window(class_name="MSPaintView")
        canvas.press_mouse_input(coords=(x1, y1))
        canvas.move_mouse_input(coords=(x2, y2))
        canvas.release_mouse_input(coords=(x2, y2))
        time.sleep(0.1)
        canvas.click_input(coords=(x2 + 5, y2 + 5))
        time.sleep(0.2)  
        return {"content":[TextContent(type="text",text=f"Left arrow drawn from ({x1},{y1}) to ({x2},{y2})")]}
    except Exception as e:
        return {"content":[TextContent(type="text",text=f"Error drawing left arrow: {e}")]}

@mcp.tool()
async def draw_up_arrow(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Draw an up arrow in Paint from (x1,y1) to (x2,y2)"""
    global paint_app
    try:
        if not paint_app:
            return {"content":[TextContent(type="text",text="Paint is not open. Please call open_paint first.")]}
        paint_window = paint_app.window(class_name="MSPaintApp")
        if not paint_window.has_focus():
            paint_window.set_focus(); time.sleep(0.2)
        # Select Up Arrow tool
        paint_window.click_input(coords=(800, 82)); time.sleep(0.2)
        canvas = paint_window.child_window(class_name="MSPaintView")
        canvas.press_mouse_input(coords=(x1, y1))
        canvas.move_mouse_input(coords=(x2, y2))
        canvas.release_mouse_input(coords=(x2, y2))
        time.sleep(0.1)
        canvas.click_input(coords=(x2 + 5, y2 + 5))
        time.sleep(0.2)  
        return {"content":[TextContent(type="text",text=f"Up arrow drawn from ({x1},{y1}) to ({x2},{y2})")]}
    except Exception as e:
        return {"content":[TextContent(type="text",text=f"Error drawing up arrow: {e}")]}

@mcp.tool()
async def draw_down_arrow(x1: int, y1: int, x2: int, y2: int) -> dict:
    """Draw a down arrow in Paint from (x1,y1) to (x2,y2)"""
    global paint_app
    try:
        if not paint_app:
            return {"content":[TextContent(type="text",text="Paint is not open. Please call open_paint first.")]}
        paint_window = paint_app.window(class_name="MSPaintApp")
        if not paint_window.has_focus():
            paint_window.set_focus(); time.sleep(0.2)
        # Select Down Arrow tool
        paint_window.click_input(coords=(379, 105)); time.sleep(0.2)
        canvas = paint_window.child_window(class_name="MSPaintView")
        canvas.press_mouse_input(coords=(x1, y1))
        canvas.move_mouse_input(coords=(x2, y2))
        canvas.release_mouse_input(coords=(x2, y2))
        time.sleep(0.1)
        canvas.click_input(coords=(x2 + 5, y2 + 5))
        time.sleep(0.2)  
        return {"content":[TextContent(type="text",text=f"Down arrow drawn from ({x1},{y1}) to ({x2},{y2})")]}
    except Exception as e:
        return {"content":[TextContent(type="text",text=f"Error drawing down arrow: {e}")]}

# DEFINE RESOURCES

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    print("CALLED: get_greeting(name: str) -> str:")
    return f"Hello, {name}!"


# DEFINE AVAILABLE PROMPTS
@mcp.prompt()
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"
    print("CALLED: review_code(code: str) -> str:")


@mcp.prompt()
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]

if __name__ == "__main__":
    # Check if running with mcp dev command
    print("STARTING")
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()  # Run without transport for dev server
    else:
        mcp.run(transport="stdio")  # Run with stdio for direct execution
