"""
Token usage tracking for Claude API calls.
"""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Pricing per 1M tokens (in USD)
PRICING = {
    # Claude 3.5 Sonnet
    "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0, "cached_input": 0.3},
    "anthropic.claude-3-5-sonnet-20240620:0": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet@20240620": {"input": 3.0, "output": 15.0},
    
    # Claude 3.5 Sonnet v2
    "claude-3-5-sonnet-20241022-v2": {"input": 3.0, "output": 15.0, "cached_input": 0.3},
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-v2@20241022": {"input": 3.0, "output": 15.0},
    
    # Claude 3.7 Sonnet
    "claude-3-7-sonnet-20250219": {"input": 5.0, "output": 25.0, "cached_input": 0.5},
    
    # Default fallback pricing if model not found
    "default": {"input": 5.0, "output": 25.0, "cached_input": 0.5}
}

# Path for token usage log
# Can be overridden with TOKEN_LOG_PATH environment variable
TOKEN_LOG_PATH = os.environ.get("TOKEN_LOG_PATH", Path.home() / ".anthropic" / "token_usage.json")
print(f"Token usage statistics will be logged to: {TOKEN_LOG_PATH}")

@dataclass
class TokenUsage:
    """Track token usage for a single API call."""
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float = 0.0
    
    def calculate_cost(self):
        """Calculate the cost of token usage."""
        if self.model in PRICING:
            pricing = PRICING[self.model]
        else:
            pricing = PRICING["default"]
            
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]
        
        cached_cost = 0
        if "cached_input" in pricing and self.cached_input_tokens > 0:
            cached_cost = (self.cached_input_tokens / 1_000_000) * pricing["cached_input"]
            
        self.cost_usd = input_cost + output_cost + cached_cost
        return self.cost_usd


class TokenTracker:
    """Track token usage across multiple API calls."""
    
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else Path(TOKEN_LOG_PATH)
        self.usage_records: List[TokenUsage] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start_time = datetime.now()
        self._load_existing_records()
    
    def _load_existing_records(self):
        """Load existing records from the log file if it exists."""
        if self.log_path.exists():
            try:
                with open(self.log_path, "r") as f:
                    data = json.load(f)
                    # Convert dict records to TokenUsage objects
                    for record in data.get("records", []):
                        self.usage_records.append(TokenUsage(**record))
            except (json.JSONDecodeError, FileNotFoundError):
                # Start with empty records if file is invalid or missing
                self.usage_records = []
        
        # Create directory if it doesn't exist
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def add_usage(self, usage: TokenUsage):
        """Add a new token usage record and update the log file."""
        usage.calculate_cost()
        self.usage_records.append(usage)
        self._write_to_file()
        
    def _write_to_file(self):
        """Write all records to the log file."""
        # Calculate session totals
        session_data = self.get_session_stats()
        
        data = {
            "session_id": self.session_id,
            "last_updated": datetime.now().isoformat(),
            "session_stats": session_data,
            "records": [asdict(record) for record in self.usage_records]
        }
        
        with open(self.log_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_session_stats(self) -> Dict:
        """Get statistics for the current session."""
        total_input = sum(rec.input_tokens for rec in self.usage_records)
        total_output = sum(rec.output_tokens for rec in self.usage_records)
        total_cached = sum(rec.cached_input_tokens for rec in self.usage_records)
        total_thinking = sum(rec.thinking_tokens for rec in self.usage_records)
        total_cost = sum(rec.cost_usd for rec in self.usage_records)
        
        # Calculate session duration
        now = datetime.now()
        session_duration = now - self.session_start_time
        duration_seconds = session_duration.total_seconds()
        
        # Format duration as HH:MM:SS
        hours, remainder = divmod(int(duration_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        formatted_duration = f"{hours:02}:{minutes:02}:{seconds:02}"
        
        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cached_input_tokens": total_cached,
            "total_thinking_tokens": total_thinking,
            "total_requests": len(self.usage_records),
            "total_cost_usd": total_cost,
            "session_start_time": self.session_start_time.isoformat(),
            "current_time": now.isoformat(),
            "session_duration_seconds": duration_seconds,
            "session_duration": formatted_duration,
        }


# Global token tracker instance
token_tracker = TokenTracker()

def get_token_log_path():
    """Helper function to get the token log path."""
    return TOKEN_LOG_PATH