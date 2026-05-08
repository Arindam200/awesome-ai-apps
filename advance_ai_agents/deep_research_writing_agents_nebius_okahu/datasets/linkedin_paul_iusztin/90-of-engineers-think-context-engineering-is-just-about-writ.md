90% of engineers think context engineering is just about writing better prompts.

Newsflash: It's not.

Prompt engineering is only one part of it.

Context engineering is about deciding what information the model sees (and when).

Think of it as curing the model's short-term memory...

You only have a few thousand tokens to work with.

So every piece of context you include has to earn its spot.

Here's what makes up that context:

𝟭/ 𝗦𝘆𝘀𝘁𝗲𝗺 𝗣𝗿𝗼𝗺𝗽𝘁 (𝗣𝗿𝗼𝗰𝗲𝗱𝘂𝗿𝗮𝗹 𝗠𝗲𝗺𝗼𝗿𝘆)

This defines how your agent behaves → tone, rules, and reasoning style.

It’s the foundation of its “personality” and procedural logic.

𝟮/ 𝗠𝗲𝘀𝘀𝗮𝗴𝗲 𝗛𝗶𝘀𝘁𝗼𝗿𝘆 (𝗪𝗼𝗿𝗸𝗶𝗻𝗴 𝗠𝗲𝗺𝗼𝗿𝘆)

The recent back-and-forth between you and the model.

This includes user inputs, the agent’s reasoning steps, tool outputs → everything the model needs to stay coherent in a conversation.

𝟯. 𝗨𝘀𝗲𝗿 𝗣𝗿𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲𝘀 & 𝗣𝗮𝘀𝘁 𝗜𝗻𝘁𝗲𝗿𝗮𝗰𝘁𝗶𝗼𝗻𝘀 (𝗘𝗽𝗶𝘀𝗼𝗱𝗶𝗰 𝗠𝗲𝗺𝗼𝗿𝘆)

Facts about the user or system that personalize responses.

Think of this as long-term memory stored in a vector or graph database.

𝟰. 𝗥𝗲𝘁𝗿𝗶𝗲𝘃𝗲𝗱 𝗜𝗻𝗳𝗼𝗿𝗺𝗮𝘁𝗶𝗼𝗻 (𝗦𝗲𝗺𝗮𝗻𝘁𝗶𝗰 𝗠𝗲𝗺𝗼𝗿𝘆)

Relevant documents or data fetched via RAG pipelines or APIs.

This is where your factual grounding lives.

𝟱. 𝗧𝗼𝗼𝗹 & 𝗦𝘁𝗿𝘂𝗰𝘁𝘂𝗿𝗲𝗱 𝗢𝘂𝘁𝗽𝘂𝘁 𝗦𝗰𝗵𝗲𝗺𝗮𝘀 (𝗣𝗿𝗼𝗰𝗲𝗱𝘂𝗿𝗮𝗹 𝗠𝗲𝗺𝗼𝗿𝘆)

Definitions for what tools the agent can use and what outputs it should return.

𝗪𝗵𝗲𝗻 𝘆𝗼𝘂 𝗮𝘀𝘀𝗲𝗺𝗯𝗹𝗲 𝗮𝗹𝗹 𝗼𝗳 𝘁𝗵𝗲𝘀𝗲 𝘁𝗼𝗴𝗲𝘁𝗵𝗲𝗿, 𝘆𝗼𝘂 𝗴𝗲𝘁 𝘁𝗵𝗲 𝗰𝗼𝗻𝘁𝗲𝘅𝘁 𝗽𝗮𝘆𝗹𝗼𝗮𝗱.

It’s the short-term memory subset that the LLM actually sees during inference.

It’s the curated slice of memory that powers every LLM call.

And just like RAM in a computer, it’s dynamic.

Every request rewrites it → adding new information, forgetting irrelevant details, and retrieving just what’s needed.

That’s the real art of context engineering:

Fitting just enough information to make the model smart without overloading it with noise.

So next time you see someone talk about prompt engineering...

Remember → prompts are just one piece of a much larger system.

P.S. I wrote a full article diving deeper into context engineering in Decoding AI Magazine. Check it out here → https://lnkd.in/dTYs6ezm
