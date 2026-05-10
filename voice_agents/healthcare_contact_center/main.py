"""Voice AI healthcare contact center.

Pipeline: WebRTC/Daily -> Cartesia STT -> Nebius LLM (with tools) -> Cartesia TTS -> out.
On escalation, swaps the TTS voice and injects a Supervisor system prompt mid-session.
"""

import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import LLMRunFrame, TTSUpdateSettingsFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.stt import CartesiaSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.nebius.llm import NebiusLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.daily.transport import DailyParams

from personalities import (
    FRONT_DESK_PROMPT,
    FRONT_DESK_VOICE,
    SUPERVISOR_PROMPT,
    SUPERVISOR_VOICE,
)
from tools.appointments import book_appointment, check_availability
from tools.escalation import escalate_to_human
from tools.knowledge_base import lookup_faq

load_dotenv(override=True)


# ---------- Tool schemas ----------

check_availability_tool = FunctionSchema(
    name="check_availability",
    description="List open appointment slots, optionally filtered by date or doctor.",
    properties={
        "date": {"type": "string", "description": "ISO date YYYY-MM-DD. Optional."},
        "doctor": {"type": "string", "description": "Doctor name fragment. Optional."},
    },
    required=[],
)

book_appointment_tool = FunctionSchema(
    name="book_appointment",
    description="Book a specific slot for a patient. Confirm name and phone before calling.",
    properties={
        "slot_id": {"type": "string", "description": "Slot ID from check_availability."},
        "patient_name": {"type": "string", "description": "Patient full name."},
        "phone": {"type": "string", "description": "Patient callback phone number."},
    },
    required=["slot_id", "patient_name", "phone"],
)

lookup_faq_tool = FunctionSchema(
    name="lookup_faq",
    description="Look up clinic policy: hours, insurance, billing, location, new-patient info.",
    properties={
        "query": {"type": "string", "description": "The patient question, verbatim."},
    },
    required=["query"],
)

escalate_tool = FunctionSchema(
    name="escalate_to_human",
    description=(
        "Escalate the call to a supervisor. Use for emergencies, complaints, "
        "or anything you cannot handle."
    ),
    properties={
        "reason": {"type": "string", "description": "Why escalation is needed."},
        "urgency": {
            "type": "string",
            "enum": ["normal", "emergency"],
            "description": "Use 'emergency' for medical emergencies.",
        },
        "summary": {"type": "string", "description": "Short summary of the call so far."},
    },
    required=["reason", "urgency"],
)

TOOLS = ToolsSchema(
    standard_tools=[
        check_availability_tool,
        book_appointment_tool,
        lookup_faq_tool,
        escalate_tool,
    ]
)


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(
        runner_args,
        {
            "daily": lambda: DailyParams(audio_in_enabled=True, audio_out_enabled=True),
            "webrtc": lambda: TransportParams(
                audio_in_enabled=True, audio_out_enabled=True
            ),
        },
    )

    stt = CartesiaSTTService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        settings=CartesiaSTTService.Settings(model="ink-whisper", language="en"),
    )

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        settings=CartesiaTTSService.Settings(voice=FRONT_DESK_VOICE),
    )

    llm = NebiusLLMService(
        api_key=os.getenv("NEBIUS_API_KEY"),
        settings=NebiusLLMService.Settings(model="openai/gpt-oss-120b"),
    )

    messages = [{"role": "system", "content": FRONT_DESK_PROMPT}]
    context = LLMContext(messages=messages, tools=TOOLS)
    context_aggregator = LLMContextAggregatorPair(context)

    # ---------- Tool handlers ----------

    async def handle_check_availability(params: FunctionCallParams):
        slots = check_availability(
            date=params.arguments.get("date"),
            doctor=params.arguments.get("doctor"),
        )
        await params.result_callback({"slots": slots})

    async def handle_book_appointment(params: FunctionCallParams):
        result = book_appointment(
            slot_id=params.arguments["slot_id"],
            patient_name=params.arguments["patient_name"],
            phone=params.arguments["phone"],
        )
        await params.result_callback(result)

    async def handle_lookup_faq(params: FunctionCallParams):
        await params.result_callback(lookup_faq(params.arguments["query"]))

    async def handle_escalate(params: FunctionCallParams):
        result = escalate_to_human(
            reason=params.arguments["reason"],
            urgency=params.arguments.get("urgency", "normal"),
            summary=params.arguments.get("summary", ""),
        )
        # Switch personality: new voice + supervisor system prompt for the next turn.
        logger.info("Switching personality to Supervisor")
        await tts.push_frame(
            TTSUpdateSettingsFrame(
                settings=CartesiaTTSService.Settings(voice=SUPERVISOR_VOICE)
            )
        )
        messages.append({"role": "system", "content": SUPERVISOR_PROMPT})
        await params.result_callback(result)

    llm.register_function("check_availability", handle_check_availability)
    llm.register_function("book_appointment", handle_book_appointment)
    llm.register_function("lookup_faq", handle_lookup_faq)
    llm.register_function("escalate_to_human", handle_escalate)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(pipeline)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Caller connected")
        messages.append(
            {
                "role": "system",
                "content": "Greet the caller as Aria from Wellness Clinic and ask how you can help.",
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Caller disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
