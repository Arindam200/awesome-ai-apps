import os

import dspy
lm = dspy.LM(
    "nebius/moonshotai/Kimi-K2-Instruct",
    api_key=os.environ.get("NEBIUS_API_KEY"),
    api_base="https://api.studio.nebius.com/v1/",
)

dspy.configure(lm=lm)


def evaluate_math(expression: str):
    return dspy.PythonInterpreter({}).execute(expression)


def search_wikipedia(query: str):
    results = dspy.ColBERTv2(url="http://20.102.90.50:2017/wiki17_abstracts")(
        query, k=3
    )
    return [x["text"] for x in results]


react = dspy.ReAct("question -> answer: str", tools=[evaluate_math, search_wikipedia])

question = "What is 9362158 divided by the year of Messi’s first Ballon d’Or?"

pred = react(question=question)

print("Question:", question)
print("Answer:", pred.answer)