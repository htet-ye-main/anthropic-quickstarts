"""
Token usage tracking for Claude API calls.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Pricing per 1M tokens (in USD)
PRICING = {
    # Claude 3.5 Sonnet
    "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0, "cached_input": 0.3},
    "anthropic.claude-3-5-sonnet-20240620:0": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet@20240620": {"input": 3.0, "output": 15.0},
    # Claude 3.5 Sonnet v2
    "claude-3-5-sonnet-20241022-v2": {
        "input": 3.0,
        "output": 15.0,
        "cached_input": 0.3,
    },
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet-v2@20241022": {"input": 3.0, "output": 15.0},
    # Claude 3.7 Sonnet
    "claude-3-7-sonnet-20250219": {"input": 5.0, "output": 25.0, "cached_input": 0.5},
    # Claude 4 Sonnet
    "claude-sonnet-4-20250514": {"input": 15.0, "output": 75.0, "cached_input": 1.5},
    # Claude 4 Opus
    "claude-opus-4-20250514": {"input": 30.0, "output": 150.0, "cached_input": 3.0},
    "claude-opus-4@20250508": {"input": 30.0, "output": 150.0, "cached_input": 3.0},
    # Default fallback pricing if model not found
    "default": {"input": 5.0, "output": 25.0, "cached_input": 0.5},
}

# Path for token usage log
# Can be overridden with TOKEN_LOG_PATH environment variable
TOKEN_LOG_PATH = os.environ.get(
    "TOKEN_LOG_PATH", Path.home() / ".anthropic" / "token_usage.json"
)
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
            cached_cost = (self.cached_input_tokens / 1_000_000) * pricing[
                "cached_input"
            ]

        self.cost_usd = input_cost + output_cost + cached_cost
        return self.cost_usd


class TokenTracker:
    """Track token usage across multiple API calls."""

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else Path(TOKEN_LOG_PATH)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start_time = datetime.now()

        # Track only aggregates
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cached_input_tokens = 0
        self.total_thinking_tokens = 0
        self.total_cost_usd = 0.0
        self.total_requests = 0

        # Create directory if it doesn't exist
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def add_usage(self, usage: TokenUsage):
        """Add usage to aggregated totals and update the log file."""
        usage.calculate_cost()

        # Update aggregates directly
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_cached_input_tokens += usage.cached_input_tokens
        self.total_thinking_tokens += usage.thinking_tokens
        self.total_cost_usd += usage.cost_usd
        self.total_requests += 1

        self._write_to_file()

    def _write_to_file(self):
        """Write aggregated stats to the log file."""
        session_data = self.get_session_stats()

        data = {
            "session_id": self.session_id,
            "last_updated": datetime.now().isoformat(),
            "session_stats": session_data,
        }

        with open(self.log_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_session_stats(self) -> Dict:
        """Get statistics for the current session."""
        # Calculate session duration
        now = datetime.now()
        session_duration = now - self.session_start_time
        duration_seconds = session_duration.total_seconds()

        # Format duration as HH:MM:SS
        hours, remainder = divmod(int(duration_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        formatted_duration = f"{hours:02}:{minutes:02}:{seconds:02}"

        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cached_input_tokens": self.total_cached_input_tokens,
            "total_thinking_tokens": self.total_thinking_tokens,
            "total_requests": self.total_requests,
            "total_cost_usd": self.total_cost_usd,
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
