I was a true believer in clean architecture.

I honestly thought it would help me structure my Python AI projects.

This resulted in countless hours wasted obsessively dividing my projects into four folders:

• Domain
• Application
• Infrastructure
• Interface

It felt right.
But it was a complete nightmare to maintain.

It wasn’t until I realized that these layers should be virtual concepts that I finally cracked it.

Because Python doesn’t force structure on you.
It gives you freedom.

And that freedom is exactly why AI projects fall apart.

If you don’t impose some structure, you get spaghetti code.
If you impose too much structure, you get ceremony and friction.

Most advice pushes you to one extreme or the other.

Either rigid Clean Architecture, copied from Java, or tool-specific templates that lock you into a framework.

Neither worked for me.

What finally worked was treating clean architecture as a set of boundaries.

The domain became “pure business logic.”
The application became orchestration.
Infrastructure became swappable details.
Interfaces became replaceable entry points.

But none of that needed to be enforced dogmatically in folders.

Once I made that shift, things got simpler.

AI agents became reusable.
Workflows became easier to change.
Switching models or storage stopped rippling through the codebase.

If your Python AI project feels messy and fragile, or clean but painful to work in...

You’re probably applying the right ideas in the wrong way.

Btw, I wrote down the exact mental model and project structure that finally worked for me while building AI agents and workflows.

Sharing it here in case it helps someone else…

Link: https://lnkd.in/eGsU7ww3

P.S. If clean architecture ever made your Python project worse before it made it better, you’re not alone :)
