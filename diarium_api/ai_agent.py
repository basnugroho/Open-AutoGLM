"""
AI Agent Module
===============

Wrapper for running the AutoGLM phone agent.
"""

import os
import asyncio
from typing import Tuple

from .config import Config


async def run_phone_agent(task: str) -> Tuple[bool, str]:
    """
    Run the AutoGLM phone agent with given task.
    
    This executes main.py as a subprocess with the ZAI API configuration.
    The agent uses vision AI to analyze screenshots and perform actions.
    
    Args:
        task: Natural language description of what to do
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    cmd = [
        Config.PYTHON_PATH,
        Config.MAIN_SCRIPT,
        "--base-url", Config.ZAI_BASE_URL,
        "--model", Config.ZAI_MODEL,
        "--apikey", Config.ZAI_API_KEY,
        "--lang", "en",
        task
    ]
    
    env = os.environ.copy()
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env
        )
        
        stdout, stderr = await process.communicate()
        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""
        
        if process.returncode == 0:
            if "Task Completed:" in output:
                result_start = output.find("Task Completed:") + len("Task Completed:")
                result_end = output.find("==", result_start)
                message = output[result_start:result_end].strip() if result_end > result_start else "Task completed"
            else:
                message = "Task completed successfully"
            return True, message
        else:
            return False, f"Task failed: {error or output}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"


def parse_status_response(message: str) -> Tuple[str, dict]:
    """Parse STATUS:XXX:key=value format from AI response."""
    result = {}
    status = "unknown"
    
    message_upper = message.upper()
    
    # Find STATUS: pattern
    if "STATUS:" in message_upper:
        parts = message.split("STATUS:")
        if len(parts) > 1:
            status_part = parts[1].strip().split()[0]
            status_parts = status_part.split(":")
            status = status_parts[0].lower()
            
            for part in status_parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    result[key.lower()] = value
    
    # Check for common patterns
    if "logged_in" in message_upper or "already logged in" in message_upper:
        status = "logged_in"
    elif "not_logged_in" in message_upper or "login screen" in message_upper:
        status = "not_logged_in"
    elif "mfa_required" in message_upper or "mfa" in message_upper.split():
        status = "mfa_required"
    elif "login_failed" in message_upper or "failed" in message_upper:
        status = "login_failed"
    elif "login_success" in message_upper or "success" in message_upper:
        status = "login_success"
    
    return status, result
