from crewai import Agent, Task,LLM
import os
from dotenv import load_dotenv
from crewai import Crew, Process

load_dotenv()

# Create a researcher agent
researcher = Agent(
  role='Senior Researcher',
  goal='Discover groundbreaking technologies',
  verbose=True,
  llm=LLM(
        model="nebius/Qwen/Qwen3-235B-A22B",
        api_key=os.getenv("NEBIUS_API_KEY")
  ),
  backstory='A curious mind fascinated by cutting-edge innovation and the potential to change the world, you know everything about tech.'
)

# Task for the researcher
research_task = Task(
  description='Identify the next big trend in AI',
  expected_output='5 paragraphs on the next big AI trend',
  agent=researcher  # Assigning the task to the researcher
)

# Instantiate your crew
tech_crew = Crew(
  agents=[researcher],
  tasks=[research_task],
  process=Process.sequential  # Tasks will be executed one after the other
)

# Begin the task execution
tech_crew.kickoff()
