import json
import os
import datetime
import requests
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('alm.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

OLLAMA_MODEL = "gemma3:4b"
MEMORY_FILE = "alm_memory.json"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MAX_LOG_ENTRIES = 100  # Prevent memory log from growing infinitely
REQUEST_TIMEOUT = 30  # seconds


class ALMError(Exception):
    """Base exception for ALM-related errors"""
    pass


class OllamaConnectionError(ALMError):
    """Raised when connection to Ollama fails"""
    pass


class MemoryError(ALMError):
    """Raised when memory operations fail"""
    pass


def load_memory() -> Dict[str, Any]:
    """Load memory from disk with error handling"""
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding='utf-8') as f:
                memory = json.load(f)
                # Validate memory structure
                if not isinstance(memory, dict):
                    raise ValueError("Memory file format is invalid")
                if "goals" not in memory or "log" not in memory:
                    logger.warning("Memory file missing required keys, initializing defaults")
                    memory.setdefault("goals", [])
                    memory.setdefault("log", [])
                return memory
        return {"goals": [], "log": []}
    except (json.JSONDecodeError, IOError, ValueError) as e:
        logger.error(f"Failed to load memory: {e}")
        logger.info("Creating new memory file")
        return {"goals": [], "log": []}


def save_memory(memory: Dict[str, Any]) -> None:
    """Save memory to disk with error handling"""
    try:
        # Limit log size to prevent unbounded growth
        if len(memory["log"]) > MAX_LOG_ENTRIES:
            memory["log"] = memory["log"][-MAX_LOG_ENTRIES:]
            logger.info(f"Trimmed memory log to {MAX_LOG_ENTRIES} entries")
        
        with open(MEMORY_FILE, "w", encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except (IOError, TypeError) as e:
        logger.error(f"Failed to save memory: {e}")
        raise MemoryError(f"Could not save memory: {e}")


def query_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Query the local Ollama model with error handling"""
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    
    if not model.strip():
        model = OLLAMA_MODEL  # Fallback to default
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()  # Raise exception for bad status codes
        
        response_data = response.json()
        if "response" not in response_data:
            raise ValueError("Invalid response format from Ollama")
        
        return response_data["response"]
    
    except requests.exceptions.ConnectionError:
        raise OllamaConnectionError("Could not connect to Ollama server. Is it running?")
    except requests.exceptions.Timeout:
        raise OllamaConnectionError(f"Request to Ollama timed out after {REQUEST_TIMEOUT} seconds")
    except requests.exceptions.RequestException as e:
        raise OllamaConnectionError(f"Request to Ollama failed: {e}")
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise OllamaConnectionError(f"Invalid response from Ollama: {e}")


def build_prompt(memory: Dict[str, Any], user_input: str) -> str:
    """Generate prompt from current state"""
    if not user_input.strip():
        raise ValueError("User input cannot be empty")
    
    # Get recent log entries safely
    recent_log = memory.get("log", [])[-5:]
    past_log = "\n".join(
        f"{entry.get('timestamp', 'Unknown')}: {entry.get('user', 'Unknown')}" 
        for entry in recent_log
    )
    
    # Get goals safely
    goals = memory.get("goals", [])
    goals_text = "\n".join(f"- {goal}" for goal in goals if goal)
    
    return f"""
You are an autonomous language model tasked with helping a human achieve their goals.

Current Goals:
{goals_text or 'No goals yet.'}

Recent Interaction Log:
{past_log or 'None'}

Human said: {user_input}

Based on the goals and history, provide a thoughtful response and optionally add or update a goal or memory entry.
"""


def main() -> None:
    """Main REPL loop with comprehensive error handling"""
    logger.info("Starting Autonomous Language Model (ALM)")
    
    try:
        memory = load_memory()
        logger.info(f"Loaded memory with {len(memory['goals'])} goals and {len(memory['log'])} log entries")
    except Exception as e:
        logger.error(f"Failed to initialize memory: {e}")
        return
    
    print("Autonomous Language Model (ALM) is ready. Type 'exit' to quit.")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() == "exit":
                logger.info("User requested exit")
                break
            
            if not user_input:
                print("Please enter a message.")
                continue
            
            logger.info(f"Processing user input: {user_input[:50]}...")
            
            # Build prompt and query Ollama
            prompt = build_prompt(memory, user_input)
            response = query_ollama(prompt)
            
            # Log the interaction
            timestamp = datetime.datetime.utcnow().isoformat()
            memory["log"].append({
                "timestamp": timestamp,
                "user": user_input,
                "model": response
            })
            
            # Save memory
            save_memory(memory)
            
            print(f"ALM: {response.strip()}\n")
            logger.info("Interaction completed successfully")
            
        except KeyboardInterrupt:
            logger.info("User interrupted with Ctrl+C")
            break
        except OllamaConnectionError as e:
            logger.error(f"Ollama connection error: {e}")
            print(f"Error: {e}")
            print("Please check that Ollama is running and try again.")
        except MemoryError as e:
            logger.error(f"Memory error: {e}")
            print(f"Error saving memory: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"An unexpected error occurred: {e}")
    
    print("ALM session ended.")
    logger.info("ALM session ended")


if __name__ == "__main__":
    main()
