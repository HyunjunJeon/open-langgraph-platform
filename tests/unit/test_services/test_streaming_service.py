"""StreamingService unit tests

Core function tests to improve test coverage.
"""


from src.agent_server.services.streaming_service import StreamingService


class TestStreamingServiceInit:
    """Tests for StreamingService initialization"""

    def test_initialization(self):
        """Verify that the service initializes correctly"""
        service = StreamingService()

        assert service.event_counters == {}
        assert service.event_converter is not None


class TestProcessInterruptUpdates:
    """Tests for the _process_interrupt_updates method"""

    def setup_method(self):
        """Create a StreamingService instance before each test"""
        self.service = StreamingService()

    def test_process_interrupt_updates_skip_non_interrupt(self):
        """Skip non-interrupt updates events"""
        raw_event = ("updates", {"key": "value"})
        only_interrupt_updates = True

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        # Skip because it's not an interrupt
        assert should_skip is True

    def test_process_interrupt_updates_pass_interrupt(self):
        """Pass interrupt updates by converting them to values"""
        raw_event = ("updates", {"__interrupt__": [{"type": "human"}]})
        only_interrupt_updates = True

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        # Pass because it's an interrupt and convert to values
        assert should_skip is False
        assert processed_event[0] == "values"

    def test_process_interrupt_updates_with_disabled_filter(self):
        """Do not filter when only_interrupt_updates=False"""
        raw_event = ("updates", {"key": "value"})
        only_interrupt_updates = False

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        # Do not skip because filtering is disabled
        assert should_skip is False
        assert processed_event == raw_event

    def test_process_interrupt_updates_non_tuple_event(self):
        """Pass non-tuple events as is"""
        raw_event = {"event": "data"}
        only_interrupt_updates = True

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        assert should_skip is False
        assert processed_event == raw_event


