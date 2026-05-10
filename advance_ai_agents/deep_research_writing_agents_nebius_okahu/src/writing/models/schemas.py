"""Pydantic models for writing operations."""

from pydantic import BaseModel, Field


class Profile(BaseModel):
    """A single writing profile."""

    name: str = Field(description="Profile type identifier")
    content: str = Field(description="Full markdown content of the profile")


class Profiles(BaseModel):
    """Container for all writing profiles."""

    structure: Profile = Field(description="Post structure rules")
    terminology: Profile = Field(description="Word choice and style rules")
    character: Profile = Field(description="Voice, persona, and tone rules")
    branding: Profile = Field(description="Visual identity and design rules")


class Post(BaseModel):
    """A LinkedIn post."""

    content: str = Field(description="The full text of the LinkedIn post")


class Review(BaseModel):
    """A single review item identifying a constraint violation."""

    profile: str = Field(
        description="Which constraint was violated (e.g., 'structure_profile', 'guideline')"
    )
    location: str = Field(
        description="Where in the post (e.g., 'Hook', 'Paragraph 3', 'CTA')"
    )
    comment: str = Field(description="What is wrong and how it deviates from the rules")


class PostReviews(BaseModel):
    """Structured output from the post reviewer."""

    reviews: list[Review] = Field(
        default_factory=list, description="List of review items"
    )


class GeneratePostResult(BaseModel):
    """Result of the generate post pipeline, including all intermediate versions."""

    post: Post = Field(description="The final post after all iterations")
    versions: list[Post] = Field(
        default_factory=list,
        description="All intermediate post versions (initial + each edit)",
    )
    reviews: list[PostReviews] = Field(
        default_factory=list,
        description="Review results from each iteration",
    )
