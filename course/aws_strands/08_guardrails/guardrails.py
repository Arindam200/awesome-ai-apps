import re
import datetime
from typing import Tuple, Dict, List
from strands.hooks import HookProvider, HookRegistry
from strands.hooks import BeforeInvocationEvent, AfterInvocationEvent


class SafetyGuardrails:
    """Implements safety guardrails for AI systems."""

    def __init__(self):
        self.safety_log = []

        # Define safety rules
        self.safety_rules = {
            "prohibited_keywords": [
                "harmful",
                "dangerous",
                "illegal",
                "violence",
                "hate",
                "discrimination",
                "explicit",
                "inappropriate",
                "bomb",
                "weapon",
                "suicide",
                "self-harm",
                "terrorist",
                "attack",
            ],
            "jailbreak_patterns": [
                r"ignore\s+previous\s+instructions",
                r"forget\s+everything",
                r"you\s+are\s+now",
                r"pretend\s+to\s+be",
                r"act\s+as\s+if",
                r"roleplay\s+as",
                r"system\s+prompt",
                r"developer\s+mode",
            ],
            "sensitive_topics": [
                "personal information",
                "financial data",
                "medical records",
                "legal advice",
                "professional diagnosis",
                "ssn",
                "credit card",
                "password",
                "private key",
            ],
        }

    def validate_input(self, user_input: str) -> Tuple[bool, str, Dict]:
        """Validate user input against safety rules."""
        validation_result = {"is_safe": True, "violations": [], "risk_level": "low"}

        # Check for prohibited keywords
        for keyword in self.safety_rules["prohibited_keywords"]:
            if keyword.lower() in user_input.lower():
                validation_result["violations"].append(f"Prohibited keyword: {keyword}")
                validation_result["is_safe"] = False

        # Check for jailbreak patterns
        for pattern in self.safety_rules["jailbreak_patterns"]:
            if re.search(pattern, user_input, re.IGNORECASE):
                validation_result["violations"].append(
                    f"Jailbreak pattern detected: {pattern}"
                )
                validation_result["is_safe"] = False

        # Check for sensitive topics
        for topic in self.safety_rules["sensitive_topics"]:
            if topic.lower() in user_input.lower():
                validation_result["violations"].append(f"Sensitive topic: {topic}")
                validation_result["risk_level"] = "medium"

        # Determine risk level
        if validation_result["violations"]:
            if len(validation_result["violations"]) > 2:
                validation_result["risk_level"] = "high"
            elif validation_result["risk_level"] != "medium":
                validation_result["risk_level"] = "medium"

        # Log validation result
        self.safety_log.append(
            {
                "input": user_input,
                "result": validation_result,
                "timestamp": self._get_timestamp(),
            }
        )

        return (
            validation_result["is_safe"],
            validation_result["risk_level"],
            validation_result,
        )

    def check_content_safety(self, content: str) -> Tuple[bool, str]:
        """Check content safety using LLM."""
        prompt = f"""
        Review this content for safety and appropriateness:
        
        Content: {content}
        
        Check for:
        1. Harmful or dangerous information
        2. Inappropriate content
        3. Misleading information
        4. Privacy violations
        
        Respond with:
        SAFE: [true/false]
        REASON: [brief explanation]
        """

        response = self.llm.generate(prompt).content

        # Parse response
        is_safe = "true" in response.lower()
        reason = "Content safety check completed"

        if "REASON:" in response:
            reason = response.split("REASON:")[1].strip()

        return is_safe, reason

    def sanitize_input(self, user_input: str) -> str:
        """Sanitize user input by removing or replacing problematic content."""
        sanitized = user_input

        # Remove prohibited keywords
        for keyword in self.safety_rules["prohibited_keywords"]:
            sanitized = re.sub(keyword, "[REDACTED]", sanitized, flags=re.IGNORECASE)

        # Remove jailbreak patterns
        for pattern in self.safety_rules["jailbreak_patterns"]:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

        return sanitized

    def generate_safe_response(self, user_input: str) -> str:
        """Generate a safe response to user input."""
        # First validate input
        is_safe, risk_level, validation = self.validate_input(user_input)

        if not is_safe:
            return self._generate_safety_message(validation["violations"])

        # Generate response
        prompt = f"""
        Provide a helpful and safe response to this user input:
        {user_input}
        
        Guidelines:
        - Be helpful and informative
        - Avoid harmful or inappropriate content
        - Respect privacy and safety
        - Provide accurate information
        """

        response = self.llm.generate(prompt).content

        # Check response safety
        response_safe, reason = self.check_content_safety(response)

        if not response_safe:
            return "I apologize, but I cannot provide a response to that request for safety reasons."

        return response

    def _generate_safety_message(self, violations: List[str]) -> str:
        """Generate a safety message for violations."""
        if not violations:
            return "I cannot process this request."

        message = (
            "I cannot process this request due to the following safety concerns:\n"
        )
        for violation in violations:
            message += f"- {violation}\n"
        message += "\nPlease rephrase your request in a safe and appropriate manner."

        return message

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        import datetime

        return datetime.datetime.now().isoformat()

    def get_safety_log(self) -> List[Dict]:
        """Get safety log."""
        return self.safety_log

    def get_safety_statistics(self) -> Dict:
        """Get safety statistics."""
        total_requests = len(self.safety_log)
        unsafe_requests = sum(
            1 for log in self.safety_log if not log["result"]["is_safe"]
        )
        high_risk_requests = sum(
            1 for log in self.safety_log if log["result"]["risk_level"] == "high"
        )

        return {
            "total_requests": total_requests,
            "unsafe_requests": unsafe_requests,
            "high_risk_requests": high_risk_requests,
            "safety_rate": (total_requests - unsafe_requests)
            / max(1, total_requests)
            * 100,
        }


