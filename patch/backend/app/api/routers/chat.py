import os
import logging
import asyncio

from aiostream import stream
from fastapi import APIRouter, Depends, HTTPException, Request, status, WebSocket, WebSocketDisconnect
from llama_index.core.chat_engine.types import BaseChatEngine
from llama_index.core.llms import MessageRole
from app.engine import get_chat_engine
from app.api.routers.vercel_response import VercelStreamResponse
from app.api.routers.events import EventCallbackHandler
from app.api.routers.models import (
    ChatData,
    ChatConfig,
    SourceNodes,
    Result,
    Message,
)

chat_router = r = APIRouter()

logger = logging.getLogger("uvicorn")

event_handler_instance = EventCallbackHandler()

def get_event_callback_handler():
    return event_handler_instance
# streaming endpoint - delete if not needed
# @r.post("")
# async def chat(
#     request: Request,
#     data: ChatData,
#     chat_engine: BaseChatEngine = Depends(get_chat_engine),
# ):
#     try:
#         last_message_content = data.get_last_message_content()
#         messages = data.get_history_messages()

#         # event_handler = EventCallbackHandler()
#         chat_engine.callback_manager.handlers.append(event_handler)  # type: ignore

#         async def content_generator():
#             # Yield the text response
#             print('running context generator')
#             async def _chat_response_generator():
#                 print('running chat response generator')
#                 response = await chat_engine.astream_chat(
#                     last_message_content, messages
#                 )
#                 async for token in response.async_response_gen():
#                     yield VercelStreamResponse.convert_text(token)
#                 # the text_generator is the leading stream, once it's finished, also finish the event stream
#                 event_handler.is_done = True

#                 # Yield the source nodes
#                 yield VercelStreamResponse.convert_data(
#                     {
#                         "type": "sources",
#                         "data": {
#                             "nodes": [
#                                 SourceNodes.from_source_node(node).dict()
#                                 for node in response.source_nodes
#                             ]
#                         },
#                     }
#                 )

#             # Yield the events from the event handler
#             async def _event_generator():
#                 print('running event handler generator')
#                 async for event in event_handler.async_event_gen():
#                     event_response = event.to_response()
#                     print("event_response: ", event_response)
#                     if event_response is not None:
#                         yield VercelStreamResponse.convert_data(event_response)

#             combine = stream.merge(_chat_response_generator(), _event_generator())
#             is_stream_started = False
#             async with combine.stream() as streamer:
#                 async for output in streamer:
#                     print('output: ', output)
#                     if not is_stream_started:
#                         is_stream_started = True
#                         # Stream a blank message to start the stream
#                         yield VercelStreamResponse.convert_text("")

#                     yield output

#                     if await request.is_disconnected():
#                         break

#         return VercelStreamResponse(content=content_generator())
#     except Exception as e:
#         logger.exception("Error in chat engine", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error in chat engine: {e}",
#         ) from e
from qdrant_client import QdrantClient, models

@r.post("")
async def chat(
    request: Request,
    data: ChatData,
    chat_engine: BaseChatEngine = Depends(get_chat_engine),
    event_handler: EventCallbackHandler = Depends(get_event_callback_handler),  # Ensure DI here
):
    try:

        last_message_content = data.get_last_message_content()
        messages = data.get_history_messages()
        chat_engine.callback_manager.handlers.append(event_handler)  # type: ignore

        async def content_generator():
            async def _chat_response_generator():
                response = await chat_engine.astream_chat(last_message_content, messages)
                async for token in response.async_response_gen():
                    yield VercelStreamResponse.convert_text(token)
                event_handler.is_done = True
                yield VercelStreamResponse.convert_data(
                    {
                        "type": "sources",
                        "data": {
                            "nodes": [
                                SourceNodes.from_source_node(node).dict()
                                for node in response.source_nodes
                            ]
                        },
                    }
                )

            async def _event_generator():
                async for event in event_handler.async_event_gen():
                    event_response = event.to_response()
                    if event_response is not None:
                        yield VercelStreamResponse.convert_data(event_response)

            combine = stream.merge(_chat_response_generator(), _event_generator())
            is_stream_started = False
            async with combine.stream() as streamer:
                async for output in streamer:
                    if not is_stream_started:
                        is_stream_started = True
                        yield VercelStreamResponse.convert_text("")

                    yield output

                    if await request.is_disconnected():
                        break

        return VercelStreamResponse(content=content_generator())
    except Exception as e:
        logger.exception("Error in chat engine", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in chat engine: {e}",
        ) from e


# non-streaming endpoint - delete if not needed
@r.post("/request")
async def chat_request(
    data: ChatData,
    chat_engine: BaseChatEngine = Depends(get_chat_engine),
) -> Result:
    last_message_content = data.get_last_message_content()
    messages = data.get_history_messages()

    response = await chat_engine.achat(last_message_content, messages)
    return Result(
        result=Message(role=MessageRole.ASSISTANT, content=response.response),
        nodes=SourceNodes.from_source_nodes(response.source_nodes),
    )


@r.get("/config")
async def chat_config() -> ChatConfig:
    starter_questions = None
    conversation_starters = os.getenv("CONVERSATION_STARTERS")
    if conversation_starters and conversation_starters.strip():
        starter_questions = conversation_starters.strip().split("\n")
    return ChatConfig(starterQuestions=starter_questions)


# @r.websocket("/ws/events")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     event_handler = EventCallbackHandler()
#     # event_handler.set_websocket(websocket)

#     try:
#         while True:
#             if event_handler.current_event is not None:
#                 print(event_handler.current_event)
#                 await websocket.send_json(event_handler.current_event)

#             await asyncio.sleep(2)
            
#     except WebSocketDisconnect:
#         # Handle WebSocket disconnection
#         print("WebSocket connection closed")
import json
@r.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    async def send_test_message():
        while True:
            event_data = {
                "type": "event",
                "data": {"message": "This is a test message from the server."},
            }
            await websocket.send(json.dumps(event_data))
            await asyncio.sleep(2)  # Send the message every 2 seconds

    send_task = asyncio.create_task(send_test_message())

    async for message in websocket:
        pass  # You can process incoming messages from the client here if needed

    # Cancel the send_task when the client disconnects
    send_task.cancel()
    await websocket.close()


# async def websocket_endpoint(websocket: WebSocket, event_handler: EventCallbackHandler = Depends(get_event_callback_handler)):
#     await websocket.accept()
#     event_handler.websocket = websocket  # Set the WebSocket instance

#     try:
#         async for event in event_handler.async_event_gen():
#             event_response = event.to_response()
#             if event_response is not None:
#                 await websocket.send_json(event_response)

#         # await websocket.close()
#     except WebSocketDisconnect:
#         event_handler.websocket = None  # Handle WebSocket disconnection
#         logger.info("WebSocket connection closed")
#     finally:
#         event_handler.websocket = None  # Ensure cleanup




    # try:
    #     while True:
    #         data = await websocket.receive_text()
    #         # Process incoming data here. This part is optional and depends on your needs.
    #         # For example, you could emit events based on the received data.
    #         print(f"Message received from the client: {data}")
    # except Exception as e:
    #     print(f"WebSocket connection closed with exception: {e}")
    # finally:
    #     # Perform any necessary cleanup here
    #     print("WebSocket connection closed")


from fastapi import HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

@r.get("/download")
def download_file():
    file_path = Path("reports/Results-LLM.xlsx")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(file_path), filename="Results-LLM.xlsx")