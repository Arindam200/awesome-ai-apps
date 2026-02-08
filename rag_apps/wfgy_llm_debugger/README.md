# 🧪 WFGY 16 Problem Map · RAG Failure Clinic (Nebius TXT runner)

A practical RAG failure clinic built on top of **WFGY Problem Map 1.0**.  
You run a curated list of **16 reproducible failure modes** against any Nebius-hosted LLM and see exactly where your RAG pipeline breaks.

Instead of only asking “does my chatbot answer something”, this clinic is designed to surface:

- hallucination & chunk drift (Problem Map No.1)  
- interpretation collapse when chunks are correct but logic is wrong (No.2)  
- long reasoning chain drift (No.3)  
- bluffing / overconfident answers with no evidence (No.4)  
- semantic vs embedding mismatch in your vector store (No.5)  
- …and the rest of the 16 canonical failure modes you defined in WFGY.

> The full map, stories, and fixes are in the open source WFGY repo (MIT):  
> https://github.com/onestardao/WFGY/tree/main/ProblemMap#readme

This example only gives you a **Nebius TXT runner** so you can quickly probe those 16 modes with any Nebius Token Factory model.
