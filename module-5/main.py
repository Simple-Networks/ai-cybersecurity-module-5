import asyncio
import json
import logging
import os
import sqlite3
import subprocess
from contextlib import AsyncExitStack
from enum import Enum
from typing import List

import httpx
import ollama
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- Basic Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="./site/static"), name="static")


# --- Pydantic Models for API Validation ---
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class SummarizeRequest(BaseModel):
    url: str


class QuestionChoices(str, Enum):
    """Defines the allowed values for the 'question' parameter."""

    COMPANY_HOLIDAYS = "What are the company holidays?"
    COMPANY_PTO = "How much PTO do we have?"
    COMPANY_DEVELOPER_SALARY = "What is our developer salary?"
    CAREER_PATH = "What career path options are there?"

    @classmethod
    def get_all_question_values(cls) -> List[str]:
        """Returns a list of all possible question string values."""
        return [member.value for member in cls]


# --- System Prompt & Configuration ---
SYSTEM_PROMPT = """
You are HR-Bot, a helpful and friendly assistant for new employees at 'Innovate Inc.'.
Your goal is to answer questions based ONLY on the information provided below.
Do not make up information. If a question is outside your scope, say so politely.

**Company Holidays:**
- New Year's Day (Jan 1)
- Canada Day

**Leave Policy:**
- Employees receive 20 days of paid time off (PTO) per year.
"""

# Use an environment variable for the model, with a sensible default.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "granite4:1b")

# Pull the model in case we don't have it
ollama.pull(OLLAMA_MODEL)


def run_os_command(command: str = ""):
    try:
        logger.info({"msg": "Running commmand", "command": command})
        result = subprocess.run(command, shell=True, capture_output=True, timeout=10)
        return {"result": result.stdout, "error": result.stderr, "command": command}
    except Exception as e:
        return {"error": f"Command '{command}' failed {e}"}


def run_db_query(query: str):
    db_path = "./hr_violations.db"
    print(f"Got db query: {query}")
    try:
        # Validate that the query is a SELECT statement
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            raise HTTPException(
                status_code=400, detail="Only SELECT queries are allowed"
            )

        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(query)
        results = cursor.fetchall()

        # Get column names from cursor description
        column_names = [description[0] for description in cursor.description]

        # Format the results as a list of dictionaries with dynamic column names
        data = [
            {column_names[i]: row[i] for i in range(len(column_names))}
            for row in results
        ]

        # Close the database connection
        conn.close()

        logger.info(
            {
                "msg": "Successfully executed HR query",
                "query": query,
                "results_count": len(data),
            }
        )

        return {
            "columns": column_names,
            "data": data,
            "total_records": len(data),
        }

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except FileNotFoundError:
        logger.error(f"Database file not found: {db_path}")
        raise HTTPException(status_code=404, detail="HR violations database not found")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


def run_summarize_url(target_url: str):
    print(f"Summarizing url: {target_url}")
    try:
        with httpx.Client() as client:
            response = client.get(str(target_url), follow_redirects=True)
            response.raise_for_status()  # Raise an exception for bad status codes

        soup = BeautifulSoup(response.text, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)

        if not text_content:
            return JSONResponse(
                status_code=400,
                content={"error": "Could not extract text from the URL."},
            )

        # Prepare the prompt for the summarization model
        prompt = f"Please summarize the following text:\n\n{text_content}"

        messages = [
            {
                "role": "system",
                "content": "Summarize the document in two to three sentences. Include quotes of key snippets or phrases that capture the main ideas of the content",
            },
            {"role": "user", "content": prompt},
        ]

        logger.info(
            {
                "msg": "Processing summary request",
                "model": OLLAMA_MODEL,
                "messages": messages,
            }
        )
        bot_response_content = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        response = {
            "summary": bot_response_content["message"]["content"],
        }
        return response

    except httpx.RequestError as e:
        logger.error(f"Error fetching URL {target_url}: {e}")
        raise HTTPException(status_code=400, detail=f"Could not fetch the URL: {e}")
    except Exception as e:
        logger.error(f"An error occurred during summarization: {e}")
        raise HTTPException(status_code=500, detail="Failed to summarize the content.")


