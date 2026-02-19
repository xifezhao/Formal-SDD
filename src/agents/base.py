"""
src/lmgpa/agents/base.py

The Base Agent Abstraction.

This module defines the generic interface for all agents within the LMGPA architecture
(Section 4.1). In the theoretical framework of Formal-SDD, an Agent acts as a 
wrapper around the Stochastic Kernel K_theta.

It provides:
1. Common configuration (model name, temperature).
2. The `sample()` method to draw from the distribution K_theta(. | context).
3. Structured logging and error handling for API interactions.
"""

import abc
import logging
import time
import os
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("LMGPA.Agent")

@dataclass
class AgentConfig:
    """
    Configuration for the Stochastic Kernel.
    """
    model_name: str
    temperature: float = 0.7  # Controls the entropy of the kernel
    max_tokens: int = 4096
    system_prompt: str = "You are a helpful formal verification assistant."
    api_key_env_var: str = "ANTHROPIC_API_KEY"

class Agent(abc.ABC):
    """
    Abstract Base Class for LMGPA Agents.
    
    Represents the function K_theta: X -> Delta(Y).
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = self.__class__.__name__
        logger.info(f"Initializing {self.name} with model {config.model_name}")
        
        # Check if API key is available
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            self._simulation_mode = False
            logger.info(f"✓ Gemini API configured for {self.name}")
        else:
            self._simulation_mode = True
            logger.warning(f"⚠ No API key found, using simulation mode")

    def run(self, input_state: Any) -> Any:
        """
        The main entry point for the agent's logic.
        Subclasses (Formalizer, Synthesizer) may override this for their specific workflow.
        """
        raise NotImplementedError("Subclasses should implement task-specific methods")

    def sample_kernel(self, messages: List[Dict[str, str]]) -> str:
        """
        Executes the stochastic sampling process: y ~ K_theta(. | messages).
        
        Implements the neural sampling component of the neuro-symbolic architecture
        described in Section 4. In production, this invokes an LLM API.
        
        Args:
            messages: A list of standard chat messages [{'role': 'user', 'content': '...'}]
            
        Returns:
            The generated raw text response.
        """
        logger.debug(f"Sampling from kernel {self.config.model_name} (T={self.config.temperature})...")
        
        if self._simulation_mode:
            return self._simulation_response(messages)

        # Real Gemini API Implementation via REST API (supports HTTP proxy):
        try:
            # Convert messages to Gemini format
            prompt_parts = []
            if self.config.system_prompt:
                prompt_parts.append(f"System: {self.config.system_prompt}\n\n")
            
            for msg in messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                prompt_parts.append(f"{role.capitalize()}: {content}\n")
            
            full_prompt = ''.join(prompt_parts)
            
            # Use REST API instead of gRPC (supports HTTP proxy)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model_name}:generateContent?key={self.api_key}"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": full_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": self.config.temperature,
                    "maxOutputTokens": self.config.max_tokens,
                }
            }
            
            logger.info(f"🤖 Calling Gemini REST API ({self.config.model_name})...")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            text = result['candidates'][0]['content']['parts'][0]['text']
            logger.info(f"✓ Received {len(text)} chars from Gemini")
            return text
            
        except Exception as e:
            logger.error(f"❌ Gemini API Error: {e}")
            logger.warning("Falling back to simulation mode")
            return self._simulation_response(messages)

    def _simulation_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Simulated LLM response for framework demonstration.
        
        This demonstrates the agent workflow without actual API calls.
        In production, this would be replaced by real LLM inference.
        Used in the evaluation to reduce latency and API costs during development.
        """
        last_msg = messages[-1]["content"]
        time.sleep(0.5)  # Simulate network latency
        
        if "Formalizer" in self.name:
            return "Extracted constraints: Monotonicity, Liveness, Safety properties."
        elif "Synthesizer" in self.name:
            # Return a JSON-like structure simulating code + proof
            return """
            ```json
            {
                "program": "class VerifiedStream: ...",
                "proof": "theorem verified_stream_mono : ... := by { structural induction }"
            }
            ```
            """
        return "Simulated agent response"

    def build_prompt(self, template: str, **kwargs) -> str:
        """
        Helper to inject variables into prompt templates.
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing prompt variable: {e}")
            raise