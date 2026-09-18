import os

from dotenv import load_dotenv
from mnemoverse import (
    MnemoClient,
    MnemoAuthError,
    MnemoRateLimitError,
    MnemoError,
)
from openai import OpenAI

DOMAIN = "project-assistant"
CONCEPTS = ["project-assistant"]


def create_clients():
    load_dotenv()

    mnemoverse_key = os.getenv("MNEMOVERSE_API_KEY")
    nebius_key = os.getenv("NEBIUS_API_KEY")

    if not mnemoverse_key:
        raise RuntimeError(
            "MNEMOVERSE_API_KEY is missing. "
            "Copy .env.example to .env and add your Mnemoverse API key."
        )

    if not nebius_key:
        raise RuntimeError(
            "NEBIUS_API_KEY is missing. "
            "Copy .env.example to .env and add your Nebius API key."
        )

    memory = MnemoClient(api_key=mnemoverse_key)

    llm = OpenAI(
        api_key=nebius_key,
        base_url="https://api.tokenfactory.nebius.com/v1",
    )

    return memory, llm


def generate_answer(llm, task, memories):
    context = "\n".join(f"- {item.content}" for item in memories)

    if not context:
        context = "(No relevant memories found.)"

    response = llm.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a project assistant. "
                    "Use recalled memories as reference material. "
                    "Do not blindly trust memories because they may be outdated. "
                    "Answer the user's request clearly and concisely."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"<recalled_memories>\n{context}\n"
                    f"</recalled_memories>\n\n"
                    f"Current task: {task}"
                ),
            },
        ],
        max_tokens=500,
    )

    return response.choices[0].message.content


def recall_memory(memory, task):
    response = memory.read(
        task,
        top_k=5,
        domain=DOMAIN,
    )

    print("\n🧠 RECALLED MEMORIES")
    print("=" * 60)

    if not response.items:
        print("(No relevant memories found.)")
    else:
        for item in response.items:
            print(f"- [{item.relevance:.2f}] {item.content}")

    return response


def store_memory(memory, task, answer):
    response = memory.write(
        content=f"Task: {task}\nAssistant answer: {answer[:2000]}",
        concepts=CONCEPTS,
        domain=DOMAIN,
    )

    print("\n💾 MEMORY STORED")
    print("=" * 60)
    print(f"Memory ID: {response.atom_id}")

    return response


def send_feedback(memory, recalled):
    if not recalled.items:
        return

    print("\nWas the recalled memory useful?")
    print("  y = helpful")
    print("  n = misleading")
    print("  s = skip")

    choice = input("> ").strip().lower()

    if choice not in {"y", "n"}:
        print("⏭️ Feedback skipped.")
        return

    outcome = 1.0 if choice == "y" else -1.0

    feedback = memory.feedback(
        atom_ids=[item.atom_id for item in recalled.items],
        outcome=outcome,
        query_concepts=recalled.query_concepts,
        concepts=CONCEPTS,
        domain=DOMAIN,
    )

    print("\n📈 MEMORY FEEDBACK")
    print("=" * 60)
    print(f"Outcome: {outcome:+.1f}")
    print(f"Updated memories: {feedback.updated_count}")
    print(f"Average valence: {feedback.avg_valence:.2f}")


def run(task):
    try:
        memory, llm = create_clients()

        recalled = recall_memory(memory, task)
        answer = generate_answer(
            llm,
            task,
            recalled.items,
        )

        print("\n🤖 ASSISTANT")
        print("=" * 60)
        print(answer)

        store_memory(memory, task, answer)

        send_feedback(memory, recalled)

        return answer

    except RuntimeError as error:
        print(f"❌ Configuration error: {error}")
    except MnemoAuthError:
        print("❌ Invalid Mnemoverse API key.")
    except MnemoRateLimitError as error:
        print("❌ Mnemoverse rate limit reached. " f"Retry after {error.retry_after}s.")
    except MnemoError as error:
        print(f"❌ Mnemoverse error: {error}")


def main():
    print("🧠 Mnemoverse Memory Agent")
    print("=" * 60)
    print("Persistent project-assistant memory with feedback.\n")

    task = input("What should the project assistant help with?\n> ").strip()

    if not task:
        print("❌ Please enter a task.")
        return

    run(task)


if __name__ == "__main__":
    main()
