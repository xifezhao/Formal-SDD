"""
src/agents/formalizer.py

The Formalizer Agent (I -> S_tr).

This module implements the transformation from Natural Language Intent to 
Behavioral Trace Specifications.
"""

import logging
import re
import json
from typing import List, Dict, Any

from src.lmgpa.state_manager import TraceSpec
from src.agents.base import Agent, AgentConfig

logger = logging.getLogger("LMGPA.Formalizer")


class FormalizerAgent(Agent):
    """Formalizer Agent - Translates natural language to formal specs"""
    
    def formalize(self, requirements: str) -> str:
        """Convert natural language requirements to formal specification"""
        prompt = f"""
You are a formal specification expert.
Given the following requirements, extract the key formal properties:

Requirements:
{requirements}

Please list:
1. Safety properties (things that must always be true)
2. Liveness properties (things that must eventually happen)  
3. Key state variables
4. Logical constraints

Provide a structured JSON response.
"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self.sample_kernel(messages)
        
        # Try to extract JSON, otherwise return raw response
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                spec_dict = json.loads(json_match.group(0))
                return json.dumps(spec_dict, indent=2)
        except:
            pass
            
        return response