class GuardrailsHook(HookProvider):
    """Hook implementation for safety guardrails using AWS Strands hooks."""

    def __init__(self, safety_guardrails: SafetyGuardrails = None):
        """
        Initialize the guardrails hook.

        Args:
            safety_guardrails: Optional SafetyGuardrails instance. If None, creates a new one.
        """
        self.guardrails = safety_guardrails or SafetyGuardrails()
        self.blocked_requests = 0
        self.allowed_requests = 0

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register hooks for input and output validation."""
        registry.add_callback(BeforeInvocationEvent, self.validate_input)
        registry.add_callback(AfterInvocationEvent, self.validate_output)

    def validate_input(self, event: BeforeInvocationEvent) -> None:
        """
        Validate user input before processing.

        Args:
            event: BeforeInvocationEvent containing the user input
        """
        # Extract user input from the event
        user_input = self._extract_user_input(event)

        if not user_input:
            return

        print(f"\n🔒 GUARDRAILS: Validating input...")
        print(f"Input: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")

        # Validate input using safety guardrails
        is_safe, risk_level, validation = self.guardrails.validate_input(user_input)

        if not is_safe:
            print(f"❌ BLOCKED: Input failed safety validation")
            print(f"Risk Level: {risk_level.upper()}")
            print(f"Violations: {', '.join(validation['violations'])}")

            # Block the request by raising an exception
            self.blocked_requests += 1
            raise ValueError(
                f"Request blocked by safety guardrails: {', '.join(validation['violations'])}"
            )

        print(f"✅ ALLOWED: Input passed safety validation (Risk: {risk_level})")
        self.allowed_requests += 1

    def validate_output(self, event: AfterInvocationEvent) -> None:
        """
        Validate agent output after processing.

        Args:
            event: AfterInvocationEvent containing the agent response
        """
        # Extract agent response from the event
        agent_response = self._extract_agent_response(event)

        if not agent_response:
            return

        print(f"\n🔒 GUARDRAILS: Validating output...")
        print(
            f"Output: {agent_response[:100]}{'...' if len(agent_response) > 100 else ''}"
        )

        # Validate output using safety guardrails
        is_safe, risk_level, validation = self.guardrails.validate_input(agent_response)

        if not is_safe:
            print(f"⚠️  WARNING: Output contains potentially unsafe content")
            print(f"Risk Level: {risk_level.upper()}")
            print(f"Violations: {', '.join(validation['violations'])}")

            # Log the violation but don't block (as output is already generated)
            self.guardrails.safety_log.append(
                {
                    "input": agent_response,
                    "result": validation,
                    "timestamp": self.guardrails._get_timestamp(),
                    "type": "output_validation",
                }
            )
        else:
            print(f"✅ SAFE: Output passed safety validation (Risk: {risk_level})")

    def _extract_user_input(self, event: BeforeInvocationEvent) -> str:
        """Extract user input from BeforeInvocationEvent."""
        try:
            # Try to get the user input from the event
            if hasattr(event, "messages") and event.messages:
                for message in event.messages:
                    if hasattr(message, "content") and message.content:
                        if isinstance(message.content, str):
                            return message.content
                        elif isinstance(message.content, list):
                            for content_item in message.content:
                                if hasattr(content_item, "text"):
                                    return content_item.text
            return ""
        except Exception:
            return ""

    def _extract_agent_response(self, event: AfterInvocationEvent) -> str:
        """Extract agent response from AfterInvocationEvent."""
        try:
            # Try to get the agent response from the event
            if hasattr(event, "response") and event.response:
                if hasattr(event.response, "content") and event.response.content:
                    if isinstance(event.response.content, str):
                        return event.response.content
                    elif isinstance(event.response.content, list):
                        for content_item in event.response.content:
                            if hasattr(content_item, "text"):
                                return content_item.text
            return ""
        except Exception:
            return ""

    def get_safety_statistics(self) -> Dict:
        """Get comprehensive safety statistics."""
        base_stats = self.guardrails.get_safety_statistics()
        base_stats.update(
            {
                "blocked_requests": self.blocked_requests,
                "allowed_requests": self.allowed_requests,
                "total_processed": self.blocked_requests + self.allowed_requests,
            }
        )
        return base_stats

    def print_safety_report(self) -> None:
        """Print a comprehensive safety report."""
        stats = self.get_safety_statistics()

        print("\n" + "=" * 60)
        print("🔒 SAFETY GUARDRAILS REPORT")
        print("=" * 60)
        print(f"Total Requests Processed: {stats['total_processed']}")
        print(f"Blocked Requests: {stats['blocked_requests']}")
        print(f"Allowed Requests: {stats['allowed_requests']}")
        print(f"Safety Rate: {stats['safety_rate']:.1f}%")
        print(f"High Risk Requests: {stats['high_risk_requests']}")
        print("=" * 60)


class GuardedAgent:
    """Wrapper around an Agent that adds safety guardrails."""

    def __init__(self, agent, guardrails_hook: GuardrailsHook):
        """
        Initialize the guarded agent.

        Args:
            agent: The underlying Agent instance
            guardrails_hook: The GuardrailsHook instance for validation
        """
        self.agent = agent
        self.guardrails_hook = guardrails_hook

    def __call__(self, user_input: str):
        """
        Call the agent with input validation.

        Args:
            user_input: The user input to process

        Returns:
            Agent response if input is safe

        Raises:
            ValueError: If input fails safety validation
        """
        # Validate input first
        if not self.guardrails_hook.validate_input_manually(user_input):
            raise ValueError("Request blocked by safety guardrails")

        # If input is safe, proceed with agent call
        return self.agent(user_input)

    def __getattr__(self, name):
        """Delegate other attributes to the underlying agent."""
        return getattr(self.agent, name)