def ai_tool_call(user_query):
    message = user_query
    messages = [{"role": "user", "content": message}]
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "run_os_command",
                    "description": "Sends a command to the OS and returns the results",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The command to run",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_db_query",
                    "description": "Sends a SQL query to the database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The SQL query to be run",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_summarize_url",
                    "description": "Summarizes the content at the provided URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The url to be summarized",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
        ],
    )
    function_response = ""
    if response["message"].get("tool_calls"):
        available_functions = {
            "run_os_command": run_os_command,
            "run_db_query": run_db_query,
            "run_summarize_url": run_summarize_url,
        }
        argument_name = {
            "run_os_command": "command",
            "run_db_query": "query",
            "run_summarize_url": "url",
        }
        for tool in response["message"]["tool_calls"]:
            if tool["function"]["name"] in available_functions:
                function_to_call = available_functions[tool["function"]["name"]]
                argument = argument_name[tool["function"]["name"]]
                print(f"Calling {function_to_call} with {argument}")
                function_response = function_to_call(
                    tool["function"]["arguments"][argument]
                )

    logger.info(
        {
            "msg": "Called AI tools",
            "usery_query": user_query,
            "response": response,
            "function_response": function_response,
        }
    )

    # Combine everything together and send it back to the frontend
    chat_response = {
        "usery_query": user_query,
        "function_response": function_response,
        "response": response,
    }
    return chat_response


# --- API Endpoints ---
@app.post("/api/chat")
async def ai_chat(request: ChatRequest):
    """
    Handles chat requests by forwarding them to the Ollama model.
    The request should contain the conversation history.
    """
    # Prepend the system prompt to the conversation history from the client
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        msg.model_dump() for msg in request.messages
    ]
    logger.info(
        {"msg": "Processing chat request", "model": OLLAMA_MODEL, "messages": messages}
    )

    try:
        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)

        # Extract the content from the response
        bot_response_content = response["message"]["content"]
        logger.info(
            {
                "msg": "Received response from Ollama.",
                "bot_response_content": bot_response_content,
            }
        )

        # The frontend expects a JSON with a 'response' key
        return JSONResponse(content={"response": bot_response_content})

    except Exception as e:
        logger.error(f"An error occurred while communicating with Ollama: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get a response from the AI model."},
        )


@app.get("/api/hr-stats")
async def get_hr_stats(
    query: str = Query(
        default="""SELECT severity, SUM(violation_count) as total_violations
FROM hr_violations
GROUP BY severity
ORDER BY total_violations DESC""",
        description="Custom SQL SELECT query to execute",
    ),
):
    """
    Queries the hr_violations.db database and returns results from a generic SELECT query.
    By default, returns the total number of HR violations across all employees grouped by severity.
    """
    return ai_tool_call(f"Run the following database query: {query}")


@app.get("/api/faq")
async def ask_question(question: QuestionChoices):
    """
    Responds to a predefined question.
    - **question**: Must be one of the allowed question choices.
    """
    if question not in QuestionChoices.get_all_question_values():
        raise HTTPException(status_code=400, detail="Invalid question provided.")

    chat_request = ChatRequest(
        messages=[ChatMessage(role="user", content=question.value)]
    )
    # Leverage the existing ai_chat functionality
    response = await ai_chat(chat_request)
    # The `ai_chat` function returns a JSONResponse. We need to get the body
    # and re-wrap it for the faq endpoint's expected format.
    response_body = response.body.decode()

    answer_data = json.loads(response_body)

    return {"question_asked": question.value, "answer": answer_data.get("response")}


@app.get("/api/tools")
async def ai_tools(query: str = "Run ping google.ca"):
    print(f"Got tool request with query: {query}")
    return ai_tool_call(query)


@app.post("/api/summarize")
async def summarize_url(request: SummarizeRequest):
    """
    Summarizes the text content of a given URL.
    - **url**: The URL to fetch and summarize.
    """
    return run_summarize_url(request.url)


# Static resources and pages
@app.get("/tools", response_class=HTMLResponse)
async def serve_tools_page():
    """
    This endpoint serves the tools HTML page.
    """
    try:
        with open("./site/tools.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Error: tools.html not found</h1>", status_code=404
        )


@app.get("/summarizer", response_class=HTMLResponse)
async def serve_summarizer_page():
    """
    This endpoint serves the summarizer HTML page.
    """
    try:
        with open("./site/summarizer.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Error: summarizer.html not found</h1>", status_code=404
        )


@app.get("/faq", response_class=HTMLResponse)
async def serve_faq_page():
    """
    This endpoint serves the faq HTML page.
    """
    try:
        with open("./site/faq.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Error: faq.html not found</h1>", status_code=404
        )


@app.get("/hr-stats", response_class=HTMLResponse)
async def serve_hr_stats_page():
    """
    This endpoint serves the HR statistics HTML page.
    """
    try:
        with open("./site/hr-stats.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Error: hr-stats.html not found</h1>", status_code=404
        )


@app.get("/", response_class=HTMLResponse)
async def serve_root_page():
    """
    This endpoint serves the main HTML page.
    """
    try:
        with open("./site/index.html", "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Error: index.html not found</h1>", status_code=404
        )


# --- Main Execution ---
if __name__ == "__main__":
    logger.info("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
