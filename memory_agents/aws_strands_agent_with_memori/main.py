#!/usr/bin/env python3
"""
Professional Development Coach Agent with Memory using Strands SDK + LiteLLM

This example demonstrates how to integrate Memori memory capabilities with Strands SDK
and LiteLLM to create a professional development coach that remembers your career goals,
learning progress, and provides personalized coaching across multiple sessions.

Features:
- Memory-enhanced coaching with persistent context
- Career goal tracking and progress monitoring
- Personalized resource recommendations
- Multi-session conversation continuity
- Custom coaching tools with Strands SDK
- LiteLLM integration with Nebius Llama-3.1-70B model

Requirements:
- pip install memorisdk strands-agents python-dotenv 'strands-agents[litellm]' strands-agents-tools
- Nebius API key (for LiteLLM)

Usage:
    python aws_strands_example.py

Environment Variables:
    # For LiteLLM with Nebius AI Studio
    NEBIUS_API_KEY=your_nebius_api_key
"""

from typing import Dict, List, Optional, Any
import logging
import os

from dataclasses import dataclass
from datetime import datetime
import asyncio
def demo_coaching_session():
    """Demo function to show example interactions"""
    print("\n" + "="*60)
    print("📋 EXAMPLE COACHING SESSION")
    print("="*60)

    examples = [
        {
            "user": "Hi! I'm a software developer with 3 years of experience. I want to become a senior developer within the next 2 years.",
            "coach_action": "The coach would set your career goal, search memory for any previous interactions, and provide initial guidance."
        },
        {
            "user": "Can you assess my current Python skills? I'd say I'm at intermediate level.",
            "coach_action": "The coach would record your Python skill assessment and suggest areas for improvement."
        },
        {
            "user": "I just completed the 'Clean Code' book. Please update my progress.",
            "coach_action": "The coach would track this learning activity and potentially recommend related resources."
        },
        {
            "user": "What resources do you recommend for learning system design?",
            "coach_action": "The coach would provide personalized recommendations based on your goals and current skill level."
        },
        {
            "user": "What do you remember about my goals from our last conversation?",
            "coach_action": "The coach would search memory and recall your career goals, progress, and previous discussions."
        }
    ]

    for i, example in enumerate(examples, 1):
        print(f"\n Example {i}:")
        print(f"User: {example['user']}")
        print(f"Coach Action: {example['coach_action']}")

    print("\n" + "="*60)
    print(" Run the script to start your actual coaching session!")
    print("="*60)

try:
    from strands import Agent, tool
    from strands.models.litellm import LiteLLMModel
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    if __name__ == "__main__":
        import sys
        if len(sys.argv) <= 1 or sys.argv[1] != "--demo":
            print(" Error: strands-agents not installed")
            print("Install with: pip install strands-agents")
            exit(1)

try:
    from memori import Memori, create_memory_tool
    MEMORI_AVAILABLE = True
except ImportError:
    MEMORI_AVAILABLE = False
    if __name__ == "__main__":
        import sys
        if len(sys.argv) <= 1 or sys.argv[1] != "--demo":
            print(" Error: memorisdk not installed")
            print("Install with: pip install memorisdk")
            exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print(" Warning: python-dotenv not installed. Install with: pip install python-dotenv")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Mock tool decorator when strands is not available
if not STRANDS_AVAILABLE:
    def tool(func):
        return func

# Enable Strands debug logging (optional)
# logging.getLogger("strands").setLevel(logging.DEBUG)


@dataclass
class SkillAssessment:
    """Structure for skill assessments"""
    skill: str
    proficiency: str  # beginner, intermediate, advanced, expert
    last_updated: str
    notes: str


@dataclass
class CareerGoal:
    """Structure for career goals"""
    goal: str
    target_date: str
    progress: str
    priority: str  # high, medium, low


