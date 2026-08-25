"""OpenAI LLM client for transaction analysis and fraud detection."""

import os
import logging
from typing import Dict, Optional, List
from openai import OpenAI
from utils.config import config

logger = logging.getLogger(__name__)

class LLMClient:
    """Client for LLM inference using OpenAI."""
    
    def __init__(self):
        """Initialize OpenAI LLM client."""
        self._client = None
        self.model = config.OPENAI_MODEL
        self.api_key = config.OPENAI_API_KEY
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client (for Temporal compatibility)."""
        if self._client is None and self.api_key:
            try:
                self._client = OpenAI(api_key=self.api_key)
                logger.info(f"Initialized OpenAI LLM client with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self._client = None
        return self._client
    
    def analyze_transaction(self, transaction_data: Dict, context: Optional[Dict] = None) -> Dict:
        """
        Analyze a transaction for fraud detection.
        
        Args:
            transaction_data: Transaction details
            context: Additional context (similar transactions, risk flags, etc.)
            
        Returns:
            Dictionary with decision, confidence, reasoning, and risk factors
        """
        if not self.client:
            logger.warning("OpenAI client not available. Returning mock analysis.")
            return self._mock_analysis()
        
        # Build prompt for transaction analysis
        prompt = self._build_analysis_prompt(transaction_data, context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial fraud detection expert. Analyze transactions for potential fraud, money laundering, or compliance violations. Provide clear reasoning for your decisions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=1000
            )
            
            # Parse response
            analysis_text = response.choices[0].message.content
            return self._parse_analysis_response(analysis_text, transaction_data)
            
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")
            return self._mock_analysis()
    
    def _build_analysis_prompt(self, transaction_data: Dict, context: Optional[Dict] = None) -> str:
        """Build the prompt for transaction analysis."""
        prompt_parts = [
            "Analyze the following financial transaction for fraud risk:",
            "",
            f"Transaction Type: {transaction_data.get('transaction_type', 'N/A')}",
            f"Amount: ${transaction_data.get('amount', 0):,.2f} {transaction_data.get('currency', 'USD')}",
            f"Sender: {transaction_data.get('sender', {}).get('name', 'N/A')} ({transaction_data.get('sender', {}).get('country', 'N/A')})",
            f"Recipient: {transaction_data.get('recipient', {}).get('name', 'N/A')} ({transaction_data.get('recipient', {}).get('country', 'N/A')})",
            f"Description: {transaction_data.get('description', 'N/A')}",
        ]
        
        if transaction_data.get('risk_flags'):
            prompt_parts.append(f"Risk Flags: {', '.join(transaction_data['risk_flags'])}")
        
        if context:
            if context.get('similar_transactions'):
                prompt_parts.append(f"\nFound {len(context['similar_transactions'])} similar historical transactions.")
            if context.get('risk_score'):
                prompt_parts.append(f"Preliminary Risk Score: {context['risk_score']}")
        
        prompt_parts.extend([
            "",
            "Provide your analysis in the following format:",
            "DECISION: [approve/reject/escalate]",
            "CONFIDENCE: [0-100]",
            "REASONING: [detailed explanation]",
            "RISK_FACTORS: [comma-separated list of risk factors]"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_analysis_response(self, response_text: str, transaction_data: Dict) -> Dict:
        """Parse the LLM response into structured format."""
        # Default values
        decision = "escalate"
        confidence = 50
        reasoning = response_text
        risk_factors = []
        
        # Try to extract structured information
        lines = response_text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("DECISION:"):
                decision_text = line.split(":", 1)[1].strip().lower()
                if "approve" in decision_text:
                    decision = "approve"
                elif "reject" in decision_text:
                    decision = "reject"
                elif "escalate" in decision_text:
                    decision = "escalate"
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = int(line.split(":", 1)[1].strip())
                    confidence = max(0, min(100, confidence))
                except:
                    pass
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("RISK_FACTORS:"):
                factors_text = line.split(":", 1)[1].strip()
                risk_factors = [f.strip() for f in factors_text.split(",")]
        
        # If no structured format found, try to infer from text
        if decision == "escalate" and not any(line.startswith("DECISION:") for line in lines):
            response_lower = response_text.lower()
            if any(word in response_lower for word in ["fraud", "suspicious", "high risk", "reject"]):
                decision = "reject"
                confidence = max(confidence, 70)
            elif any(word in response_lower for word in ["low risk", "legitimate", "approve", "safe"]):
                decision = "approve"
                confidence = max(confidence, 80)
        
        return {
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "risk_factors": risk_factors if risk_factors else ["general_review"]
        }
    
    def _mock_analysis(self) -> Dict:
        """Return mock analysis when API is unavailable."""
        return {
            "decision": "escalate",
            "confidence": 50,
            "reasoning": "Mock analysis - OpenAI API not available",
            "risk_factors": ["api_unavailable"]
        }
    
    def health_check(self) -> Dict:
        """Check the health status of the LLM service."""
        return {
            "available": self.client is not None,
            "model": self.model,
            "provider": "openai"
        }

# Global instance
llm_client = LLMClient()

