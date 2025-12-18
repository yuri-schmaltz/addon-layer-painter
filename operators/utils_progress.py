"""Progress feedback system for Layer Painter operations.

Provides real-time progress updates to UI for long-running operations like baking.

Key Components:
- ProgressTracker: Core progress tracking
- progress_callback: UI update mechanism
- Context managers for automatic progress cleanup
"""

import bpy
from typing import Callable, Optional


class ProgressTracker:
    """Tracks progress for long-running operations."""
    
    def __init__(self, 
                 name: str,
                 total_steps: int,
                 callback: Optional[Callable] = None):
        """Initialize progress tracker.
        
        Args:
            name: Operation name (e.g., "Baking Channels")
            total_steps: Total steps to complete
            callback: Optional callback(name, current, total, percent) for UI updates
        """
        self.name = name
        self.total_steps = max(total_steps, 1)  # Avoid division by zero
        self.current_step = 0
        self.callback = callback
        self._started = False
    
    def start(self):
        """Start progress tracking."""
        self._started = True
        self.current_step = 0
        self._update()
    
    def step(self, count: int = 1):
        """Advance progress by count steps."""
        self.current_step = min(self.current_step + count, self.total_steps)
        self._update()
    
    def set_progress(self, current: int):
        """Set progress to specific step."""
        self.current_step = min(max(current, 0), self.total_steps)
        self._update()
    
    def finish(self):
        """Mark operation as finished."""
        self.current_step = self.total_steps
        self._update()
    
    def _update(self):
        """Update UI with progress."""
        if self.callback:
            percent = (self.current_step / self.total_steps) * 100
            self.callback(
                name=self.name,
                current=self.current_step,
                total=self.total_steps,
                percent=percent
            )
    
    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        return (self.current_step / self.total_steps) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.current_step >= self.total_steps


class ProgressContext:
    """Context manager for progress tracking."""
    
    def __init__(self,
                 name: str,
                 total_steps: int,
                 callback: Optional[Callable] = None):
        """Initialize progress context.
        
        Args:
            name: Operation name
            total_steps: Total steps
            callback: Optional progress callback
        """
        self.tracker = ProgressTracker(name, total_steps, callback)
    
    def __enter__(self):
        """Start progress tracking on enter."""
        self.tracker.start()
        return self.tracker
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finish progress tracking on exit."""
        if exc_type is None:
            self.tracker.finish()
        return False


# Global progress callback for UI updates
_progress_callback: Optional[Callable] = None


def set_progress_callback(callback: Optional[Callable]):
    """Set global progress callback for UI updates.
    
    Callback signature: callback(name: str, current: int, total: int, percent: float)
    """
    global _progress_callback
    _progress_callback = callback


def get_progress_callback() -> Optional[Callable]:
    """Get global progress callback."""
    return _progress_callback


def update_progress(name: str, current: int, total: int):
    """Update progress globally.
    
    Args:
        name: Operation name
        current: Current step
        total: Total steps
    """
    if _progress_callback:
        percent = (current / max(total, 1)) * 100
        _progress_callback(name=name, current=current, total=total, percent=percent)
