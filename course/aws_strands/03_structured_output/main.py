"""
Lesson 3: Structured Output

This script demonstrates how to extract structured data (like JSON) from
unstructured text using an agent.

We'll define a Pydantic model to specify the desired data schema, and the
agent's `structured_output` method will handle the extraction, parsing,
and validation.
"""

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from strands import Agent
from strands.models.litellm import LiteLLMModel

# Load environment variables from a .env file
load_dotenv()

# Define the data schema using a Pydantic model.
# This tells the agent exactly what information to extract and in what format.
class PersonInfo(BaseModel):
    """A Pydantic model to represent structured information about a person."""

    name: str = Field(..., description="The full name of the person.")
    age: int = Field(..., description="The age of the person.")
    occupation: str = Field(..., description="The current occupation of the person.")

def main():
    """
    Main function to demonstrate structured data extraction.
    """
    # Configure the language model
    model = LiteLLMModel(
        client_args={"api_key": os.getenv("NEBIUS_API_KEY")},
        model_id="nebius/zai-org/GLM-4.5",
    )
    # Create the data extraction agent
    agent = Agent(
        model=model,
        system_prompt="You are an expert assistant that extracts structured information about people from text based on the provided schema.",
        structured_output_model=PersonInfo,
    )

    # Unstructured text containing the information we want to extract
    text_to_process = (
        "John Smith is a 30-year-old software engineer living in San Francisco."
    )

    print(f"--- Extracting information from text ---\n")
    print(f'Input Text: "{text_to_process}"\n')

    # Use the structured_output method to extract the data
    # The agent will return a validated Pydantic object.
    try:
        result = agent(text_to_process)
        person_info: PersonInfo = result.structured_output

        # result_2 = agent(text_to_process, structured_output_model=ComapnyInfo)
        print("--- Extraction Successful ---")
        print(f"Name: {person_info.name}")
        print(f"Age: {person_info.age}")
        print(f"Occupation: {person_info.occupation}")

    except Exception as e:
        print("--- Extraction Failed ---")
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
