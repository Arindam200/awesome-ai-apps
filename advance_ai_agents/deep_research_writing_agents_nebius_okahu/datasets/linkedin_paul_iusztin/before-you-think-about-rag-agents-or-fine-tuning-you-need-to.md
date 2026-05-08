Before you think about RAG, agents, or fine-tuning, you need to get one thing right:

Your data pipeline architecture.

It doesn't matter how fancy your algorithm is if your data is fragmented, inconsistent, or low quality.

So how do you do it right?

Here's how I did it while building my Second Brain AI assistant:

To make it scalable, the pipeline was split into two clear layers.

𝟭/ 𝗗𝗮𝘁𝗮 𝗰𝗼𝗹𝗹𝗲𝗰𝘁𝗶𝗼𝗻 𝗽𝗶𝗽𝗲𝗹𝗶𝗻𝗲

Raw data is extracted from Notion via API, enriched by crawling linked content, standardized into Markdown, and stored as JSON in S3.

This decouples ingestion from usage.

Think of S3 as a data lake: one place where raw unstructured knowledge lives, accessible to any downstream system.

𝟮/ 𝗘𝗧𝗟 𝗽𝗶𝗽𝗲𝗹𝗶𝗻𝗲 (𝗘𝘅𝘁𝗿𝗮𝗰𝘁, 𝗧𝗿𝗮𝗻𝘀𝗳𝗼𝗿𝗺, 𝗟𝗼𝗮𝗱)

Once data is in S3, we:

• Extract documents from storage
• Transform them by crawling, cleaning, and normalizing to Markdown
• Compute a quality score per document
• Load everything into a document database for consumption

Why did we standardize to Markdown?

It ensures downstream pipelines can treat all sources equally, whether the data came from Notion or the open web.

𝗤𝘂𝗮𝗹𝗶𝘁𝘆 𝘀𝗰𝗼𝗿𝗶𝗻𝗴 𝗶𝘀 𝗷𝘂𝘀𝘁 𝗮𝘀 𝗰𝗿𝗶𝘁𝗶𝗰𝗮𝗹...

AI systems obey a simple rule:

Garbage in, garbage out.

By attaching a quality score to each document, downstream systems can decide what’s good enough for RAG versus what’s suitable for fine-tuning.

One more important principle:

Decouple data from AI.

By snapshotting and versioning data between the data and AI layers, you can iterate on retrieval, agents, and models without constantly re-running ingestion.

This is how we keep production systems flexible.

If you want a hands-on walkthrough of how to architect data pipelines specifically for AI assistants...

This is covered in Lesson 2 of the open-source course Building Your Second Brain AI Assistant Using Agents, LLMs, and RAG.

Check it out here → https://lnkd.in/e_JM9rv4