class ProfessionalCoachingTools:
    """Custom tools for professional development coaching"""

    def __init__(self, memori_instance):
        self.memori = memori_instance

    @tool
    def set_career_goal(self, goal: str, target_date: str, priority: str = "medium") -> str:
        """Set or update a career goal.

        Args:
            goal: The career goal description
            target_date: Target completion date (YYYY-MM-DD or description)
            priority: Goal priority (high, medium, low)
        """
        try:
            goal_data = {
                "goal": goal,
                "target_date": target_date,
                "priority": priority,
                "created_date": datetime.now().isoformat(),
                "status": "active"
            }

            # Store in memory for future reference
            memory_content = f"Career Goal Set: {goal} (Target: {target_date}, Priority: {priority})"

            return f"Career goal set successfully: '{goal}' with target date {target_date} (Priority: {priority})"

        except Exception as e:
            return f"Error setting career goal: {str(e)}"

    @tool
    def assess_skill(self, skill: str, proficiency: str, notes: str = "") -> str:
        """Record or update a skill assessment.

        Args:
            skill: The skill name (e.g., "Python", "Leadership", "Data Analysis")
            proficiency: Proficiency level (beginner, intermediate, advanced, expert)
            notes: Additional notes about the skill
        """
        try:
            valid_levels = ["beginner", "intermediate", "advanced", "expert"]
            if proficiency.lower() not in valid_levels:
                return f" Invalid proficiency level. Use: {', '.join(valid_levels)}"

            assessment_data = {
                "skill": skill,
                "proficiency": proficiency.lower(),
                "assessment_date": datetime.now().isoformat(),
                "notes": notes
            }

            memory_content = f"Skill Assessment: {skill} - {proficiency} level"
            if notes:
                memory_content += f" (Notes: {notes})"

            return f"Skill assessment recorded: {skill} at {proficiency} level"

        except Exception as e:
            return f"Error recording skill assessment: {str(e)}"

    @tool
    def track_learning_progress(self, activity: str, status: str, notes: str = "") -> str:
        """Track learning activities and progress.

        Args:
            activity: Learning activity (course, book, project, certification)
            status: Current status (started, in_progress, completed, paused)
            notes: Additional progress notes
        """
        try:
            valid_statuses = ["started", "in_progress", "completed", "paused"]
            if status.lower() not in valid_statuses:
                return f" Invalid status. Use: {', '.join(valid_statuses)}"

            progress_data = {
                "activity": activity,
                "status": status.lower(),
                "updated_date": datetime.now().isoformat(),
                "notes": notes
            }

            memory_content = f"Learning Progress: {activity} - {status}"
            if notes:
                memory_content += f" (Notes: {notes})"

            return f"Learning progress updated: {activity} - {status}"

        except Exception as e:
            return f" Error tracking learning progress: {str(e)}"

    @tool
    def recommend_resources(self, topic: str, resource_type: str = "any") -> str:
        """Get personalized learning resource recommendations.

        Args:
            topic: Topic or skill area for recommendations
            resource_type: Type of resource (course, book, project, certification, any)
        """
        try:
            # This would typically connect to a resource database or API
            # For this example, we'll provide sample recommendations

            recommendations = {
                "python": {
                    "course": ["Python for Everybody (Coursera)", "Automate the Boring Stuff with Python"],
                    "book": ["Python Crash Course", "Effective Python"],
                    "project": ["Build a web scraper", "Create a REST API with FastAPI"],
                    "certification": ["Python Institute PCAP", "Microsoft Python Developer"]
                },
                "leadership": {
                    "course": ["Leadership Fundamentals (LinkedIn Learning)", "Leading Teams (Coursera)"],
                    "book": ["The 7 Habits of Highly Effective People", "Leaders Eat Last"],
                    "project": ["Lead a team project", "Mentor a junior colleague"],
                    "certification": ["PMI Leadership Certificate", "Google Project Management"]
                },
                "data analysis": {
                    "course": ["Data Analysis with Python", "Statistics for Data Science"],
                    "book": ["Python for Data Analysis", "The Art of Statistics"],
                    "project": ["Analyze public datasets", "Build a data dashboard"],
                    "certification": ["Google Data Analytics", "Microsoft Power BI"]
                }
            }

            topic_lower = topic.lower()
            resource_recommendations = []

            # Find matching topics
            for key, resources in recommendations.items():
                if key in topic_lower or topic_lower in key:
                    if resource_type == "any":
                        for res_type, items in resources.items():
                            resource_recommendations.extend([f"{res_type.title()}: {item}" for item in items])
                    elif resource_type in resources:
                        resource_recommendations.extend([f"{resource_type.title()}: {item}" for item in resources[resource_type]])

            if not resource_recommendations:
                return f" I don't have specific recommendations for '{topic}' yet. Consider searching online courses, books, or industry certifications related to this topic."

            result = f" Recommended resources for {topic}:\n\n"
            for i, rec in enumerate(resource_recommendations[:5], 1):  # Limit to 5 recommendations
                result += f"{i}. {rec}\n"

            return result

        except Exception as e:
            return f" Error getting recommendations: {str(e)}"


def check_environment() -> tuple[bool, str]:
    """Check if required environment variables are set"""

    # Check for Nebius API key (preferred provider with LiteLLM)
    nebius_api_key = os.getenv("NEBIUS_API_KEY")

    if nebius_api_key:
        return True, "litellm"
    else:
        return False, "missing_credentials"

def initialize_memory_system():
    """Initialize and configure the Memori memory system"""

    if not MEMORI_AVAILABLE:
        raise ImportError("Memori not available")

    try:
        # Get database URL from environment or use default
        database_url = os.getenv("DATABASE_URL", "sqlite:///professional_coach_memory.db")

        # Get OpenAI API key for memory agents
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            logger.warning("OpenAI API key not found. Memory intelligence features may be limited.")

        # Initialize Memori with both conscious and auto ingestion
        memori = Memori(
            database_connect=database_url,
            namespace="professional_coach",
            conscious_ingest=True,  # Enable working memory
            auto_ingest=True,       # Enable dynamic memory search
            openai_api_key=openai_api_key,
            verbose=False
        )

        # Enable the memory system
        memori.enable()

        logger.info(f"  Memory system initialized with database: {database_url}")
        return memori

    except Exception as e:
        logger.error(f" Failed to initialize memory system: {e}")
        raise


