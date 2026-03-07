import os
import asyncio
import json

from tenacity import retry, wait_random_exponential, stop_after_attempt

import pydantic.networks as pydantic_networks
from pydantic_core import Url as PydanticCoreUrl

if not hasattr(pydantic_networks, "Url"):
    pydantic_networks.Url = PydanticCoreUrl

from semantic_kernel.functions.kernel_arguments import KernelArguments
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.functions import KernelPlugin
import semantic_kernel as sk

ORCHESTRATOR_FOLDER = "orc"
PLUGINS_FOLDER = f"{ORCHESTRATOR_FOLDER}/plugins"
BOT_DESCRIPTION_FILE = f"{ORCHESTRATOR_FOLDER}/bot_description.prompt"

async def create_kernel(service_id='aoai_chat_completion'):
    kernel = sk.Kernel()
    kernel.add_service(
        OpenAIChatCompletion(
            ai_model_id="gpt-4o",
            service_id=service_id,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    )
    return kernel

@retry(wait=wait_random_exponential(min=20, max=60), stop=stop_after_attempt(6), reraise=True)
async def call_semantic_function(kernel, function, arguments):
    function_result = await kernel.invoke(function, arguments)
    return function_result

async def get_answer(query: str, history: list, conv_id: str) -> str:
    bot_description = open(BOT_DESCRIPTION_FILE, "r").read()

    kernel = await create_kernel()
    # create the arguments that will used by semantic functions
    arguments = KernelArguments()
    arguments["bot_description"] = bot_description
    arguments["ask"] = query
    arguments["history"] = history
    arguments["previous_answer"] = history[-2]['content'] if len(history) > 1 else ""
    # import RAG plugins
    conversationPluginTask = asyncio.create_task(asyncio.to_thread(kernel.add_plugin, KernelPlugin.from_directory(parent_directory=PLUGINS_FOLDER,plugin_name="Conversations")))
    retrievalPluginTask = asyncio.create_task(asyncio.to_thread(kernel.add_plugin, KernelPlugin.from_directory(parent_directory=PLUGINS_FOLDER,plugin_name="Retrieval")))
    
    conversationPlugin= await conversationPluginTask

    function_result = await call_semantic_function(kernel, conversationPlugin["Language"], arguments)
    detected_language = str(function_result)
    arguments["language"] = detected_language

    if history != []:
        function_result = await call_semantic_function(kernel, conversationPlugin["ConversationSummary"], arguments)
        conversation_history_summary =  str(function_result)
    else:
        conversation_history_summary =  ""
    arguments["conversation_summary"] = conversation_history_summary

    function_result =  await call_semantic_function(kernel, conversationPlugin["Triage"], arguments)
    triage_result = str(function_result)    

    try:
        response = triage_result.strip("`json\n`")
        triage_dict = json.loads(response)
    except json.JSONDecodeError:
        raise Exception(f"Triage was not successful due to a JSON error. Invalid json: {triage_result}") 
    
    intents = triage_dict.get("intents", [])
    if set(intents).intersection({"follow_up", "question_answering"}):
        answer = triage_dict['answer']
        retrievalPlugin= await retrievalPluginTask
       
        search_query = triage_dict['query_string'] if triage_dict['query_string'] != '' else query
        search_function_result = await kernel.invoke(retrievalPlugin["VectorIndexRetrieval"], KernelArguments(input=search_query))
        arguments["sources"] = search_function_result

        function_result = await call_semantic_function(kernel, conversationPlugin["Answer"], arguments)
        answer =  str(function_result)
        
    elif set(intents).intersection({"about_bot", "off_topic"}):
        answer = triage_dict['answer']
        
    elif "greeting" in intents:
        answer = triage_dict['answer']

    elif intents == ["none"]:
        answer = "unable to provide answer now"
    else:
        print(f"Unexpected triage result: {intents}")
        answer = "unable to provide answer now"
    
    return answer