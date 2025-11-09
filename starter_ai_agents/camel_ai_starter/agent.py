import time
import matplotlib.pyplot as plt
from camel.agents import ChatAgent
from camel.configs import NebiusConfig, ChatGPTConfig
from camel.messages import BaseMessage
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

from dotenv import load_dotenv

load_dotenv()

# Create model instances
def create_models():
    model_configs = [
        (ModelPlatformType.OPENAI, ModelType.GPT_4O_MINI, ChatGPTConfig(temperature=0.0, max_tokens=2000), "OpenAI GPT-4O Mini"),
        (ModelPlatformType.OPENAI, ModelType.GPT_4O, ChatGPTConfig(temperature=0.0, max_tokens=2000), "OpenAI GPT-4O"),
# Nebius Models
        (ModelPlatformType.NEBIUS, "moonshotai/Kimi-K2-Instruct", NebiusConfig(temperature=0.0, max_tokens=2000), "Nebius Kimi-K2-Instruct"),
        (ModelPlatformType.NEBIUS, "Qwen/Qwen3-Coder-480B-A35B-Instruct", NebiusConfig(temperature=0.0, max_tokens=2000), "Nebius Qwen3-Coder-480B-A35B-Instruct"),
        (ModelPlatformType.NEBIUS, "zai-org/GLM-4.5-Air", NebiusConfig(temperature=0.0, max_tokens=2000), "Nebius GLM-4.5-Air")
    ]

    models = [(ModelFactory.create(model_platform=platform, model_type=model_type, model_config_dict=config.as_dict(), url="https://api.tokenfactory.nebius.com/v1" if platform == ModelPlatformType.NEBIUS else None), name)
              for platform, model_type, config, name in model_configs]
    return models

# Define messages
def create_messages():
    sys_msg = BaseMessage.make_assistant_message(role_name="Assistant", content="You are a helpful assistant.")
    user_msg = BaseMessage.make_user_message(role_name="User", content="Tell me a long story.")
    return sys_msg, user_msg

# Initialize ChatAgent instances
def initialize_agents(models, sys_msg):
    return [(ChatAgent(system_message=sys_msg, model=model), name) for model, name in models]

# Measure response time for a given agent
def measure_response_time(agent, message):
    start_time = time.time()
    response = agent.step(message)
    end_time = time.time()
    tokens_per_second = response.info['usage']["completion_tokens"] / (end_time - start_time)
    return tokens_per_second

# Visualize results
def plot_results(model_names, tokens_per_sec):
    plt.figure(figsize=(10, 6))
    plt.barh(model_names, tokens_per_sec, color='skyblue')
    plt.xlabel("Tokens per Second")
    plt.title("Model Speed Comparison: Tokens per Second")
    plt.gca().invert_yaxis()
    plt.show()

# Main execution
models = create_models()
sys_msg, user_msg = create_messages()
agents = initialize_agents(models, sys_msg)

# Measure response times and collect data
model_names = []
tokens_per_sec = []

for agent, model_name in agents:
    model_names.append(model_name)
    tokens_per_sec.append(measure_response_time(agent, user_msg))

# Visualize the results
plot_results(model_names, tokens_per_sec)