def create_coaching_agent(memori_instance):
    """Create the professional development coach agent"""

    if not STRANDS_AVAILABLE or not MEMORI_AVAILABLE:
        raise ImportError("Required dependencies not available")

    # Initialize coaching tools
    coaching_tools = ProfessionalCoachingTools(memori_instance)

    # Create memory search tool
    memory_tool = create_memory_tool(memori_instance)

    # Create a memory search wrapper tool for the agent
    @tool
    def search_memory(query: str) -> str:
        """Search the agent's memory for past conversations and information.

        Args:
            query: What to search for in memory (e.g., "career goals", "skill assessments", "learning progress")
        """
        try:
            if not query.strip():
                return "Please provide a search query"

            result = memory_tool.execute(query=query.strip())
            return str(result) if result else "No relevant memories found"

        except Exception as e:
            return f"Memory search error: {str(e)}"

    # Combine all tools
    all_tools = [
        search_memory,
        coaching_tools.set_career_goal,
        coaching_tools.assess_skill,
        coaching_tools.track_learning_progress,
        coaching_tools.recommend_resources
    ]

    model = LiteLLMModel(
        client_args={
            "api_key": os.getenv("NEBIUS_API_KEY"),
        },
        model_id="nebius/Qwen/Qwen3-Coder-480B-A35B-Instruct",
        params={
            "max_tokens": 1000,
            "temperature": 0.7,
        },
    )

    # Create the agent with coaching personality
    agent = Agent(
        model=model,
        tools=all_tools,
        name="Professional Development Coach",

    )

    return agent


def print_welcome_message():
    """Print welcome message and instructions"""
    print("\n" + "="*60)
    print("PROFESSIONAL DEVELOPMENT COACH")
    print("   Powered by Strands SDK + Memori Memory + LiteLLM")
    print("="*60)
    print("\n I'm your AI coach with persistent memory. I can help you:")
    print("   • Set and track career goals")
    print("   • Assess and develop your skills")
    print("   • Track learning progress")
    print("   • Get personalized resource recommendations")
    print("   • Remember our conversations across sessions")

    print("\n Available features:")
    print("   • Memory search: I remember our past conversations")
    print("   • Goal setting: Set SMART career objectives")
    print("   • Skill tracking: Record your current proficiency levels")
    print("   • Progress monitoring: Track courses, books, projects")
    print("   • Resource recommendations: Get personalized learning suggestions")

    print("\n Example questions:")
    print("   • 'Help me set a career goal to become a senior developer'")
    print("   • 'Assess my Python skills as intermediate level'")
    print("   • 'I completed the FastAPI course - update my progress'")
    print("   • 'Recommend resources for learning machine learning'")
    print("   • 'What do you remember about my career goals?'")

    print("\n Type 'quit', 'exit', or 'bye' to end our session")
    print("="*60 + "\n")


async def main():
    """Main function to run the professional development coach"""

    print("🚀 Initializing Professional Development Coach...")

    try:
        # Initialize memory system
        print(" Initializing memory system...")
        memori = initialize_memory_system()

        # Create coaching agent
        print(" Creating your professional coach...")
        coach = create_coaching_agent(memori)

        print(" Initialization complete!")

        # Print welcome message
        print_welcome_message()

        # Main conversation loop
        conversation_count = 0

        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()

                # Check for exit commands
                if user_input.lower() in ["quit", "exit", "bye", "goodbye"]:
                    print("\n Coach: Great session! I'll remember everything we discussed.")
                    print("Your progress and goals are saved for our next conversation.")
                    break

                if not user_input:
                    continue

                conversation_count += 1
                print(f"\n Coach (thinking... session #{conversation_count})")

                # Get response from the coach
                try:
                    result = await coach.invoke_async(user_input)
                    print(f"\n Coach: {result.message}")

                    # Record the conversation in memory for future sessions
                    memori.record_conversation(user_input=user_input, ai_output=str(result.message))

                except Exception as e:
                    print(f"\n Error during coaching session: {str(e)}")
                    print("Let's try that again...")
                    continue

                print("\n" + "-"*50)

            except KeyboardInterrupt:
                print("\n\n Coach: Session interrupted. Your progress is saved!")
                break

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                print(f"\n Unexpected error: {str(e)}")
                print("Let's continue our session...")
                continue

    except Exception as e:
        logger.error(f"Failed to initialize coach: {e}")
        print(f"\n Failed to start coaching session: {str(e)}")
        print("\nPlease check your configuration and try again.")
        return

    # Print session summary
    print(f"\n Session Summary:")
    print(f"   • Conversations: {conversation_count}")
    print(f"   • Memory database: professional_coach_memory.db")
    print(f"   • Namespace: professional_coach")
    print("\n All our conversations and your progress are saved!")
    print("Your coach will remember everything when you return. 🧠✨")


if __name__ == "__main__":
    import sys

    # Check if user wants to see demo
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_coaching_session()
        exit(0)

    # Example usage and testing
    print("Professional Development Coach with Strands SDK + Memori + LiteLLM")
    print("=" * 60)
    print("Run with --demo flag to see example interactions")
    print("=" * 60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n Goodbye! Your progress has been saved.")
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"\n Application error: {str(e)}")