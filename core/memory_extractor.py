"""
APRIL Memory Extractor

Extracts structured knowledge from conversations using LLM.
"""

import json
from typing import List, Dict, Optional


class MemoryExtractor:
    """
    Extracts structured memories from conversations
    
    Uses LLM to analyze conversation turns and extract:
    - Facts learned
    - Decisions made
    - Solutions provided
    - User preferences
    """
    
    EXTRACTION_PROMPT = """Analyze the following conversation and extract structured memories.

Conversation:
{conversation}

Extract the following types of information:
1. **Facts**: Objective information learned (e.g., "User prefers VS Code editor")
2. **Decisions**: Choices made during conversation (e.g., "Decided to use PostgreSQL database")
3. **Solutions**: Problems solved or approaches identified (e.g., "Fixed bug by increasing timeout to 60s")
4. **Preferences**: User preferences detected (e.g., "User wants local-first approach")

For each extraction, provide:
- type: "fact", "decision", "solution", or "preference"
- content: The extracted information (as a dictionary with "text" key)
- confidence: 0.0 to 1.0 (how certain is this extraction)
- tags: List of relevant tags (e.g., ["configuration", "database"])

Return a JSON object with "extractions" array:
{{
  "extractions": [
    {{
      "type": "fact",
      "content": {{"text": "..."}},
      "confidence": 0.9,
      "tags": ["tag1", "tag2"]
    }}
  ]
}}

If nothing worth remembering, return:
{{"extractions": []}}

Only return valid JSON. No explanation."""

    def __init__(self, model: str = "gemma4:31b-cloud"):
        """
        Initialize extractor
        
        Args:
            model: Model to use for extraction
        """
        self.model = model
        self._client = None
    
    @property
    def client(self):
        """Lazy load OpenAI client"""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key="test",
                base_url="http://localhost:11434/v1"
            )
        return self._client
    
    def format_conversation(self, messages: List[Dict]) -> str:
        """
        Format messages for extraction prompt
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Formatted conversation string
        """
        lines = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            lines.append(f"{role.capitalize()}: {content}")
        
        return "\n".join(lines)
    
    def extract(self, messages: List[Dict], client: "OpenAI" = None, fallback_mode: bool = True) -> List[Dict]:
        """
        Extract memories from conversation
        
        Args:
            messages: List of message dictionaries
            client: OpenAI client instance (optional, uses lazy loaded if not provided)
            fallback_mode: If True, return empty list on error rather than raising
            
        Returns:
            List of extracted memories
        """
        if not messages:
            return []
        
        # Format conversation
        conversation_text = self.format_conversation(messages)
        
        # Build prompt
        prompt = self.EXTRACTION_PROMPT.format(conversation=conversation_text)
        
        # Get OpenAI client
        if client is None:
            try:
                client = self.client
            except Exception:
                if fallback_mode:
                    return []
                raise
        
        # Call LLM for extraction
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            extractions = result.get('extractions', [])
            
            # Validate extractions
            validated = []
            for ext in extractions:
                if self._validate_extraction(ext):
                    validated.append(ext)
            
            return validated
            
        except json.JSONDecodeError as e:
            if fallback_mode:
                print(f"JSON parse error: {e}")
                print(f"Response was: {result_text}")
                return []
            raise
        except Exception as e:
            if fallback_mode:
                print(f"Extraction error: {e}")
                return []
            raise
    
    def _validate_extraction(self, extraction: Dict) -> bool:
        """
        Validate extraction structure
        
        Args:
            extraction: Extraction dictionary
            
        Returns:
            True if valid
        """
        required_fields = ['type', 'content', 'confidence', 'tags']
        
        if not all(field in extraction for field in required_fields):
            return False
        
        if extraction['type'] not in ['fact', 'decision', 'solution', 'preference']:
            return False
        
        if not isinstance(extraction['confidence'], (int, float)):
            return False
        
        if not (0 <= extraction['confidence'] <= 1):
            return False
        
        if not isinstance(extraction['tags'], list):
            return False
        
        return True
    
    def extract_incremental(self, old_messages: List[Dict], new_messages: List[Dict], client: "OpenAI" = None) -> List[Dict]:
        """
        Extract only from new messages, using old for context
        
        Args:
            old_messages: Previously processed messages
            new_messages: New unprocessed messages
            client: OpenAI client instance
            
        Returns:
            List of extracted memories
        """
        # For now, extract from all messages
        # Future: More sophisticated incremental extraction
        all_messages = old_messages + new_messages
        return self.extract(all_messages, client)


# Example usage
if __name__ == "__main__":
    # Test extraction
    extractor = MemoryExtractor()
    
    test_messages = [
        {"role": "user", "content": "Change the model to gemma4:31b-cloud"},
        {"role": "assistant", "content": "I've updated the configuration to use gemma4:31b-cloud model."}
    ]
    
    memories = extractor.extract(test_messages)
    
    print("Extracted memories:")
    for memory in memories:
        print(json.dumps(memory, indent=2))
