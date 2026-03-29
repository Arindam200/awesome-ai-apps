import os
from dotenv import load_dotenv
from loguru import logger
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.daily.transport import DailyParams

load_dotenv(override=True)


def build_llm_service() -> OpenAILLMService:
    """Create OpenAI-compatible LLM service using OpenAI or Nebius provider."""
    llm_provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    allowed_providers = {"openai", "nebius"}
    if llm_provider not in allowed_providers:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{llm_provider}'. "
            f"Supported providers are: {', '.join(sorted(allowed_providers))}."
        )

    if llm_provider == "nebius":
        api_key = os.getenv("NEBIUS_API_KEY")
        if not api_key:
            raise ValueError("NEBIUS_API_KEY is required when LLM_PROVIDER=nebius")

        model = os.getenv("NEBIUS_MODEL", "deepseek-ai/DeepSeek-V3-0324")
        base_url = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")

        # Prefer explicit base_url, but support older Pipecat versions without that arg.
        try:
            llm = OpenAILLMService(api_key=api_key, model=model, base_url=base_url)
        except TypeError as e:
            # Only fall back if the error is due to an unexpected 'base_url' kwarg.
            if "base_url" not in str(e):
                raise
            os.environ["OPENAI_BASE_URL"] = base_url
            llm = OpenAILLMService(api_key=api_key, model=model)

        logger.info("Using Nebius Token Factory LLM model: {}", model)
        return llm

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    logger.info("Using OpenAI LLM model: {}", model)
    return OpenAILLMService(api_key=api_key, model=model)

async def bot(runner_args: RunnerArguments):
    """Main bot entry point."""
    
    # Create transport (supports both Daily and WebRTC)
    transport = await create_transport(
        runner_args,
        {
            "daily": lambda: DailyParams(audio_in_enabled=True, audio_out_enabled=True),
            "webrtc": lambda: TransportParams(
                audio_in_enabled=True, audio_out_enabled=True
            ),
        },
    )

    # Initialize AI services
    stt = SarvamSTTService(api_key=os.getenv("SARVAM_API_KEY"),)
    tts = SarvamTTSService(api_key=os.getenv("SARVAM_API_KEY"))
    llm = build_llm_service()

    # Set up conversation context
    messages = [
        {
            "role": "system",
            "content": "You are a friendly AI assistant. Keep your responses brief and conversational.",
        },
    ]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)

    # Build pipeline
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
        logger.info("Client connected")
        messages.append(
            {"role": "system", "content": "Say hello and briefly introduce yourself."}
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)

if __name__ == "__main__":
    from pipecat.runner.run import main
    main()
